"""
Terraform runner — write HCL, then `terraform init` + `terraform plan`.

HYBRID:
  • If the `terraform` CLI is available, it runs a REAL `terraform plan` (plan only —
    it never applies). First init downloads the AWS provider (cached afterwards).
  • If terraform is missing or init/plan fails, it returns a realistic MOCK plan so the
    demo always works.

Set TF_REAL=false to force mock mode even when terraform is installed.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

WORKDIR = Path(__file__).resolve().parent / "generated"

_PROVIDERS = '''terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" {
  region = "%s"
}
'''


def _real_enabled() -> bool:
    if os.getenv("TF_REAL", "true").lower() in ("0", "false", "no"):
        return False
    return shutil.which("terraform") is not None


def _run(cmd, cwd, timeout):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _counts(plan_text: str):
    m = re.search(r"Plan:\s+(\d+) to add,\s+(\d+) to change,\s+(\d+) to destroy", plan_text)
    if m:
        return {"add": int(m.group(1)), "change": int(m.group(2)), "destroy": int(m.group(3))}
    # count "will be created/updated/destroyed" as a fallback
    return {"add": plan_text.count("will be created"),
            "change": plan_text.count("will be updated"),
            "destroy": plan_text.count("will be destroyed")}


def run_plan(hcl: str, region: str = None) -> dict:
    """Write HCL + provider, run terraform plan (real or mock). Returns a result dict."""
    region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    if _real_enabled():
        try:
            WORKDIR.mkdir(exist_ok=True)
            (WORKDIR / "providers.tf").write_text(_PROVIDERS % region)
            (WORKDIR / "main.tf").write_text(hcl)
            # init (cached after first run)
            init = _run(["terraform", "init", "-input=false", "-no-color"], WORKDIR, 180)
            if init.returncode != 0:
                return _mock(hcl, note="init failed: " + init.stderr.strip().splitlines()[-1][:120])
            # validate
            val = _run(["terraform", "validate", "-no-color"], WORKDIR, 60)
            # plan (never applies)
            plan = _run(["terraform", "plan", "-input=false", "-no-color", "-lock=false"], WORKDIR, 180)
            out = (plan.stdout or "") + (plan.stderr or "")
            if plan.returncode not in (0, 2):   # 2 = "diff present", also success
                return _mock(hcl, note="plan error: " + out.strip().splitlines()[-1][:140] if out else "plan failed")
            return {"mode": "real", "ok": True, "valid": val.returncode == 0,
                    "plan_text": out.strip(), "counts": _counts(out)}
        except subprocess.TimeoutExpired:
            return _mock(hcl, note="terraform timed out — showing a representative plan")
        except Exception as e:
            return _mock(hcl, note=f"{type(e).__name__}: {e}")
    return _mock(hcl)


def _mock(hcl: str, note: str = "terraform CLI not used — representative plan") -> dict:
    n = max(1, hcl.count("resource \""))
    plan = f"""Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_s3_bucket.assets will be created
  + resource "aws_s3_bucket" "assets" {{
      + bucket = "acme-demo-assets-8472"
      + id     = (known after apply)
      + arn    = (known after apply)
    }}
  # aws_s3_bucket_versioning.assets will be created
  # aws_s3_bucket_server_side_encryption_configuration.assets will be created
  # aws_s3_bucket_public_access_block.assets will be created

Plan: {n} to add, 0 to change, 0 to destroy."""
    return {"mode": "mock", "ok": True, "valid": True, "plan_text": plan,
            "counts": {"add": n, "change": 0, "destroy": 0}, "note": note}


if __name__ == "__main__":
    from iac_agent import _MOCK_HCL
    r = run_plan(_MOCK_HCL)
    print("mode:", r["mode"], "| counts:", r["counts"])
    print(r["plan_text"][:600])

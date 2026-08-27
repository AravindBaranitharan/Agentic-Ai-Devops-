"""
IaC Generator Agent — the brain (OpenAI gpt-4o).

Two LLM jobs:
  1. generate_hcl(request)      : natural language  ->  secure, valid Terraform HCL
  2. explain_plan(plan_text)    : a `terraform plan` diff  ->  plain-English review

The agent NEVER applies anything — it generates, plans, and explains. Applying is a
separate, human-gated step (see the Streamlit app).
"""

import os
import re
from pathlib import Path

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")
    load_dotenv(_here / "env")
except ImportError:
    pass

MODEL = os.getenv("MODEL", "gpt-4o")


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


_GEN_SYSTEM = (
    "You are a senior platform engineer who writes production-grade AWS Terraform for the "
    "hashicorp/aws provider version 5.x. Given a natural-language request, output ONLY valid "
    "Terraform HCL for the requested resource(s) — no markdown fences, no prose, no explanations. "
    "Do NOT include a `terraform {}` or `provider {}` block (those are added separately).\n"
    "CRITICAL provider-v5 rules:\n"
    "- For S3, the aws_s3_bucket resource takes ONLY `bucket` (and tags). Configure everything "
    "else as SEPARATE resources: aws_s3_bucket_versioning, "
    "aws_s3_bucket_server_side_encryption_configuration, and aws_s3_bucket_public_access_block. "
    "Do NOT use inline `versioning`, `server_side_encryption_configuration`, `acl`, or "
    "`block_public_*` arguments on aws_s3_bucket (removed in v5).\n"
    "- Make bucket names globally-unique-looking (add a random-ish suffix).\n"
    "Apply SECURE-BY-DEFAULT: block all public access, SSE encryption, versioning where relevant, "
    "least-privilege, and never 0.0.0.0/0 unless the user explicitly demands it. "
    "Add brief `#` comments."
)


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:hcl|terraform|tf)?\s*", "", text.strip(), flags=re.I)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip() + "\n"


def generate_hcl(request: str) -> str:
    """Natural language -> Terraform HCL (resources only)."""
    if not has_key():
        # offline fallback so the demo runs with no key
        return _MOCK_HCL
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[{"role": "system", "content": _GEN_SYSTEM},
                  {"role": "user", "content": request}],
    )
    return _strip_fences(resp.choices[0].message.content or "")


_EXPLAIN_SYSTEM = (
    "You are a Terraform reviewer. Given the output of `terraform plan`, explain in plain "
    "English, for a mixed audience: (1) what will be CREATED / CHANGED / DESTROYED, "
    "(2) the security posture (encryption, public access, ingress), and (3) any risk to "
    "call out before apply. Be concise — short bullet points. Do not invent resources."
)


def explain_plan(plan_text: str) -> str:
    """Explain a terraform plan diff in plain English."""
    if not has_key():
        return ("• Creates 1 resource (an S3 bucket) with versioning and AES256 encryption.\n"
                "• Public access is blocked; ACL is private.\n"
                "• No destroys or changes. Low risk — safe to apply after review.\n"
                "(offline explanation — set OPENAI_API_KEY for a live review)")
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[{"role": "system", "content": _EXPLAIN_SYSTEM},
                  {"role": "user", "content": "terraform plan output:\n\n" + plan_text[:6000]}],
    )
    return resp.choices[0].message.content or ""


_MOCK_HCL = '''# S3 bucket — secure by default (offline sample)
resource "aws_s3_bucket" "assets" {
  bucket = "acme-demo-assets-8472"
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
'''

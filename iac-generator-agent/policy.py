"""
Policy-as-code — cheap guardrails on the generated HCL BEFORE plan/apply.

These are deliberately simple, readable checks (a real setup would use OPA/Conftest or
Sentinel). Each returns a finding with a severity so the UI can gate risky changes.
"""

import re


def check(hcl: str) -> list[dict]:
    findings = []
    low = hcl.lower()

    def add(ok, sid, msg):
        findings.append({"id": sid, "status": "PASS" if ok else "FAIL", "message": msg})

    # P-001 — no wide-open ingress
    add(not re.search(r'0\.0\.0\.0/0', hcl),
        "P-001", "No 0.0.0.0/0 ingress (public to the world).")

    # P-002 — no public-read ACLs
    add(not re.search(r'acl\s*=\s*"(public-read|public-read-write)"', low),
        "P-002", "No public-read S3 ACLs.")

    # P-003 — encryption present when an S3 bucket is declared
    has_bucket = "aws_s3_bucket" in low
    has_enc = "server_side_encryption" in low or "sse_algorithm" in low or "kms" in low
    add((not has_bucket) or has_enc,
        "P-003", "S3 buckets have server-side encryption configured.")

    # P-004 — public access block present for S3
    has_pab = "public_access_block" in low
    add((not has_bucket) or has_pab,
        "P-004", "S3 buckets have a public access block.")

    # P-005 — no hard-coded secrets that look like AWS keys
    add(not re.search(r'AKIA[0-9A-Z]{16}', hcl),
        "P-005", "No hard-coded AWS access keys in the HCL.")

    return findings


def verdict(findings: list[dict]) -> str:
    return "DENY" if any(f["status"] == "FAIL" for f in findings) else "PASS"

"""
S3 freshness audit — built with LangChain.

Rule: a bucket PASSES if ANY object in it was modified within the last N days
(default 30); otherwise it FAILS (stale). Empty buckets FAIL.

This module exposes:
  • s3_bucket_freshness(days)  -> list of per-bucket rows (the raw data for the table)
  • check_s3_freshness         -> a LangChain @tool wrapping the audit
  • ask_s3_agent(question)     -> a LangChain tool-calling agent (gpt-4o) that answers
                                   natural-language questions using the tool

Works in MOCK mode (offline, deterministic) or LIVE mode (real boto3) — same switch
as the rest of the app: USE_REAL_AWS=true.
"""

import os
import datetime as dt

from langchain_core.tools import tool


def _use_real() -> bool:
    return os.getenv("USE_REAL_AWS", "false").strip().lower() in ("1", "true", "yes")


# ── the audit ────────────────────────────────────────────────────────────────
def s3_bucket_freshness(days: int = 30, page_cap: int = 60) -> list[dict]:
    """Return one row per bucket: {bucket, status, latest, objects, note}.

    status is PASS (a recent object exists), FAIL (stale / empty), or ERROR (no
    permission / could not read). We short-circuit to PASS as soon as we see one
    object newer than the cutoff, so active buckets are fast; only stale buckets
    are fully scanned (bounded by page_cap)."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=days)

    if not _use_real():
        return _mock_rows(cutoff, now)

    import boto3
    base = boto3.client("s3")
    rows = []
    for b in base.list_buckets().get("Buckets", []):
        rows.append(_check_bucket_real(base, b["Name"], cutoff, now, page_cap))
    return rows


def _bucket_region(base, name: str) -> str:
    try:
        loc = base.get_bucket_location(Bucket=name).get("LocationConstraint")
        if loc == "EU":
            return "eu-west-1"
        return loc or "us-east-1"          # us-east-1 reports None
    except Exception:
        return os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def _check_bucket_real(base, name, cutoff, now, page_cap) -> dict:
    import boto3
    try:
        cli = boto3.client("s3", region_name=_bucket_region(base, name))
        latest, scanned, recent, pages = None, 0, False, 0
        for page in cli.get_paginator("list_objects_v2").paginate(Bucket=name):
            pages += 1
            for obj in page.get("Contents", []):
                scanned += 1
                lm = obj["LastModified"]
                if latest is None or lm > latest:
                    latest = lm
                if lm >= cutoff:
                    recent = True
                    break
            if recent or pages >= page_cap:
                break
        if scanned == 0:
            return {"bucket": name, "status": "FAIL", "latest": None, "objects": 0, "note": "empty — no objects"}
        status = "PASS" if recent else "FAIL"
        age = (now - latest).days
        note = f"updated {age}d ago" if status == "PASS" else f"stale — newest is {age}d old"
        if pages >= page_cap and not recent:
            note += " (scan capped)"
        return {"bucket": name, "status": status, "latest": latest, "objects": scanned, "note": note}
    except Exception as e:
        code = getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)
        return {"bucket": name, "status": "ERROR", "latest": None, "objects": None, "note": code}


def _mock_rows(cutoff, now) -> list[dict]:
    samples = [
        ("acme-prod-assets",  now - dt.timedelta(days=2),   128),
        ("acme-app-logs",     now - dt.timedelta(days=1),  4021),
        ("customer-uploads",  now - dt.timedelta(days=18),  340),
        ("acme-backups-2021", now - dt.timedelta(days=410),  57),
        ("legacy-archive",    now - dt.timedelta(days=95),   12),
        ("empty-scratch",     None,                           0),
    ]
    rows = []
    for name, latest, count in samples:
        if count == 0 or latest is None:
            rows.append({"bucket": name, "status": "FAIL", "latest": None, "objects": 0, "note": "empty — no objects"})
            continue
        status = "PASS" if latest >= cutoff else "FAIL"
        age = (now - latest).days
        note = f"updated {age}d ago" if status == "PASS" else f"stale — newest is {age}d old"
        rows.append({"bucket": name, "status": status, "latest": latest, "objects": count, "note": note})
    return rows


def format_rows(rows: list[dict], days: int = 30) -> str:
    """Compact text summary — this is what the LangChain tool returns to the model."""
    lines = [f"S3 freshness (PASS = an object modified within {days} days):"]
    for r in rows:
        when = r["latest"].strftime("%Y-%m-%d") if r["latest"] else "—"
        lines.append(f"  [{r['status']:<4}] {r['bucket']}  (newest: {when}; {r['note']})")
    npass = sum(1 for r in rows if r["status"] == "PASS")
    nfail = sum(1 for r in rows if r["status"] == "FAIL")
    lines.append(f"Summary: {npass} PASS, {nfail} FAIL, {len(rows)} total.")
    return "\n".join(lines)


# ── LangChain tool ───────────────────────────────────────────────────────────
@tool
def check_s3_freshness(days: int = 30) -> str:
    """Audit every S3 bucket for freshness. A bucket PASSES if any object was modified
    within `days` days (default 30), otherwise it FAILS (stale). Use this to answer
    questions about which buckets are active vs stale/abandoned."""
    return format_rows(s3_bucket_freshness(days), days)


# ── LangChain agent (gpt-4o) — LangChain 1.x create_agent ────────────────────
_SYSTEM = (
    "You are an AWS S3 auditor. Use the provided tool to inspect buckets and answer the "
    "question. PASS means a bucket had an object modified within the window; FAIL means it "
    "is stale. Be concise and, when useful, list the failing buckets."
)


def ask_s3_agent(question: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "Set OPENAI_API_KEY to use the LangChain agent. (The table above works without it.)"
    from langchain.agents import create_agent

    agent = create_agent(
        "openai:" + os.getenv("MODEL", "gpt-4o"),
        [check_s3_freshness],
        system_prompt=_SYSTEM,
    )
    out = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return out["messages"][-1].content

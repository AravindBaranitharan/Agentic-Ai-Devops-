"""
Real GitHub Actions access for the CI/CD Build-Failure Triage Agent.

Production-standard, no mock: this talks to the live GitHub REST API to read failed
workflow runs, their jobs, the failing step, and the real job logs — and (guarded) to
post a triage comment back on the commit.

Auth (in order):
  1. GITHUB_TOKEN in the environment / .env
  2. `gh auth token`  (the GitHub CLI, if you're logged in)

Repo:  GITHUB_REPO="owner/name"  (defaults to this course repo).
"""

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")
    load_dotenv(_here / "env")
except ImportError:
    pass

API = "https://api.github.com"
DEFAULT_REPO = "AravindBaranitharan/Agentic-Ai-Devops-"


@lru_cache(maxsize=1)
def _token() -> str | None:
    t = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if t:
        return t.strip()
    try:  # fall back to the GitHub CLI's token
        return subprocess.check_output(["gh", "auth", "token"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def repo() -> str:
    return os.getenv("GITHUB_REPO", DEFAULT_REPO).strip()


def has_auth() -> bool:
    return bool(_token())


def _headers(raw: bool = False) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    if raw:
        h["Accept"] = "application/vnd.github.raw"
    return h


def whoami() -> str:
    try:
        r = requests.get(f"{API}/user", headers=_headers(), timeout=10)
        return r.json().get("login", "?") if r.ok else "unauthenticated"
    except Exception:
        return "unauthenticated"


# --------------------------------------------------------------------------- #
#  Runs
# --------------------------------------------------------------------------- #
def list_failed_runs(limit: int = 15) -> list[dict]:
    """The most recent FAILED workflow runs for the repo."""
    url = f"{API}/repos/{repo()}/actions/runs"
    r = requests.get(url, headers=_headers(),
                     params={"status": "failure", "per_page": limit}, timeout=20)
    r.raise_for_status()
    runs = r.json().get("workflow_runs", [])
    return [{
        "id": w["id"],
        "name": w.get("name") or w.get("display_title"),
        "title": w.get("display_title"),
        "branch": w.get("head_branch"),
        "event": w.get("event"),
        "sha": w.get("head_sha", "")[:7],
        "full_sha": w.get("head_sha", ""),
        "created_at": w.get("created_at"),
        "url": w.get("html_url"),
        "run_number": w.get("run_number"),
    } for w in runs]


def get_run(run_id: int) -> dict:
    r = requests.get(f"{API}/repos/{repo()}/actions/runs/{run_id}", headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()


def get_run_jobs(run_id: int) -> list[dict]:
    """Jobs for a run, each with its failing step highlighted."""
    r = requests.get(f"{API}/repos/{repo()}/actions/runs/{run_id}/jobs",
                     headers=_headers(), params={"per_page": 50}, timeout=20)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        failed_steps = [s["name"] for s in (j.get("steps") or [])
                        if s.get("conclusion") == "failure"]
        out.append({
            "id": j["id"], "name": j["name"],
            "conclusion": j.get("conclusion"),
            "failed_steps": failed_steps,
            "url": j.get("html_url"),
        })
    return out


def get_job_logs(job_id: int, tail_chars: int = 8000) -> str:
    """The REAL log text for a job (redirects to a plaintext blob)."""
    url = f"{API}/repos/{repo()}/actions/jobs/{job_id}/logs"
    r = requests.get(url, headers=_headers(), timeout=30, allow_redirects=True)
    if not r.ok:
        return f"(could not fetch logs: HTTP {r.status_code})"
    text = r.text
    return text[-tail_chars:] if len(text) > tail_chars else text


def extract_error_region(logs: str, span: int = 60) -> str:
    """Pull the lines around the first real error signal — what a human scans for."""
    lines = logs.splitlines()
    signals = re.compile(r"(?i)\b(error|failed|assert|traceback|exception|"
                         r"could not find|no matching distribution|exit code [1-9]|"
                         r"\bE\s+|FAILED)\b")
    hits = [i for i, ln in enumerate(lines) if signals.search(ln)]
    if not hits:
        return "\n".join(lines[-span:])
    lo = max(0, hits[0] - 8)
    hi = min(len(lines), hits[-1] + 6)
    if hi - lo > span * 3:                       # keep it focused
        hi = min(len(lines), hits[0] + span)
    return "\n".join(lines[lo:hi])


# --------------------------------------------------------------------------- #
#  Guarded write — post the triage back on the commit
# --------------------------------------------------------------------------- #
def post_commit_comment(sha: str, body: str) -> dict:
    """Post a comment on the commit that produced the failed run. Guarded caller only."""
    url = f"{API}/repos/{repo()}/commits/{sha}/comments"
    r = requests.post(url, headers=_headers(), json={"body": body}, timeout=20)
    if r.ok:
        return {"ok": True, "url": r.json().get("html_url")}
    return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}

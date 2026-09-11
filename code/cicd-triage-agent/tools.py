"""
LangChain tools the triage agent calls to INVESTIGATE a failed build.

Thin, read-only wrappers over github_tools — the same steps a human does: open the
failed run, find the failing job/step, read the real logs. The LangGraph agent decides
which to call and when; nothing here mutates the repo.
"""

import json
from langchain_core.tools import tool

import github_tools as gh


@tool
def list_failed_runs() -> str:
    """List the most recent FAILED GitHub Actions runs (id, workflow name, branch, commit)."""
    runs = gh.list_failed_runs(15)
    return json.dumps(runs, indent=2) if runs else "No failed runs found."


@tool
def get_run_jobs(run_id: int) -> str:
    """For a run id, list its jobs, each job's conclusion, and which STEPS failed."""
    return json.dumps(gh.get_run_jobs(run_id), indent=2)


@tool
def get_job_logs(job_id: int) -> str:
    """Read the REAL logs for a failed job — focused on the error region (the lines a
    human scans to find the cause)."""
    logs = gh.get_job_logs(job_id)
    return gh.extract_error_region(logs)


# the toolbox the investigation agent is given
INVESTIGATION_TOOLS = [list_failed_runs, get_run_jobs, get_job_logs]

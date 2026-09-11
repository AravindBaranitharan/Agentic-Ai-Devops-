"""
Poster — the ONLY place this project writes to GitHub, and it is guarded:

  • It runs only after an explicit human approval in the UI.
  • DRY-RUN is the default; a real comment is posted only when execute=True.
  • The single action is "post a triage comment on the failing commit" — there is no
    arbitrary-write path.
"""

import github_tools as gh


def render_comment(diag: dict, run: dict) -> str:
    """Format the triage as a Markdown comment."""
    conf = diag.get("confidence", "—")
    return (
        f"## 🤖 CI Build-Failure Triage\n\n"
        f"**Workflow:** `{run.get('name')}`  ·  **Run:** [#{run.get('run_number')}]({run.get('url')})  "
        f"·  **Commit:** `{run.get('sha')}`\n\n"
        f"**Category:** `{diag.get('category','?')}`  ·  **Confidence:** {conf}\n\n"
        f"**Failing job / step:** `{diag.get('failing_job','?')}` → `{diag.get('failing_step','?')}`\n\n"
        f"### Root cause\n{diag.get('root_cause','—')}\n\n"
        f"### Evidence\n```\n{diag.get('evidence','—')}\n```\n\n"
        f"### Suggested fix\n{diag.get('fix','—')}\n\n"
        f"<sub>Posted by the CI/CD Build-Failure Triage Agent · gpt-4o · human-approved.</sub>"
    )


def post_triage(diag: dict, run: dict, execute: bool = False) -> dict:
    """Post (or dry-run) the triage comment on the failing commit."""
    body = render_comment(diag, run)
    if not execute:
        return {"ok": True, "mode": "DRY-RUN",
                "message": "Approved (dry-run) — comment NOT posted. Preview below.",
                "preview": body}
    if not gh.has_auth():
        return {"ok": False, "mode": "ERROR",
                "message": "No GitHub token — set GITHUB_TOKEN or run `gh auth login`."}
    res = gh.post_commit_comment(run["full_sha"], body)
    if res.get("ok"):
        return {"ok": True, "mode": "POSTED",
                "message": f"Comment posted on commit {run['sha']}.",
                "url": res.get("url"), "preview": body}
    return {"ok": False, "mode": "ERROR", "message": res.get("error", "post failed"),
            "preview": body}

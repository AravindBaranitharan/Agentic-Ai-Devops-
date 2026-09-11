# 🔧 CI/CD Build-Failure Triage Agent

A **LangGraph** agent that triages **real** failed CI builds. It reads your failed
**GitHub Actions** runs, investigates the **real job logs**, diagnoses the root cause with
gpt-4o (test failure? dependency? compile? flaky?), and posts a triage report back on the
commit — **only after you approve**.

> Failed run → the agent reads jobs + real logs → **structured triage (gpt-4o)** → **human-gated** commit comment.

**Production-standard, no mock data.** It talks to the live GitHub REST API and reasons over
the actual logs your pipeline produced.

## What it does
1. **Lists** your repo's failed GitHub Actions runs (live).
2. **Investigates** a run in a ReAct loop — finds the failing job/step and reads the **real logs**.
3. **Diagnoses** with gpt-4o → a structured triage: category · failing job/step · root cause · **evidence (real log lines)** · concrete fix · confidence.
4. **Posts** the triage as a commit comment — dry-run by default, real post only on your approval.

The LLM only reads and reasons; the single write (a comment) runs only after a human approves.

## Prerequisites
| Need | Why |
|------|-----|
| **Python 3.10+** | runtime |
| **OpenAI API key** (gpt-4o) | the reasoning brain |
| **A GitHub repo with Actions** | the real CI source (this course repo by default) |
| **GitHub auth** | read runs/logs + post the comment — either `GITHUB_TOKEN` in `.env`, or just `gh auth login` (the agent uses the CLI's token automatically) |

**Least-privilege token** (fine-grained PAT, scoped to the one repo): `Actions: Read` · `Contents: Read` · `Commit statuses: Write` (to post).

## Files
| File | What it is |
|------|------------|
| `agent_graph.py` | The **LangGraph** orchestration: investigate ⇄ tools → diagnose → human gate → post. |
| `tools.py` | The agent's read-only LangChain tools (`list_failed_runs`, `get_run_jobs`, `get_job_logs`). |
| `github_tools.py` | Live GitHub REST access — runs, jobs, real logs, error-region extraction, commit comment. |
| `poster.py` | The only write — a guarded, human-gated triage comment (dry-run default). |
| `app.py` | Streamlit UI that drives the graph and shows the investigation trace + triage. |
| `sample-project/` | A tiny app with a real bug (`add()` subtracts) that the CI builds. |
| `live-ci/` | The real failing GitHub Actions workflows (copy to `.github/workflows/`). |

## Run — the live demo
```bash
cd cicd-triage-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env                 # add OPENAI_API_KEY

# GitHub auth (either one):
gh auth login                      # simplest — the agent uses this token
# or put GITHUB_TOKEN=... in .env

streamlit run app.py
```

### Generating real failed runs to triage
The `live-ci/` workflows fail on purpose (a failing unit test, a bad dependency pin).
Copy them to your repo's `.github/workflows/` and push — GitHub Actions runs them, they
fail for real, and they show up in the agent's list.

## Real-time demo — where to connect, what's needed, how it happens
- **Where it connects:** OpenAI (gpt-4o) for reasoning; the **GitHub REST API** for runs, jobs, logs, and the comment.
- **What you need:** `OPENAI_API_KEY`, GitHub auth (token or `gh`), and at least one failed run in the repo.
- **How it happens:** pick a failed run → the LangGraph agent calls `get_run_jobs`/`get_job_logs` live → produces a structured triage from the real logs → the graph pauses at the approval gate → you approve (dry-run by default; flip *Actually post* to comment on the commit).

## Safety
- The LLM only **reads and reasons**. The one write (`poster.py`) posts a single comment, only after explicit human approval.
- Dry-run is the default; nothing is posted until you toggle *Actually post* and approve.
- Least-privilege token; `.env` is git-ignored — never commit your keys.

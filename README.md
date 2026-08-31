# Agentic AI for DevOps

Hands-on labs from the **AI Agents for Cloud & DevOps** course — prepared by Aravind Baranitharan.

**Each day is one self-contained folder.** Everything you need for a lab — code, docs,
`requirements.txt`, and an `env.sample` — lives inside that day's folder. New folders are
pushed as the course progresses.

## Labs

| Day | Folder | What you build |
|-----|--------|----------------|
| 10 | [`day-10-agent-from-scratch/`](day-10-agent-from-scratch/) | A tool-using AI agent in plain Python — no framework. OpenAI **gpt-4o** tool-calling loop over mocked Kubernetes tools. |

## Projects

| Project | Folder | What it is |
|---------|--------|------------|
| AWS ChatOps Agent | [`aws-chatops-agent/`](aws-chatops-agent/) | A real-world **agentic AI** demo: operate AWS (EC2 · S3 · CloudWatch) from a **Streamlit** chat box. gpt-4o + `boto3` tools + a human **approval gate** on every state change. Runs on mock data or live AWS. Includes the project presentation (PDF). |
| Chat-FinOps Agent | [`chat-finops-agent/`](chat-finops-agent/) | An AI **FinOps** agent: analyze AWS cost, explain month-over-month changes, and surface waste (idle EC2, unused EBS/EIP, old snapshots, stale S3) with **$/mo savings** — a Streamlit dashboard + a **LangChain** (gpt-4o) chat. Read-only; hybrid live/mock. |
| LangChain & LangGraph demo | [`langchain-langgraph-demo/`](langchain-langgraph-demo/) | Teaching material for two sessions: runnable **LangChain** (LCEL, tools/agent, structured output) and **LangGraph** (state graph, agent loop, human-in-the-loop) examples, plus two interactive decks (What-is-LangChain / What-is-LangGraph, PDF) and a comparison. |
| IaC Generator Agent | [`iac-generator-agent/`](iac-generator-agent/) | Natural language → reviewed **Terraform**: gpt-4o generates secure HCL, runs a real `terraform plan`, explains the diff, checks policy, and gates `apply` behind human approval. Streamlit app + 3-slide deck (PDF). |
| K8s Troubleshooting Agent | [`k8s-troubleshooting-agent/`](k8s-troubleshooting-agent/) | Finds broken **Kubernetes** pods, reads their status + events + logs, and gpt-4o explains the **root cause** (CrashLoopBackOff, OOMKilled, ImagePullBackOff, Unschedulable…) with a proposed fix — remediation (restart/scale/delete-pod) is a safe allow-list behind **human approval**. Read-only; real cluster or built-in mock. Streamlit app + 3-slide deck (PDF). |

## How every lab works

```bash
cd day-XX-...                       # enter the day's folder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env                  # rename, then paste your OPENAI_API_KEY inside
python <main script>.py
```

- **No API key?** Every lab still runs end-to-end in OFFLINE mode with deterministic mock data.
- **With your `OPENAI_API_KEY`** the same code runs LIVE on gpt-4o — the DevOps tools stay
  mocked, so nothing real (cluster/cloud/CI) is ever touched.
- Never commit your real `.env` — it is git-ignored.

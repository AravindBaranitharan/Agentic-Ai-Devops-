# Agentic AI for DevOps

Hands-on labs from the **AI Agents for Cloud & DevOps** course — prepared by Aravind Baranitharan.

**Each day is one self-contained folder.** Everything you need for a lab — code, docs,
`requirements.txt`, and an `env.sample` — lives inside that day's folder. New folders are
pushed as the course progresses.

## Labs

| Day | Folder | What you build |
|-----|--------|----------------|
| 10 | [`day-10-agent-from-scratch/`](day-10-agent-from-scratch/) | A tool-using AI agent in plain Python — no framework. OpenAI **gpt-4o** tool-calling loop over mocked Kubernetes tools. |

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

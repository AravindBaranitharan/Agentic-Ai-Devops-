# Agentic AI for DevOps

Hands-on code from the **AI Agents for Cloud & DevOps** course — prepared by Aravind Baranitharan.

## Day 10 — Build a Tool-Using Agent From Scratch

A working, tool-using AI agent in plain Python — no framework. The agent diagnoses a
(mocked) Kubernetes namespace by choosing and chaining tools (`get_pods`, `get_pod_logs`)
through the OpenAI **gpt-4o** tool-calling loop.

**[→ day-10-agent-from-scratch/](day-10-agent-from-scratch/)** — code + full README (what it does, how to run, expected output).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # paste your OPENAI_API_KEY (optional)

cd day-10-agent-from-scratch
python agent.py               # runs OFFLINE with scripted data if no key is set
```

- **No API key?** The demo still runs end-to-end with deterministic mock data.
- **With `OPENAI_API_KEY`** the same loop is driven live by gpt-4o; the cluster tools stay mocked, so nothing real is touched.

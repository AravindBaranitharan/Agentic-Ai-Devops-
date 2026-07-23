# Day 10 · Build a Tool-Using Agent From Scratch

Companion code for **hour-10** (the Module 2 capstone). We implement the entire
agent architecture from Hours 5–6 — **model + tools + memory + orchestration loop**
— in plain Python, no framework. Once you understand this, every agent framework
is just ergonomics on top of the same loop.

## Files

| File | What it is |
|------|------------|
| `tools.py` | Step 1 — two mocked DevOps tools (`get_pods`, `get_pod_logs`) + their JSON schemas, the `TOOLS` list, and the `REGISTRY` (name → function). |
| `agent.py` | Steps 2–5 — dispatch, memory, the agent loop, and secrets. Runnable live or offline. |
| `sample_session.md` | A full reference transcript to show in class. |
| `requirements.txt` | Everything to `pip install` — this folder is fully self-contained. |
| `env.sample` | Rename to `.env` and paste your `OPENAI_API_KEY` for a LIVE run. |

## Run it (everything happens inside THIS folder)

```bash
cd day-10-agent-from-scratch

python -m venv .venv && source .venv/bin/activate   # recommended (Windows: .venv\Scripts\activate)
pip install -r requirements.txt                     # one-time

cp env.sample .env      # ← rename, then open .env and paste your OPENAI_API_KEY (optional)
python agent.py
```

- **No key?** It runs in **OFFLINE mode** with a scripted model that walks the *exact
  same loop* — perfect for teaching the mechanics with zero setup.
- **Key set?** It runs **LIVE** — real gpt-4o (`OPENAI_API_KEY`) chooses which tools
  to call. The tools are still mocked, so no real cluster is needed.

Expected output: the agent lists pods, sees `checkout` in `CrashLoopBackOff`, reads
its logs, finds `OOMKilled`, and recommends raising the memory limit. See
`sample_session.md`.

## The 5 build steps (mapped to the deck)

1. **Define tools** (`tools.py`) — a function + a schema the model reads. The
   `description` is prompt; write it well. Start read-only.
2. **Registry & dispatch** (`run_tool` in `agent.py`) — map the model's `tool_calls`
   to real code, echo back the `tool_call_id`, return errors *as results*.
3. **Memory** (`messages` list) — the model is stateless; "memory" is a growing list
   you resend each turn: system → user → assistant(tool_calls) → tool → …
4. **The agent loop** (`run_agent`) — call model → if the message has `tool_calls`,
   run tools and feed results back → repeat → stop when it answers. `MAX_STEPS`
   guarantees termination.
5. **Config & secrets** — load `OPENAI_API_KEY` from `.env`; never hardcode keys;
   give the agent's real cloud creds **least privilege**.

## Hardening checklist (demo → production — bridges to Module 3)

- [ ] **Bounded loops** — `MAX_STEPS` + per-tool timeouts so it can't run away.
- [ ] **Tool errors as results** — let the agent recover instead of crashing.
- [ ] **Dry-run mode** — preview write actions; require approval before mutating prod.
- [ ] **Input/output validation** — reject unexpected or unsafe tool args.
- [ ] **Logging & tracing** — record every step, tool call, and token cost.

> The demo loop is ~20 lines. **Production is the guardrails around it** — exactly
> what the next 30 hours (Module 3) build into 10 real DevOps agents.

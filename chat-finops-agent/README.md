# 💰 Chat-FinOps Agent

An AI **FinOps** agent that analyzes AWS cost, explains changes, and surfaces waste with
**dollar-value savings** — all read-only. Ask questions in plain English; get a live dashboard
and a LangChain + gpt-4o chat. (This build covers Phases 1–3: insight + savings. Approval &
guarded execution are the next phases.)

## What it does
1. **Cost visibility** — month-end forecast vs budget, 6-month trend, spend per account.
2. **Cost analytics** — cost by service, month-over-month movers, spike root-cause.
3. **Optimization** — idle/low-use EC2, unattached EBS, unassociated Elastic IPs, old
   snapshots, stale S3 — each with an estimated **$/mo saving** and an annualized total.

## Files
| File | What it is |
|------|------------|
| `finops_tools.py` | Cost (real Cost Explorer → mock fallback) + optimization detectors (live boto3, read-only) + savings math. |
| `finops_agent.py` | LangChain 1.x `create_agent` (gpt-4o) exposing the tools as `@tool`s. |
| `app.py` | Streamlit **dashboard** — visibility, analytics, and the savings scan. |
| `pages/1_Chat.py` | Streamlit **chat** page — ask the LangChain FinOps agent. |
| `iam-policy.json` | Least-privilege **read-only** IAM policy. |
| `env.sample` | Rename to `.env`, paste your keys. |

## Run
```bash
cd chat-finops-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env      # paste OPENAI_API_KEY + (for live) AWS keys, set USE_REAL_AWS=true
streamlit run app.py    # dashboard; sidebar → "Chat"
```

## Modes (hybrid)
- **Optimization** always runs **live** against the account when `USE_REAL_AWS=true` — it needs
  no lead time and finds real waste today.
- **Cost dashboard** uses **real Cost Explorer** once it's enabled (Billing → Cost Explorer →
  Enable; ~24h for first data); until then it shows clearly-labeled **sample** figures.
- With `USE_REAL_AWS=false` everything is deterministic mock data — safe anywhere.

## Notes for a live demo
- The savings scan is **read-only** — it never stops, resizes, or deletes anything.
- Enable Cost Explorer ahead of time for live billing charts; the optimization numbers are live regardless.
- IAM: attach `iam-policy.json` (adds Cost Explorer, Compute Optimizer, CloudWatch metrics, and
  resource `Describe*` on top of basic read access).

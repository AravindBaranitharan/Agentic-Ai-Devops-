# 🏗️ IaC Generator Agent

Turn **plain English into reviewed Terraform**. The agent generates secure HCL, runs a real
`terraform plan`, explains the diff in plain language, checks it against policy, and waits for a
human before anything is applied.

> Natural language → Terraform → `terraform plan` → explained diff → policy → **human-gated apply**.

## What it is (in plain terms)
Writing infrastructure-as-code is slow and error-prone, and a wrong `apply` can break prod or
open a security hole. This agent lets anyone *describe* what they want ("a private S3 bucket with
versioning and encryption"), and it:
1. **Generates** production-grade Terraform (secure-by-default, AWS provider v5) with gpt-4o.
2. **Plans** it — runs a real `terraform plan` so you see exactly what would change (nothing is applied).
3. **Explains** the plan diff in plain English — what's created/changed/destroyed and the security posture.
4. **Checks policy** — no public buckets, encryption required, no `0.0.0.0/0`, no hard-coded keys.
5. **Gates apply** — a human approves before `terraform apply` ever runs.

The human stays in control; the LLM never touches your cloud directly — Terraform does, and only the plan runs automatically.

## Files
| File | What it is |
|------|------------|
| `iac_agent.py` | gpt-4o: `generate_hcl()` (NL → HCL) and `explain_plan()` (diff → plain English). |
| `terraform_runner.py` | Writes HCL + provider, runs `terraform init`/`plan` (real; mock fallback). |
| `policy.py` | Policy-as-code checks on the generated HCL (PASS/DENY). |
| `app.py` | Streamlit demo: generate → plan → explain → policy → gated apply. |
| `iam-policy.json` | Least-privilege AWS policy for plan (and the S3 apply example). |
| `env.sample` | Rename to `.env`, add keys. |

## Prerequisites — what you need
- **Python 3.10+**
- **Terraform CLI** (`brew install terraform`) — for a *real* plan. Without it, the app uses a realistic mock plan.
- **OpenAI API key** — for generation + explanation.
- **AWS credentials** — only for a real `terraform plan`/`apply` against AWS (env vars, `~/.aws`, or a role). Plan needs just `sts:GetCallerIdentity`; apply needs the resource permissions in `iam-policy.json`.

## Run
```bash
cd iac-generator-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env       # add OPENAI_API_KEY (+ AWS keys for a real plan)
streamlit run app.py
```

## Real-time demo — where to connect, what's needed, how it happens
- **Where it connects:**
  - **OpenAI** (gpt-4o) — generates the HCL and explains the plan.
  - **Terraform CLI** (local) — runs `init` + `plan` in `generated/`.
  - **AWS** — the AWS provider authenticates with your credentials to produce a real plan. `terraform plan` is **read-only** (it refreshes/plans; it does **not** create anything). Apply is separate and human-gated.
- **What you need for the live demo:** terraform installed, `OPENAI_API_KEY` set, and AWS creds set (`USE_REAL_AWS`-style env or `~/.aws`). First `terraform init` downloads the AWS provider (cached afterwards) — run one plan before the session so it's warm.
- **How it happens (flow):**
  1. You type a request → `generate_hcl` returns HCL.
  2. `terraform_runner` writes `main.tf` + `providers.tf`, runs `terraform init` (cached) + `terraform plan`.
  3. `explain_plan` turns the plan into a plain-English review.
  4. `policy.check` gates risky output (public access, missing encryption, open ingress).
  5. If policy passes, you can **Approve & apply** (off by default; toggle to run real `terraform apply`).

## Safety
- The agent only ever **generates + plans + explains** automatically. `apply` requires an explicit human toggle + button.
- Policy DENY blocks apply entirely.
- `generated/` (Terraform state + provider binaries) is git-ignored — never committed.

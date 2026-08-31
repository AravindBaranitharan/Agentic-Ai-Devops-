# 🩺 Kubernetes Troubleshooting Agent

Point it at a namespace. It finds the **broken pods**, reads their **status + events + logs**,
explains the **root cause** in plain English, and proposes a **fix** — and nothing is changed
without a **human approval**.

> Namespace → unhealthy pods → read events/logs → **gpt-4o root-cause diagnosis** → suggested fix → **human-gated remediation**.

## What it is (in plain terms)
When a pod is broken, an engineer does the same dance every time: `kubectl get pods`, spot the
red one, `kubectl describe pod`, `kubectl logs`, then pattern-match the failure
(CrashLoopBackOff? OOMKilled? ImagePullBackOff?) to a fix. This agent automates the *reading and
reasoning* — the slow, repetitive part — and leaves the *deciding* to a human.

It:
1. **Sees** the cluster read-only (pods, container states, events, log tails).
2. **Diagnoses** the failure with gpt-4o — the actual root cause, the evidence line it keyed off, and a fix.
3. **Proposes** a single remediation (a restart / scale / delete-pod) or says *manual fix required*.
4. **Waits** — a human approves before anything touches the cluster; dry-run is the default.

The LLM only reads and reasons. The one place that can change a cluster (`remediation.py`) is a
tiny, safe allow-list, gated behind an explicit human approval.

## Files
| File | What it is |
|------|------------|
| `k8s_tools.py` | Read-only cluster access (pods, events, logs) — real `kubernetes` client, or a realistic **mock cluster** of classic failures. |
| `k8s_agent.py` | gpt-4o brain: `diagnose(bundle)` → root cause + evidence + fix + suggested action. Heuristic fallback when there's no key. |
| `remediation.py` | The only place that can change a cluster — a safe allow-list (restart / scale / delete-pod), dry-run by default, human-gated. |
| `app.py` | Streamlit demo: namespace → unhealthy pods → diagnose → fix → gated remediation. |
| `rbac.yaml` | Least-privilege RBAC — read-only role for diagnosis, optional write role for remediation. |
| `env.sample` | Rename to `.env`, add your key. |

## Prerequisites — what you need
- **Python 3.10+**
- **OpenAI API key** — for the live root-cause diagnosis. (Without it, a built-in heuristic still diagnoses the common cases.)
- **A cluster (optional)** — a kubeconfig (`~/.kube/config`, `minikube`, `kind`, EKS/GKE/AKS) only if you want to read a *real* cluster. Without one, it runs on the mock cluster.

## Run
```bash
cd k8s-troubleshooting-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env       # add OPENAI_API_KEY  (leave USE_REAL_K8S=false for the mock)
streamlit run app.py
```
Open the URL Streamlit prints. Pick the `shop` namespace to see four classic failures light up.

## Real-time demo — where to connect, what's needed, how it happens
- **Where it connects:**
  - **OpenAI** (gpt-4o) — diagnoses the failure from the pod bundle.
  - **Your cluster** (optional) — the `kubernetes` client reads pods/events/logs via your kubeconfig. All reads. Remediation is a separate, human-approved step.
- **What you need for a live demo:** set `OPENAI_API_KEY`, then either leave `USE_REAL_K8S=false`
  (mock — zero setup, always works) **or** set `USE_REAL_K8S=true` with a reachable kubeconfig.
  For a real cluster, apply `rbac.yaml` so the agent has read (and optionally remediate) rights.
- **How it happens (flow):**
  1. You pick a namespace → the app lists unhealthy pods.
  2. Pick a pod → `get_pod_bundle` gathers status + events + a log tail.
  3. `diagnose` (gpt-4o) returns root cause, evidence, fix, and a machine action.
  4. If the action is safe (restart/scale/delete-pod), you can **Approve & remediate** — dry-run by default; flip *Execute for real* to actually run it (needs a live cluster + the remediate role).

## The mock cluster (what you'll see)
`shop`: CrashLoopBackOff (missing `DATABASE_URL`), ImagePullBackOff (bad tag), OOMKilled (limit too low), Unschedulable (insufficient CPU), plus a healthy control.
`platform`: a failing readiness probe (upstream down) and a CreateContainerConfigError (missing Secret).

## Safety
- The agent only ever **reads + reasons** automatically. Any change requires an explicit human toggle + button.
- Remediation is a fixed allow-list — there is **no "run arbitrary kubectl"** path.
- Dry-run is the default; a real action needs `USE_REAL_K8S=true` **and** the write role in `rbac.yaml`.
- `.env` is git-ignored — never commit your key.

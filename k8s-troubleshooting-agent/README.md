# 🩺 Kubernetes Troubleshooting Agent

A **LangGraph** agent that troubleshoots broken pods on a **real, live cluster**. Point it at a
namespace, it finds the broken pods, and the agent **investigates each one live** — calling
read-only `kubectl`-style tools in a ReAct loop — then returns a **structured root-cause
diagnosis** and proposes a fix. Any remediation **pauses at a human-approval gate** before it runs.

> Namespace → the agent calls tools (describe / logs) → **structured diagnosis (gpt-4o)** → proposed fix → **human-gated remediation** (LangGraph `interrupt`).

## Not hard-coded — real live cases
The demo does **not** rely on canned data. `live-cases/live-cases.yaml` deploys **real workloads
that genuinely break** on a real cluster, and the agent reads them live via the Kubernetes API:

| Case | What actually happens | Failure |
|------|-----------------------|---------|
| `checkout` | container exits because `DATABASE_URL` is unset | **CrashLoopBackOff** |
| `recommender` | image tag doesn't exist in the registry | **ImagePullBackOff** |
| `image-resizer` | `stress` allocates 250M against a 150Mi limit | **OOMKilled** (exit 137) |
| `batch-nightly` | requests 64 CPU cores — no node fits it | **Pending / Unschedulable** |
| `payments-api` | readiness probe hits `/ready` (404) | **not Ready** |
| `notifier` | `envFrom` a Secret that was never created | **CreateContainerConfigError** |
| `frontend` | plain nginx | **healthy control** |

(If no cluster is reachable, the app falls back to an offline mock so it still runs — but the live cases above are the real path.)

## The agent — LangGraph orchestration (not a single LLM call)
`agent_graph.py` is an explicit state machine:

```
 investigate ⇄ tools     ReAct loop: the LLM calls read-only tools (describe_pod, get_pod_logs)
      │                    until it has enough evidence
      ▼
  diagnose                LLM → STRUCTURED diagnosis (root cause · evidence · fix · action)
      │
      ├─ action == manual ─────────────► END
      ▼
 approval_gate ─ interrupt() ─► (human decides in the UI) ─► remediate ─► END
```

- **ReAct investigation** — `investigate` + `ToolNode` + `tools_condition` loop; the agent chooses what to look at.
- **Structured output** — `diagnose` uses `with_structured_output(Diagnosis)` (a Pydantic model).
- **Human-in-the-loop** — the graph literally **pauses** at `interrupt()` (with a `MemorySaver` checkpointer) and the app resumes it with `Command(resume=<decision>)`.

## Files
| File | What it is |
|------|------------|
| `agent_graph.py` | The **LangGraph** orchestration: investigate ⇄ tools → diagnose → human gate → remediate. |
| `tools.py` | The agent's read-only LangChain tools (`list_unhealthy_pods`, `describe_pod`, `get_pod_logs`). |
| `k8s_tools.py` | Cluster access — **live-first** (real `kubernetes` client) with a mock fallback. |
| `remediation.py` | The only mutating step — a safe allow-list (restart / scale / delete-pod), human-gated. |
| `app.py` | Streamlit UI that drives the graph and shows the investigation trace + diagnosis. |
| `live-cases/live-cases.yaml` | The real failing workloads the agent troubleshoots. |
| `live-cases/setup-cluster.sh` | Spin up a local `kind` cluster and apply the live cases. |
| `rbac.yaml` | Least-privilege RBAC — read-only role for diagnosis, optional write role for remediation. |

## Prerequisites
- **Python 3.10+**
- **OpenAI API key** — the LangGraph agent needs it to reason.
- **A cluster (for the live path)** — Docker + `kind` + `kubectl` for a local one, or any real cluster (EKS/GKE/AKS/minikube). Without one, the app uses the mock fallback.

## Run — the live demo
```bash
cd k8s-troubleshooting-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env                 # add OPENAI_API_KEY  (USE_REAL_K8S=auto)

# 1) create a real cluster and load the live failure cases
brew install kind kubectl          # if you don't have them
./live-cases/setup-cluster.sh      # kind cluster + kubectl apply, waits for failures

# 2) run the agent — it auto-detects the live cluster
streamlit run app.py
```
Pick the `shop` namespace, choose a broken pod, and click **Investigate & diagnose**.
Tear down with `./live-cases/setup-cluster.sh clean`.

## Real-time demo — where to connect, what's needed, how it happens
- **Where it connects:** OpenAI (gpt-4o) for reasoning; your **cluster** via the Kubernetes client (kubeconfig) for read-only investigation. Remediation is a separate, human-approved step.
- **What you need:** `OPENAI_API_KEY`, and a reachable cluster (`USE_REAL_K8S=auto` uses it automatically). Apply `rbac.yaml` for least-privilege access on a shared cluster.
- **How it happens:** you pick a pod → the LangGraph agent calls `describe_pod`/`get_pod_logs` live → produces a structured diagnosis → if the fix is a safe automated action, the graph pauses at the approval gate → you approve (dry-run by default; flip *Execute for real* to actually run it).

## Safety
- The LLM only **reads and reasons**. The one mutating step (`remediate`) runs only after an explicit human approval.
- Remediation is a fixed allow-list (restart / scale / delete-pod) — there is **no arbitrary-kubectl** path.
- Dry-run is the default; a real action needs *Execute for real* **and** the write role in `rbac.yaml`.
- `.env` is git-ignored — never commit your key.

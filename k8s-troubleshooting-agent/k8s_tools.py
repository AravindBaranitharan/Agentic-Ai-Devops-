"""
Kubernetes read-only tools — everything the agent needs to SEE a cluster.

HYBRID:
  • If a kubeconfig is reachable and USE_REAL_K8S=true, it talks to a REAL cluster
    with the official `kubernetes` client — read-only calls (list pods, read events,
    tail logs). It never mutates anything here.
  • Otherwise it serves a realistic MOCK cluster full of classic failures
    (CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending/Unschedulable) so the
    demo always runs with no cluster attached.

Set USE_REAL_K8S=false to force the mock even when a cluster is reachable.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")
    load_dotenv(_here / "env")
except ImportError:
    pass


# --------------------------------------------------------------------------- #
#  Live-cluster detection
# --------------------------------------------------------------------------- #
def _real_enabled() -> bool:
    if os.getenv("USE_REAL_K8S", "false").lower() not in ("1", "true", "yes"):
        return False
    try:
        from kubernetes import config
        try:
            config.load_incluster_config()      # running inside a pod
        except Exception:
            config.load_kube_config()           # ~/.kube/config or KUBECONFIG
        return True
    except Exception:
        return False


def cluster_context() -> str:
    """A short label for the UI: which cluster are we looking at?"""
    if _real_enabled():
        try:
            from kubernetes import config
            _, active = config.list_kube_config_contexts()
            return f"live · {active['name']}"
        except Exception:
            return "live cluster"
    return "mock cluster"


def _core_api():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api()


def _apps_api():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.AppsV1Api()


# --------------------------------------------------------------------------- #
#  Namespaces
# --------------------------------------------------------------------------- #
def list_namespaces() -> list[str]:
    if not _real_enabled():
        return sorted({p["namespace"] for p in _MOCK_PODS})
    try:
        v1 = _core_api()
        return [ns.metadata.name for ns in v1.list_namespace().items]
    except Exception:
        return sorted({p["namespace"] for p in _MOCK_PODS})


# --------------------------------------------------------------------------- #
#  Pods
# --------------------------------------------------------------------------- #
def list_pods(namespace: str) -> list[dict]:
    """One row per pod: name, phase, reason, restarts, ready, node, healthy?"""
    if not _real_enabled():
        return [_summ(p) for p in _MOCK_PODS if p["namespace"] == namespace]
    try:
        v1 = _core_api()
        pods = v1.list_namespaced_pod(namespace).items
        return [_summ_live(p) for p in pods]
    except Exception:
        return [_summ(p) for p in _MOCK_PODS if p["namespace"] == namespace]


def unhealthy_pods(namespace: str) -> list[dict]:
    return [p for p in list_pods(namespace) if not p["healthy"]]


def get_pod_bundle(namespace: str, name: str) -> dict:
    """
    Everything the agent reasons over for ONE pod:
      status, container states + reasons, recent events, and a log tail.
    This is the equivalent of `kubectl describe pod` + `kubectl logs`.
    """
    if not _real_enabled():
        for p in _MOCK_PODS:
            if p["namespace"] == namespace and p["name"] == name:
                return dict(p)  # already the full bundle
        return {"name": name, "namespace": namespace, "error": "pod not found"}
    try:
        v1 = _core_api()
        pod = v1.read_namespaced_pod(name, namespace)
        events = v1.list_namespaced_event(
            namespace, field_selector=f"involvedObject.name={name}"
        ).items
        containers = []
        for cs in (pod.status.container_statuses or []):
            state = cs.state
            reason = detail = None
            if state.waiting:
                reason, detail = state.waiting.reason, state.waiting.message
            elif state.terminated:
                reason = state.terminated.reason
                detail = f"exit code {state.terminated.exit_code}"
            containers.append({
                "container": cs.name, "ready": cs.ready,
                "restarts": cs.restart_count, "reason": reason, "detail": detail,
            })
        logs = ""
        try:
            logs = v1.read_namespaced_pod_log(name, namespace, tail_lines=40) or ""
        except Exception as e:
            logs = f"(could not read logs: {e})"
        return {
            "name": name, "namespace": namespace,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "containers": containers,
            "events": [f"{e.reason}: {e.message}" for e in events][-12:],
            "logs": logs[-4000:],
        }
    except Exception as e:
        return {"name": name, "namespace": namespace, "error": str(e)}


# --------------------------------------------------------------------------- #
#  Summaries
# --------------------------------------------------------------------------- #
def _reason_of(bundle: dict) -> str:
    for c in bundle.get("containers", []):
        if c.get("reason"):
            return c["reason"]
    return bundle.get("phase", "Unknown")


def _restarts_of(bundle: dict) -> int:
    return max((c.get("restarts", 0) for c in bundle.get("containers", [])), default=0)


def _healthy(bundle: dict) -> bool:
    phase = bundle.get("phase")
    reason = _reason_of(bundle)
    ready = all(c.get("ready") for c in bundle.get("containers", [])) if bundle.get("containers") else False
    bad = {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "OOMKilled",
           "Error", "CreateContainerConfigError", "RunContainerError"}
    return phase == "Running" and ready and reason not in bad


def _summ(bundle: dict) -> dict:
    return {
        "namespace": bundle["namespace"], "name": bundle["name"],
        "phase": bundle.get("phase", "Unknown"),
        "reason": _reason_of(bundle),
        "restarts": _restarts_of(bundle),
        "ready": all(c.get("ready") for c in bundle.get("containers", [])) if bundle.get("containers") else False,
        "node": bundle.get("node", "-"),
        "healthy": _healthy(bundle),
    }


def _summ_live(pod) -> dict:
    css = pod.status.container_statuses or []
    reason = pod.status.phase
    for cs in css:
        if cs.state.waiting and cs.state.waiting.reason:
            reason = cs.state.waiting.reason
        elif cs.state.terminated and cs.state.terminated.reason:
            reason = cs.state.terminated.reason
    b = {
        "namespace": pod.metadata.namespace, "name": pod.metadata.name,
        "phase": pod.status.phase, "reason": reason,
        "restarts": max((c.restart_count for c in css), default=0),
        "ready": all(c.ready for c in css) if css else False,
        "node": pod.spec.node_name or "-",
    }
    b["healthy"] = (b["phase"] == "Running" and b["ready"]
                    and reason not in {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull",
                                       "OOMKilled", "Error", "CreateContainerConfigError"})
    return b


# --------------------------------------------------------------------------- #
#  MOCK CLUSTER — a teaching zoo of classic Kubernetes failures
# --------------------------------------------------------------------------- #
_MOCK_PODS = [
    {   # 1 · CrashLoopBackOff — app exits on boot (bad config / missing env)
        "namespace": "shop", "name": "checkout-7d9f6c5b8b-x4k2p", "phase": "Running",
        "node": "ip-10-0-1-23", "deployment": "checkout",
        "containers": [{"container": "checkout", "ready": False, "restarts": 14,
                        "reason": "CrashLoopBackOff",
                        "detail": "back-off 5m0s restarting failed container"}],
        "events": [
            "Scheduled: Successfully assigned shop/checkout to ip-10-0-1-23",
            "Pulled: Container image \"checkout:2.3.1\" already present on machine",
            "Created: Created container checkout",
            "Started: Started container checkout",
            "BackOff: Back-off restarting failed container checkout",
        ],
        "logs": ("Starting checkout service v2.3.1\n"
                 "Reading config from $DATABASE_URL\n"
                 "panic: DATABASE_URL is empty — cannot connect to Postgres\n"
                 "goroutine 1 [running]: main.main() /app/main.go:41\n"
                 "exit status 2\n"),
    },
    {   # 2 · ImagePullBackOff — wrong tag / registry auth
        "namespace": "shop", "name": "recommender-6b4c8d7f9-tt8vq", "phase": "Pending",
        "node": "ip-10-0-1-23", "deployment": "recommender",
        "containers": [{"container": "recommender", "ready": False, "restarts": 0,
                        "reason": "ImagePullBackOff",
                        "detail": "Back-off pulling image \"recommender:v9.9.9\""}],
        "events": [
            "Scheduled: Successfully assigned shop/recommender to ip-10-0-1-23",
            "Pulling: Pulling image \"recommender:v9.9.9\"",
            "Failed: Failed to pull image \"recommender:v9.9.9\": manifest unknown: tag does not exist",
            "Failed: Error: ErrImagePull",
            "BackOff: Back-off pulling image \"recommender:v9.9.9\"",
        ],
        "logs": "(no logs — container never started)\n",
    },
    {   # 3 · OOMKilled — memory limit too low
        "namespace": "shop", "name": "image-resizer-5f7b9c-2m9lk", "phase": "Running",
        "node": "ip-10-0-1-77", "deployment": "image-resizer",
        "containers": [{"container": "resizer", "ready": False, "restarts": 6,
                        "reason": "OOMKilled",
                        "detail": "terminated: exit code 137 (out of memory)"}],
        "events": [
            "Scheduled: Successfully assigned shop/image-resizer to ip-10-0-1-77",
            "Started: Started container resizer",
            "Killing: Container resizer exceeded memory limit (128Mi)",
            "OOMKilling: Memory cgroup out of memory: Killed process resizer",
        ],
        "logs": ("Resizing batch of 512 images...\n"
                 "Loaded 480MB into memory buffer\n"
                 "Killed\n"),
    },
    {   # 4 · Pending / Unschedulable — no node has room
        "namespace": "shop", "name": "batch-nightly-9c8d-qq77z", "phase": "Pending",
        "node": None, "deployment": "batch-nightly",
        "containers": [{"container": "batch", "ready": False, "restarts": 0,
                        "reason": "Unschedulable",
                        "detail": "0/3 nodes are available: insufficient cpu"}],
        "events": [
            "FailedScheduling: 0/3 nodes are available: 3 Insufficient cpu.",
            "FailedScheduling: 0/3 nodes are available: 3 Insufficient cpu.",
        ],
        "logs": "(no logs — pod is unscheduled)\n",
    },
    {   # 5 · Healthy — the control group
        "namespace": "shop", "name": "frontend-84b5d7c9f-abc12", "phase": "Running",
        "node": "ip-10-0-1-23", "deployment": "frontend",
        "containers": [{"container": "frontend", "ready": True, "restarts": 0,
                        "reason": None, "detail": None}],
        "events": ["Started: Started container frontend"],
        "logs": "Listening on :8080\nHealth check OK\n",
    },
    {   # 6 · Readiness probe failing — up but never Ready
        "namespace": "platform", "name": "payments-api-79f6b-kk3ww", "phase": "Running",
        "node": "ip-10-0-1-77", "deployment": "payments-api",
        "containers": [{"container": "api", "ready": False, "restarts": 0,
                        "reason": "Unhealthy",
                        "detail": "Readiness probe failed: HTTP 503 on /ready"}],
        "events": [
            "Started: Started container api",
            "Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 503",
            "Unhealthy: Readiness probe failed: HTTP probe failed with statuscode: 503",
        ],
        "logs": ("payments-api starting\n"
                 "waiting for upstream ledger service at ledger:9000 ...\n"
                 "ledger not reachable — /ready returns 503\n"),
    },
    {   # 7 · Healthy
        "namespace": "platform", "name": "ledger-6d9c8b-zz00y", "phase": "Running",
        "node": "ip-10-0-1-77", "deployment": "ledger",
        "containers": [{"container": "ledger", "ready": True, "restarts": 0,
                        "reason": None, "detail": None}],
        "events": ["Started: Started container ledger"],
        "logs": "ledger ready on :9000\n",
    },
    {   # 8 · CreateContainerConfigError — missing Secret/ConfigMap
        "namespace": "platform", "name": "notifier-5b7c9d-ll55x", "phase": "Pending",
        "node": "ip-10-0-1-23", "deployment": "notifier",
        "containers": [{"container": "notifier", "ready": False, "restarts": 0,
                        "reason": "CreateContainerConfigError",
                        "detail": "secret \"smtp-credentials\" not found"}],
        "events": [
            "Scheduled: Successfully assigned platform/notifier to ip-10-0-1-23",
            "Failed: Error: secret \"smtp-credentials\" not found",
        ],
        "logs": "(no logs — container config could not be created)\n",
    },
]

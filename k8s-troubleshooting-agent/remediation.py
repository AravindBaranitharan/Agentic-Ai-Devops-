"""
Remediation — the ONLY place this project can change a cluster, and every path is
guarded:

  • Nothing runs without an explicit human approval in the UI.
  • DRY-RUN is the default. A real action runs only when execute=True AND a live
    cluster is enabled (USE_REAL_K8S=true).
  • The action set is a tiny, safe allow-list (restart / scale / delete-pod). There is
    no "run arbitrary kubectl" path.

In mock mode every action is simulated so the demo is safe to click through.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")
except ImportError:
    pass

from k8s_tools import _real_enabled


# risk shown next to each action in the UI
RISK = {
    "restart_deployment": "medium",   # rolling restart — brief churn, self-heals
    "scale_deployment":   "medium",
    "delete_pod":         "low",      # controller recreates it
    "manual":             "n/a",
}

HUMAN = {
    "restart_deployment": "Roll-restart the deployment (kubectl rollout restart)",
    "scale_deployment":   "Scale the deployment to N replicas",
    "delete_pod":         "Delete the pod so its controller recreates it",
    "manual":             "Manual fix required — no safe automated action",
}


def _apps():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.AppsV1Api()


def _core():
    from kubernetes import client, config
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api()


def run_action(action: str, namespace: str, target: str,
               execute: bool = False, replicas: int = 2) -> dict:
    """
    Perform a remediation.  execute=False  → dry run (nothing touched).
                            execute=True   → real action, but only on a live cluster.
    Returns {ok, mode, message}.
    """
    if action == "manual" or action not in RISK:
        return {"ok": False, "mode": "n/a",
                "message": "No safe automated action for this issue — remediate manually."}

    plan = {
        "restart_deployment": f"kubectl -n {namespace} rollout restart deploy/{target}",
        "scale_deployment":   f"kubectl -n {namespace} scale deploy/{target} --replicas={replicas}",
        "delete_pod":         f"kubectl -n {namespace} delete pod {target}",
    }[action]

    if not execute:
        return {"ok": True, "mode": "DRY-RUN",
                "message": f"Approved (dry-run). Would run:\n  {plan}\n"
                           f"Enable 'Execute for real' + a live cluster to apply."}

    if not _real_enabled():
        return {"ok": True, "mode": "SIMULATED",
                "message": f"No live cluster attached — simulated:\n  {plan}\n"
                           f"(Set USE_REAL_K8S=true with a kubeconfig to run it for real.)"}

    # ---- real, live actions (read the allow-list above) ----
    try:
        import time
        if action == "restart_deployment":
            api = _apps()
            body = {"spec": {"template": {"metadata": {"annotations":
                    {"kubectl.kubernetes.io/restartedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ")}}}}}
            api.patch_namespaced_deployment(target, namespace, body)
            msg = f"Rolled restart of deploy/{target} in {namespace}."
        elif action == "scale_deployment":
            api = _apps()
            api.patch_namespaced_deployment_scale(
                target, namespace, {"spec": {"replicas": int(replicas)}})
            msg = f"Scaled deploy/{target} to {replicas} replicas in {namespace}."
        elif action == "delete_pod":
            _core().delete_namespaced_pod(target, namespace)
            msg = f"Deleted pod {target} in {namespace}; its controller will recreate it."
        else:
            return {"ok": False, "mode": "n/a", "message": "Unknown action."}
        return {"ok": True, "mode": "APPLIED", "message": msg}
    except Exception as e:
        return {"ok": False, "mode": "ERROR", "message": f"Action failed: {e}"}

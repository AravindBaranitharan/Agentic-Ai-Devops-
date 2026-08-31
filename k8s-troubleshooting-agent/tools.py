"""
LangChain tools the agent calls to INVESTIGATE a cluster.

These are thin, read-only wrappers over k8s_tools — the same functions a human runs
as `kubectl get / describe / logs`. The LangGraph agent decides which to call and in
what order; nothing here mutates the cluster.
"""

import json
from langchain_core.tools import tool

import k8s_tools as k8s


@tool
def list_namespaces() -> str:
    """List the namespaces in the cluster."""
    return json.dumps(k8s.list_namespaces())


@tool
def list_unhealthy_pods(namespace: str) -> str:
    """List the UNHEALTHY pods in a namespace (name, phase, reason, restarts, node)."""
    pods = k8s.unhealthy_pods(namespace)
    return json.dumps(pods, indent=2) if pods else "No unhealthy pods in this namespace."


@tool
def describe_pod(namespace: str, pod: str) -> str:
    """Describe one pod: phase, container states + reasons, and recent Events
    (the equivalent of `kubectl describe pod`)."""
    b = k8s.get_pod_bundle(namespace, pod)
    view = {
        "name": b.get("name"), "namespace": b.get("namespace"),
        "phase": b.get("phase"), "node": b.get("node"),
        "containers": b.get("containers"),
        "events": b.get("events"),
        "error": b.get("error"),
    }
    return json.dumps(view, indent=2)


@tool
def get_pod_logs(namespace: str, pod: str) -> str:
    """Return the recent log tail for a pod (the equivalent of `kubectl logs`)."""
    b = k8s.get_pod_bundle(namespace, pod)
    return b.get("logs") or "(no logs available)"


# the toolbox the investigation agent is given
INVESTIGATION_TOOLS = [list_namespaces, list_unhealthy_pods, describe_pod, get_pod_logs]

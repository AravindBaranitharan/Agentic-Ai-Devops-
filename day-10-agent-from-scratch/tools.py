"""
Day 10 · Step 1 — Define the tools (the agent's "hands").

A tool is just a Python function PLUS a JSON schema the model reads to decide
when and how to call it. The `description` field is effectively prompt text —
write it as carefully as a prompt.

For class we MOCK the cluster: the functions return realistic canned data, so the
agent runs end-to-end without a real Kubernetes cluster or credentials. In
Module 3 we swap these bodies for real `kubectl` / client-go / API calls — the
schemas and the agent loop do not change.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Mocked cluster state — a `checkout` pod that is CrashLoopBackOff / OOMKilled.
# ─────────────────────────────────────────────────────────────────────────────
_PODS = {
    "shop": (
        "NAME              READY   STATUS             RESTARTS   AGE\n"
        "checkout-7f9c8    0/1     CrashLoopBackOff   8          22m\n"
        "cart-5d4b2        1/1     Running            0          5h\n"
        "payments-9a1c7    1/1     Running            0          5h\n"
        "frontend-66ef0    2/2     Running            1          5h"
    ),
}

_LOGS = {
    ("checkout-7f9c8", "shop"): (
        "2024-06-21T09:14:02Z INFO  starting checkout-service v2.3.1\n"
        "2024-06-21T09:14:03Z INFO  connected to payments at payments:8443\n"
        "2024-06-21T09:14:09Z WARN  cart payload large: 18,442 items in session\n"
        "2024-06-21T09:14:10Z INFO  building order summary (in-memory)\n"
        "2024-06-21T09:14:11Z ERROR java.lang.OutOfMemoryError: Java heap space\n"
        "2024-06-21T09:14:11Z FATAL container exceeded memory limit (256Mi)\n"
        "--- last state: terminated, reason: OOMKilled, exit code: 137 ---"
    ),
}


def get_pods(namespace: str) -> str:
    """List the pods and their status in a Kubernetes namespace."""
    return _PODS.get(
        namespace,
        f"No pods found in namespace '{namespace}'.",
    )


def get_pod_logs(pod: str, namespace: str = "shop", tail: int = 20) -> str:
    """Return the last `tail` log lines for a pod (mocked)."""
    logs = _LOGS.get((pod, namespace))
    if logs is None:
        return f"No logs found for pod '{pod}' in namespace '{namespace}'."
    lines = logs.splitlines()
    return "\n".join(lines[-tail:])


# ─────────────────────────────────────────────────────────────────────────────
# Tool SCHEMAS — exactly what we pass to the model as `tools=[...]`.
# OpenAI's format wraps each tool as {"type": "function", "function": {...}} where
# `parameters` is a standard JSON Schema. The model never sees the Python; it only
# reads these descriptions + argument shapes to decide what to call.
# ─────────────────────────────────────────────────────────────────────────────
GET_PODS = {
    "type": "function",
    "function": {
        "name": "get_pods",
        "description": "List pods and their status (READY/STATUS/RESTARTS) in a "
                       "Kubernetes namespace. Use this first to find unhealthy pods.",
        "parameters": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "K8s namespace, e.g. 'shop'"},
            },
            "required": ["namespace"],
        },
    },
}

GET_POD_LOGS = {
    "type": "function",
    "function": {
        "name": "get_pod_logs",
        "description": "Fetch the most recent log lines for a specific pod. Use this "
                       "after get_pods to understand WHY a pod is failing.",
        "parameters": {
            "type": "object",
            "properties": {
                "pod": {"type": "string", "description": "Exact pod name from get_pods"},
                "namespace": {"type": "string", "description": "K8s namespace"},
                "tail": {"type": "integer", "description": "How many log lines (default 20)"},
            },
            "required": ["pod"],
        },
    },
}

# What we hand the model, and how we route a tool_call back to real code.
TOOLS = [GET_PODS, GET_POD_LOGS]
REGISTRY = {
    "get_pods": get_pods,
    "get_pod_logs": get_pod_logs,
}

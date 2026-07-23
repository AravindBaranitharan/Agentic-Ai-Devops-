# Sample session — `python agent.py`

A full run of the from-scratch agent diagnosing the mocked incident. The agent
chose the path on its own: list pods → spot the crashing pod → read its logs →
conclude. Two tool calls, zero hand-holding.

```text
● OFFLINE mode — no OPENAI_API_KEY found, using a scripted model.
  (Set OPENAI_API_KEY in code/.env for a real run.)

USER  ▸ Why is the checkout pod crashing and how do I fix it?

AGENT ▸ I'll start by listing the pods to find the unhealthy one.
      ▸ tool_call: get_pods({'namespace': 'shop'})
TOOL  ◂ NAME              READY   STATUS             RESTARTS   AGE
AGENT ▸ checkout-7f9c8 is CrashLoopBackOff — let me read its logs.
      ▸ tool_call: get_pod_logs({'pod': 'checkout-7f9c8', 'namespace': 'shop', 'tail': 20})
TOOL  ◂ 2024-06-21T09:14:02Z INFO  starting checkout-service v2.3.1
AGENT ▸ Root cause: the checkout container is OOMKilled (exit 137) — it exceeds its
        256Mi memory limit when a large cart session builds the order summary in memory.
        Fix: raise resources.limits.memory to 512Mi (and/or stream the summary to avoid
        loading all items at once), then redeploy and watch restarts settle to 0.

✓ Done in 3 step(s).
```

## What to point out in class

- The loop ran **3 iterations**: the first two messages came back with `tool_calls`
  (so we ran the tool and appended a `role: "tool"` result), the third had no
  `tool_calls` → that's the exit condition.
- The agent **decided** to call `get_pod_logs` only after seeing `CrashLoopBackOff`
  in the first observation — that branch was not coded by us, the model chose it.
- In **LIVE mode** the wording will vary run-to-run (it's a real model), but the
  control flow — call → tool_calls → tool result → repeat → answer — is identical.
- Swap the mocked tool bodies in `tools.py` for real `kubectl` calls and this same
  agent works against a real cluster. The loop never changes.

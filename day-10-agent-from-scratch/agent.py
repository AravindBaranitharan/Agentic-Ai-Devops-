"""
Day 10 · Capstone — a tool-using agent built FROM SCRATCH (no framework).

This is the whole agent architecture from Hours 5–6, in plain Python:

    Model  +  Tools  +  Memory  +  Orchestration loop

Run it:
    python agent.py

  • With OPENAI_API_KEY set (rename env.sample → .env in this folder)  → LIVE mode: real gpt-4o drives the loop.
  • Without a key                           → OFFLINE mode: a scripted "model" walks
                                              the EXACT same loop with canned decisions,
                                              so you can demo the mechanics anywhere.

The tools are mocked (see tools.py), so either mode runs without a real cluster.
"""

import os
import json
from pathlib import Path

from tools import TOOLS, REGISTRY  # Step 1 (tools) + the name→fn registry

# ── Step 5 · Secrets/config: load the key from THIS folder ─────────────────
# Students: rename `env.sample` → `.env` (or just `env`) and paste your key.
# Both names are accepted below, so either rename works.
try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")   # preferred name
    load_dotenv(_here / "env")    # also accepted
except ImportError:
    pass  # python-dotenv optional; env vars may already be exported

MODEL = os.getenv("MODEL", "gpt-4o")
MAX_STEPS = 6  # hardening: the loop can NEVER run forever

SYSTEM = (
    "You are a Kubernetes diagnostics agent. Investigate incidents using the "
    "provided read-only tools. Work step by step: inspect pods, then read logs of "
    "any failing pod, then give a concise root cause and a concrete fix. "
    "Only state conclusions supported by tool output."
)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 · Registry & dispatch — route a tool_call to real Python code.
# Errors are returned as results (so the agent can recover) — never raised.
# ─────────────────────────────────────────────────────────────────────────────
def run_tool(name: str, args: dict) -> str:
    fn = REGISTRY.get(name)
    if fn is None:
        return f"ERROR: unknown tool '{name}'"
    try:
        return fn(**args)
    except Exception as e:  # tool failures become observations, not crashes
        return f"ERROR running {name}: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 · The agent loop — the entire orchestration engine.
# `create` is a callable(messages) -> message, so the SAME loop drives both the
# real OpenAI SDK and the offline scripted model. An OpenAI assistant message has
# `.content` (str | None) and `.tool_calls` (list | None).
# ─────────────────────────────────────────────────────────────────────────────
def run_agent(task: str, create) -> str:
    # Step 3 · memory — the running transcript we resend each turn.
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    print(f"USER  ▸ {task}\n")

    for step in range(1, MAX_STEPS + 1):
        msg = create(messages)

        if msg.content:
            print(f"AGENT ▸ {msg.content}")

        # No tool requested → the agent is done.
        if not msg.tool_calls:
            print(f"\n✓ Done in {step} step(s).")
            return msg.content or ""

        # Record the assistant turn (must include tool_calls before tool results).
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        # Run every requested tool, append one tool message per call, loop again.
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            print(f"      ▸ tool_call: {tc.function.name}({args})")
            out = run_tool(tc.function.name, args)
            first_line = str(out).splitlines()[0] if out else ""
            print(f"TOOL  ◂ {first_line}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})

    print("\n⚠ Hit MAX_STEPS — stopping (loop is bounded by design).")
    return "Stopped: reached MAX_STEPS without a final answer."


# ─────────────────────────────────────────────────────────────────────────────
# LIVE mode — real gpt-4o via the official OpenAI SDK.
# ─────────────────────────────────────────────────────────────────────────────
def live_create():
    from openai import OpenAI
    client = OpenAI()  # reads OPENAI_API_KEY from the environment

    def create(messages):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0,
        )
        return resp.choices[0].message
    return create


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE mode — a scripted "model" with the same .content / .tool_calls shape as
# an OpenAI message, so run_agent() drives it identically. Great for teaching the
# mechanics with no key.
# ─────────────────────────────────────────────────────────────────────────────
class _Fn:
    def __init__(self, name, arguments): self.name, self.arguments = name, arguments

class _ToolCall:
    type = "function"
    def __init__(self, id, name, arguments): self.id, self.function = id, _Fn(name, arguments)

class _Msg:
    def __init__(self, content, tool_calls=None): self.content, self.tool_calls = content, tool_calls


def scripted_create():
    """Returns a create(messages) callable that replays a canned diagnosis."""
    script = [
        _Msg("I'll start by listing the pods to find the unhealthy one.",
             [_ToolCall("t1", "get_pods", json.dumps({"namespace": "shop"}))]),
        _Msg("checkout-7f9c8 is CrashLoopBackOff — let me read its logs.",
             [_ToolCall("t2", "get_pod_logs",
                        json.dumps({"pod": "checkout-7f9c8", "namespace": "shop", "tail": 20}))]),
        _Msg(
            "Root cause: the checkout container is OOMKilled (exit 137) — it exceeds its "
            "256Mi memory limit when a large cart session builds the order summary in memory.\n"
            "Fix: raise resources.limits.memory to 512Mi (and/or stream the summary to avoid "
            "loading all items at once), then redeploy and watch restarts settle to 0."),
    ]
    state = {"i": 0}

    def create(messages):
        msg = script[min(state["i"], len(script) - 1)]
        state["i"] += 1
        return msg
    return create


def main():
    task = "Why is the checkout pod crashing and how do I fix it?"
    if os.getenv("OPENAI_API_KEY"):
        print("● LIVE mode — real gpt-4o is driving the loop.\n")
        create = live_create()
    else:
        print("● OFFLINE mode — no OPENAI_API_KEY found, using a scripted model.")
        print("  (Rename env.sample → .env and paste your OPENAI_API_KEY for a real run.)\n")
        create = scripted_create()

    run_agent(task, create)


if __name__ == "__main__":
    main()

"""
LangChain · 02 — Tools + an agent.

A tool is a plain Python function decorated with @tool. `create_agent` gives the
model those tools and runs the loop: the model decides which tool to call, we run
it, feed the result back, and it answers. (LangChain 1.x agents API.)

Run:  python 02_tools_agent.py     (needs OPENAI_API_KEY)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langchain_core.tools import tool
from langchain.agents import create_agent

MODEL = os.getenv("MODEL", "gpt-4o")


@tool
def get_pod_status(namespace: str) -> str:
    """Return the status of pods in a Kubernetes namespace (mocked)."""
    data = {"prod": "api-7f9: CrashLoopBackOff (14 restarts); web-3c1: Running"}
    return data.get(namespace, f"(no pods in '{namespace}')")


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in ../.env to run this live."); raise SystemExit(0)

    agent = create_agent(
        "openai:" + MODEL,
        [get_pod_status, add],
        system_prompt="You are a helpful DevOps assistant. Use tools when needed; be concise.",
    )
    q = "What's the status of pods in the prod namespace, and what is 14 + 28?"
    print(f"USER ▸ {q}\n")
    out = agent.invoke({"messages": [{"role": "user", "content": q}]})

    # show the tool calls the model made, then the final answer
    for m in out["messages"]:
        calls = getattr(m, "tool_calls", None)
        if calls:
            for c in calls:
                print(f"  ↳ tool_call: {c['name']}({c['args']})")
    print(f"\nAGENT ▸ {out['messages'][-1].content}")

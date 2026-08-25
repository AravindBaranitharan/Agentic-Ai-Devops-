"""
LangGraph · 02 — The agent LOOP (the thing chains can't do cleanly).

A cyclic graph: the model can call tools, see the results, and decide to call MORE
tools — looping until it's done. This is a ReAct agent expressed as a graph:

        START → agent → (tool calls?) ──yes──▶ tools ──┐
                  ▲                                     │
                  └─────────────────────────────────────┘
                        │no
                        ▼
                       END

`tools_condition` is the conditional edge that routes agent → tools or → END.

Run:  python 02_agent_loop.py     (needs OPENAI_API_KEY)
"""

import os
from typing import Annotated, TypedDict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

MODEL = os.getenv("MODEL", "gpt-4o")


@tool
def get_pods(namespace: str) -> str:
    """List pods and their status in a Kubernetes namespace."""
    return "api-7f9: CrashLoopBackOff (14 restarts); web-3c1: Running" if namespace == "prod" \
        else f"(no pods in '{namespace}')"


@tool
def get_pod_logs(pod: str) -> str:
    """Return the most recent logs for a single pod."""
    return {"api-7f9": "exit code 137 · OOMKilled · memory limit 256Mi exceeded"}.get(
        pod, f"(no logs for '{pod}')")


tools = [get_pods, get_pod_logs]


def build_app():
    llm = ChatOpenAI(model=MODEL, temperature=0).bind_tools(tools)

    class State(TypedDict):
        messages: Annotated[list, add_messages]   # add_messages appends, not overwrites

    def agent(state: State):
        return {"messages": [llm.invoke(state["messages"])]}

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition)   # → "tools" if tool calls, else END
    g.add_edge("tools", "agent")                        # loop back after running tools
    return g.compile()


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY in ../.env to run this live."); raise SystemExit(0)

    app = build_app()
    q = "Why is the api pod in the prod namespace crashing? Investigate and give the root cause + fix."
    print(f"USER ▸ {q}\n")

    # stream node-by-node so you can SEE the loop turn
    for update in app.stream({"messages": [{"role": "user", "content": q}]}, stream_mode="updates"):
        for node, data in update.items():
            msg = data["messages"][-1]
            if getattr(msg, "tool_calls", None):
                for c in msg.tool_calls:
                    print(f"  [agent] → call {c['name']}({c['args']})")
            elif node == "tools":
                print(f"  [tools] ◂ {msg.content[:70]}")
            elif msg.content:
                print(f"\nAGENT ▸ {msg.content}")

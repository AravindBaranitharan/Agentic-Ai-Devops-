"""
LangGraph · 03 — Human-in-the-loop (pause the graph, wait for a person).

LangGraph can PAUSE mid-run at an `interrupt(...)`, persist its state via a
checkpointer, and RESUME later with the human's decision. This is how you build a
safe "propose → approve → act" workflow (exactly the FinOps approval pattern).

No LLM here — it runs offline so the mechanic is crystal clear.

Run:  python 03_human_in_the_loop.py
"""

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command


class State(TypedDict):
    resource: str
    savings: float
    approved: bool
    result: str


def propose(state: State):
    # a cost-saving recommendation
    return {"resource": "eipalloc-059 (unassociated Elastic IP)", "savings": 3.60}


def review(state: State):
    # PAUSE here — hand control to a human. The payload is what the UI would show.
    decision = interrupt({
        "resource": state["resource"],
        "savings": state["savings"],
        "question": "Approve releasing this Elastic IP?",
    })
    return {"approved": str(decision).lower().startswith("a")}   # "approve" -> True


def act(state: State):
    if state["approved"]:
        return {"result": f"✅ Released {state['resource']} — ${state['savings']:.2f}/mo saved."}
    return {"result": "🚫 Denied — nothing was changed."}


g = StateGraph(State)
g.add_node("propose", propose)
g.add_node("review", review)
g.add_node("act", act)
g.add_edge(START, "propose")
g.add_edge("propose", "review")
g.add_edge("review", "act")
g.add_edge("act", END)

# a checkpointer is REQUIRED for interrupts (it saves state while paused)
app = g.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    cfg = {"configurable": {"thread_id": "approval-demo"}}

    # 1) run until the interrupt
    paused = app.invoke({"resource": "", "savings": 0.0, "approved": False, "result": ""}, cfg)
    intr = paused["__interrupt__"][0]
    print("⏸  PAUSED — waiting for a human")
    print("   payload:", intr.value)

    # 2) a human decides → resume the SAME thread with their answer
    print("\n👤 human types: approve\n")
    final = app.invoke(Command(resume="approve"), cfg)
    print("RESULT ▸", final["result"])

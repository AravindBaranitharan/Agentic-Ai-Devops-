"""
Kubernetes Troubleshooting Agent — LangGraph orchestration.

This is the brain, built as an explicit LangGraph state machine (not a single LLM call):

    investigate  ⇄  tools          the agent calls read-only k8s tools (describe/logs)
        │                           in a ReAct loop until it has enough evidence
        ▼
    diagnose                        LLM → STRUCTURED diagnosis (root cause, evidence, fix, action)
        │
        ├─ action == manual ──────► END           (nothing safe to automate)
        ▼
    approval_gate  ── interrupt() ─►  (human decides in the UI)  ──► remediate ──► END

Human-in-the-loop is real LangGraph: the graph PAUSES at `interrupt()` with a checkpointer,
and the app resumes it with Command(resume=<decision>). The LLM only ever reads and reasons;
the single mutating step (remediate) runs only after an explicit human approval.
"""

import json
import os
from pathlib import Path
from typing import Annotated, Optional, TypedDict

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")
    load_dotenv(_here / "env")
except ImportError:
    pass

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from tools import INVESTIGATION_TOOLS
import remediation

MODEL = os.getenv("MODEL", "gpt-4o")


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


# --------------------------------------------------------------------------- #
#  Structured diagnosis (the graph's typed output)
# --------------------------------------------------------------------------- #
class Diagnosis(BaseModel):
    reason: str = Field(description="k8s failure class, e.g. CrashLoopBackOff, OOMKilled, "
                                    "ImagePullBackOff, Unschedulable, Unhealthy, "
                                    "CreateContainerConfigError, or Healthy")
    root_cause: str = Field(description="1-2 sentences, plain English, the ACTUAL cause")
    evidence: str = Field(description="the exact event/log line(s) that prove it")
    fix: str = Field(description="concrete remediation steps in plain English")
    command: str = Field(description="ONE suggested kubectl command to remediate")
    action: str = Field(description="one of: restart_deployment, scale_deployment, "
                                    "delete_pod, manual")
    target: str = Field(description="the deployment name (for restart/scale) or pod name "
                                    "(for delete_pod)")


# --------------------------------------------------------------------------- #
#  Graph state
# --------------------------------------------------------------------------- #
class State(TypedDict):
    messages: Annotated[list, add_messages]
    namespace: str
    pod: str
    diagnosis: Optional[dict]
    decision: Optional[dict]     # {"approved": bool, "execute": bool, "replicas": int}
    result: Optional[dict]       # remediation outcome


_INVESTIGATE_SYS = (
    "You are an expert Kubernetes SRE agent. You are troubleshooting ONE pod. "
    "Use the available tools to gather evidence: describe the pod (status, container "
    "states, events) and read its logs. Call tools until you understand the failure. "
    "When you have enough evidence, STOP calling tools and reply with a one-line summary — "
    "a structured diagnosis is produced in the next step."
)

_DIAGNOSE_SYS = (
    "Based on the investigation so far, produce the structured diagnosis. Base every field "
    "strictly on the evidence gathered — do not invent resources. For `action`, choose "
    "'restart_deployment' ONLY when a rollout restart genuinely fixes the issue; if the fix "
    "needs a config/image/resource change or manual step, choose 'manual'. `target` is the "
    "deployment name for restart/scale, or the pod name for delete_pod."
)


def _llm(temperature: float = 0):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=MODEL, temperature=temperature)


# --------------------------------------------------------------------------- #
#  Nodes
# --------------------------------------------------------------------------- #
def investigate(state: State) -> dict:
    """ReAct step: the LLM (with tools bound) decides what to look at next."""
    llm = _llm().bind_tools(INVESTIGATION_TOOLS)
    msgs = state["messages"]
    if not msgs:
        msgs = [
            SystemMessage(_INVESTIGATE_SYS),
            HumanMessage(f"Troubleshoot pod '{state['pod']}' in namespace "
                         f"'{state['namespace']}'. Investigate and find the root cause."),
        ]
    return {"messages": msgs + [llm.invoke(msgs)]}


def diagnose(state: State) -> dict:
    """Turn the gathered evidence into a STRUCTURED diagnosis."""
    llm = _llm().with_structured_output(Diagnosis)
    convo = state["messages"] + [HumanMessage(_DIAGNOSE_SYS)]
    d: Diagnosis = llm.invoke(convo)
    data = d.model_dump()
    if data["action"] not in ("restart_deployment", "scale_deployment", "delete_pod", "manual"):
        data["action"] = "manual"
    data["source"] = f"LangGraph agent · {MODEL}"
    return {"diagnosis": data}


def approval_gate(state: State) -> dict:
    """Human-in-the-loop: PAUSE and wait for a decision from the UI."""
    d = state["diagnosis"]
    decision = interrupt({
        "type": "remediation_approval",
        "pod": state["pod"], "namespace": state["namespace"],
        "reason": d["reason"], "action": d["action"], "target": d["target"],
        "proposed": remediation.HUMAN.get(d["action"], d["action"]),
        "risk": remediation.RISK.get(d["action"], "n/a"),
    })
    return {"decision": decision}


def remediate(state: State) -> dict:
    """The single mutating step — runs ONLY after human approval."""
    d, dec = state["diagnosis"], (state.get("decision") or {})
    if not dec.get("approved"):
        return {"result": {"ok": False, "mode": "REJECTED",
                           "message": "Human rejected the remediation."}}
    r = remediation.run_action(
        d["action"], state["namespace"], d["target"],
        execute=bool(dec.get("execute", False)),
        replicas=int(dec.get("replicas", 2)),
    )
    return {"result": r}


# --------------------------------------------------------------------------- #
#  Routing
# --------------------------------------------------------------------------- #
def after_diagnose(state: State) -> str:
    return END if state["diagnosis"]["action"] == "manual" else "approval_gate"


def build_graph():
    g = StateGraph(State)
    g.add_node("investigate", investigate)
    g.add_node("tools", ToolNode(INVESTIGATION_TOOLS))
    g.add_node("diagnose", diagnose)
    g.add_node("approval_gate", approval_gate)
    g.add_node("remediate", remediate)

    g.add_edge(START, "investigate")
    # investigate loops through tools until the LLM stops calling them
    g.add_conditional_edges("investigate", tools_condition, {"tools": "tools", END: "diagnose"})
    g.add_edge("tools", "investigate")
    g.add_conditional_edges("diagnose", after_diagnose, {"approval_gate": "approval_gate", END: END})
    g.add_edge("approval_gate", "remediate")
    g.add_edge("remediate", END)

    return g.compile(checkpointer=MemorySaver())


GRAPH = build_graph()

"""
CI/CD Build-Failure Triage Agent — LangGraph orchestration.

An explicit state machine (not a single LLM call):

    investigate ⇄ tools        the agent reads the failed run's jobs + REAL logs
        │                        in a ReAct loop until it understands the failure
        ▼
    diagnose                    LLM → STRUCTURED triage (category, root cause, evidence, fix)
        │
        ▼
    approval_gate ─ interrupt() ─►  (human approves in the UI)  ──► post ──► END

Human-in-the-loop is real LangGraph: the graph PAUSES at `interrupt()` (with a
checkpointer) and the app resumes it with Command(resume=<decision>). The LLM only reads
and reasons; the one write (a triage comment on the commit) runs only after approval.
"""

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
import poster

MODEL = os.getenv("MODEL", "gpt-4o")


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


# --------------------------------------------------------------------------- #
#  Structured triage (the graph's typed output)
# --------------------------------------------------------------------------- #
class Triage(BaseModel):
    category: str = Field(description="failure class: test_failure, dependency, "
                                      "compile_error, lint, timeout, infrastructure, "
                                      "flaky_test, oom, or config")
    failing_job: str = Field(description="the job that failed")
    failing_step: str = Field(description="the step within the job that failed")
    root_cause: str = Field(description="1-3 sentences, plain English, the ACTUAL cause")
    evidence: str = Field(description="the exact log line(s) that prove it")
    fix: str = Field(description="concrete, specific fix — file/line/command where possible")
    confidence: str = Field(description="High, Medium, or Low")


class State(TypedDict):
    messages: Annotated[list, add_messages]
    run: dict
    diagnosis: Optional[dict]
    decision: Optional[dict]     # {"approved": bool, "execute": bool}
    result: Optional[dict]


_INVESTIGATE_SYS = (
    "You are an expert CI/CD build engineer triaging a FAILED GitHub Actions run. "
    "Use the tools to investigate: list the jobs for the run, find which job/step failed, "
    "and read that job's real logs. Call tools until you understand the true root cause. "
    "When you have enough evidence, STOP calling tools and give a one-line summary — the "
    "structured triage is produced in the next step. Never guess; base everything on the logs."
)

_DIAGNOSE_SYS = (
    "Based on the investigation, produce the structured triage. Base every field strictly on "
    "the real log evidence — do not invent. The `fix` must be concrete and actionable "
    "(name the file/function/line or the exact command). `evidence` must quote the actual "
    "failing log line(s)."
)


def _llm(temperature: float = 0):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=MODEL, temperature=temperature)


# --------------------------------------------------------------------------- #
#  Nodes
# --------------------------------------------------------------------------- #
def investigate(state: State) -> dict:
    llm = _llm().bind_tools(INVESTIGATION_TOOLS)
    msgs = state["messages"]
    if not msgs:
        run = state["run"]
        msgs = [
            SystemMessage(_INVESTIGATE_SYS),
            HumanMessage(f"Triage failed run id={run['id']} — workflow '{run['name']}' "
                         f"on branch {run['branch']} (commit {run['sha']}). "
                         f"Investigate the jobs and logs and find the root cause."),
        ]
    return {"messages": msgs + [llm.invoke(msgs)]}


def diagnose(state: State) -> dict:
    llm = _llm().with_structured_output(Triage)
    convo = state["messages"] + [HumanMessage(_DIAGNOSE_SYS)]
    t: Triage = llm.invoke(convo)
    data = t.model_dump()
    data["source"] = f"LangGraph agent · {MODEL}"
    return {"diagnosis": data}


def approval_gate(state: State) -> dict:
    d = state["diagnosis"]
    decision = interrupt({
        "type": "post_triage_comment",
        "run": state["run"],
        "category": d["category"], "root_cause": d["root_cause"],
        "target": f"commit {state['run']['sha']}",
    })
    return {"decision": decision}


def post(state: State) -> dict:
    dec = state.get("decision") or {}
    if not dec.get("approved"):
        return {"result": {"ok": False, "mode": "REJECTED",
                           "message": "Human rejected posting the triage."}}
    return {"result": poster.post_triage(state["diagnosis"], state["run"],
                                         execute=bool(dec.get("execute", False)))}


def build_graph():
    g = StateGraph(State)
    g.add_node("investigate", investigate)
    g.add_node("tools", ToolNode(INVESTIGATION_TOOLS))
    g.add_node("diagnose", diagnose)
    g.add_node("approval_gate", approval_gate)
    g.add_node("post", post)

    g.add_edge(START, "investigate")
    g.add_conditional_edges("investigate", tools_condition, {"tools": "tools", END: "diagnose"})
    g.add_edge("tools", "investigate")
    g.add_edge("diagnose", "approval_gate")
    g.add_edge("approval_gate", "post")
    g.add_edge("post", END)

    return g.compile(checkpointer=MemorySaver())


GRAPH = build_graph()

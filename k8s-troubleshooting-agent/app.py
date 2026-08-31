"""
Kubernetes Troubleshooting Agent — Streamlit demo (LangGraph orchestration).

Point it at a namespace on a REAL cluster (or the built-in mock). Pick a broken pod and
the LangGraph agent investigates it live — calling read-only k8s tools in a ReAct loop —
then returns a structured root-cause diagnosis and proposes a fix. Any remediation pauses
the graph at a human-approval gate (LangGraph interrupt) before it runs.

Run:  streamlit run app.py
"""

import os
import uuid
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import k8s_tools as k8s
import remediation
from agent_graph import GRAPH, has_key, MODEL
from langgraph.types import Command

st.set_page_config(page_title="K8s Troubleshooting Agent", page_icon="🩺", layout="wide")
ss = st.session_state


def _trace(messages):
    """Pull the agent's tool calls out of the message history for a readable trace."""
    steps = []
    for m in messages:
        for tc in (getattr(m, "tool_calls", None) or []):
            steps.append(f"{tc['name']}({', '.join(f'{k}={v}' for k, v in tc['args'].items())})")
    return steps

st.title("🩺 Kubernetes Troubleshooting Agent")
st.caption("A LangGraph agent that investigates broken pods on a **live cluster**, finds the "
           "root cause, and proposes a fix — nothing is changed without your approval.")

live = k8s._real_enabled()
cluster = "🟢 LIVE cluster" if live else "🧪 mock (no cluster reachable)"
brain = "🟢 LangGraph · gpt-4o" if has_key() else "🟡 no OPENAI_API_KEY"
st.markdown(f"**Cluster:** {cluster} · `{k8s.cluster_context()}`  ·  **Agent:** {brain}")
if not live:
    st.info("No live cluster reached — showing the offline demo cluster. "
            "Run `live-cases/setup-cluster.sh` and set `USE_REAL_K8S=auto` to troubleshoot real pods.")
if not has_key():
    st.warning("Set `OPENAI_API_KEY` in `.env` — the LangGraph agent needs it to reason.")

# ── namespace + pod selection ─────────────────────────────────────────────
namespaces = k8s.list_namespaces()
c = st.columns([2, 1, 3])
ns = c[0].selectbox("Namespace", namespaces,
                    index=namespaces.index("shop") if "shop" in namespaces else 0)
only_bad = c[1].toggle("Only unhealthy", value=True)
if c[2].button("🔄 Refresh"):
    k8s._real_enabled(recheck=True)
    st.rerun()

pods = k8s.unhealthy_pods(ns) if only_bad else k8s.list_pods(ns)

st.subheader(f"Pods in `{ns}`")
if not pods:
    st.success("🎉 No unhealthy pods in this namespace.")
else:
    import pandas as pd
    st.dataframe(pd.DataFrame([{
        "": "❌" if not p["healthy"] else "✅",
        "pod": p["name"], "phase": p["phase"], "reason": p["reason"],
        "restarts": p["restarts"], "ready": p["ready"], "node": p["node"],
    } for p in pods]), use_container_width=True, hide_index=True)

    pick = st.selectbox("Troubleshoot which pod?", [p["name"] for p in pods])

    if st.button("🔎 Investigate & diagnose", type="primary"):
        ss.thread = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 25}
        with st.spinner("LangGraph agent investigating (describe → logs → reason)…"):
            state = GRAPH.invoke(
                {"namespace": ns, "pod": pick,
                 "diagnosis": None, "decision": None, "result": None},
                ss.thread)
        ss.diag = state.get("diagnosis")
        ss.trace = _trace(state.get("messages", []))
        ss.paused = ("__interrupt__" in state)
        ss.result = None

# ── diagnosis + human-gated remediation ───────────────────────────────────
if ss.get("diag"):
    d = ss.diag
    st.divider()
    st.subheader(f"Diagnosis · `{d.get('target','')}`")

    if ss.get("trace"):
        with st.expander(f"🧠 Agent investigation trace — {len(ss.trace)} tool call(s)", expanded=True):
            for s in ss.trace:
                st.markdown(f"- `{s}`")

    st.markdown(f"**Failure class:** `{d.get('reason','?')}`")
    st.markdown(f"**Root cause:** {d.get('root_cause','—')}")
    st.markdown("**Evidence**"); st.code(d.get("evidence", "—"))
    st.markdown(f"**Fix:** {d.get('fix','—')}")
    st.markdown("**Suggested command**"); st.code(d.get("command", "—"), language="bash")
    st.caption(f"source: {d.get('source','—')}")

    st.subheader("Remediation (human-gated)")
    if not ss.get("paused"):
        st.info("🔧 The agent chose **manual** — no safe automated action; apply the fix above.")
    else:
        st.markdown(f"Proposed action: **{remediation.HUMAN.get(d['action'], d['action'])}**  ·  "
                    f"risk: `{remediation.RISK.get(d['action'],'n/a')}`  ·  target: `{d['target']}`")
        replicas = st.number_input("Replicas", 0, 20, 3) if d["action"] == "scale_deployment" else 2
        execute = st.toggle("Execute for real (changes the cluster)", value=False)
        if execute:
            st.warning("⚠️ This will modify your live cluster.")
        col = st.columns(2)
        if col[0].button("✅ Approve & remediate", type="primary"):
            with st.spinner("Resuming the graph…"):
                final = GRAPH.invoke(
                    Command(resume={"approved": True, "execute": execute, "replicas": replicas}),
                    ss.thread)
            ss.result = final.get("result"); ss.paused = False
        if col[1].button("🚫 Reject"):
            final = GRAPH.invoke(Command(resume={"approved": False}), ss.thread)
            ss.result = final.get("result"); ss.paused = False

    if ss.get("result"):
        r = ss.result
        (st.success if r.get("ok") else st.error)(f"**{r['mode']}** — {r['message']}")

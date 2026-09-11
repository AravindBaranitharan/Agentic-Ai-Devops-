"""
CI/CD Build-Failure Triage Agent — Streamlit demo (LangGraph orchestration).

Reads your REAL failed GitHub Actions runs, lets a LangGraph agent investigate the
real logs and produce a structured triage (root cause + fix), then posts the triage
as a commit comment — only after you approve.

Run:  streamlit run app.py
"""

import os
import uuid
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import github_tools as gh
from agent_graph import GRAPH, has_key, MODEL
from langgraph.types import Command

st.set_page_config(page_title="CI/CD Triage Agent", page_icon="🔧", layout="wide")
ss = st.session_state


def _trace(messages):
    steps = []
    for m in messages:
        for tc in (getattr(m, "tool_calls", None) or []):
            steps.append(f"{tc['name']}({', '.join(f'{k}={v}' for k, v in tc['args'].items())})")
    return steps


st.title("🔧 CI/CD Build-Failure Triage Agent")
st.caption("A LangGraph agent that reads your **real** failed GitHub Actions runs, diagnoses the "
           "root cause from the logs, and posts the triage back — only after you approve.")

authed = gh.has_auth()
who = gh.whoami() if authed else "—"
brain = "🟢 LangGraph · gpt-4o" if has_key() else "🟡 no OPENAI_API_KEY"
st.markdown(f"**GitHub:** {'🟢 '+who if authed else '🔴 not authenticated'} · repo `{gh.repo()}`  ·  "
            f"**Agent:** {brain}")

if not authed:
    st.error("No GitHub token found. Set `GITHUB_TOKEN` in `.env`, or run `gh auth login`, then reload.")
    st.stop()
if not has_key():
    st.warning("Set `OPENAI_API_KEY` in `.env` — the agent needs it to reason.")

# ── failed runs ───────────────────────────────────────────────────────────
c = st.columns([1, 5])
if c[0].button("🔄 Refresh runs"):
    st.rerun()

try:
    runs = gh.list_failed_runs(15)
except Exception as e:
    st.error(f"Could not list runs: {e}")
    st.stop()

st.subheader("Failed workflow runs")
if not runs:
    st.success("🎉 No failed runs in this repo.")
    st.stop()

import pandas as pd
st.dataframe(pd.DataFrame([{
    "run #": r["run_number"], "workflow": r["name"], "branch": r["branch"],
    "commit": r["sha"], "when": r["created_at"],
} for r in runs]), use_container_width=True, hide_index=True)

labels = {f"#{r['run_number']} · {r['name']} · {r['sha']}": r for r in runs}
pick = st.selectbox("Triage which failed run?", list(labels.keys()))
run = labels[pick]
st.markdown(f"[↗ open run on GitHub]({run['url']})")

if st.button("🔎 Investigate & triage", type="primary"):
    ss.thread = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 25}
    ss.run = run
    with st.spinner("LangGraph agent investigating the real logs…"):
        state = GRAPH.invoke({"run": run, "diagnosis": None, "decision": None, "result": None},
                             ss.thread)
    ss.diag = state.get("diagnosis")
    ss.trace = _trace(state.get("messages", []))
    ss.paused = ("__interrupt__" in state)
    ss.result = None

# ── triage + human-gated posting ──────────────────────────────────────────
if ss.get("diag"):
    d = ss.diag
    st.divider()
    st.subheader("Triage report")

    if ss.get("trace"):
        with st.expander(f"🧠 Agent investigation trace — {len(ss.trace)} tool call(s)", expanded=True):
            for s in ss.trace:
                st.markdown(f"- `{s}`")

    m = st.columns(3)
    m[0].metric("Category", d.get("category", "?"))
    m[1].metric("Confidence", d.get("confidence", "?"))
    m[2].metric("Failing job", d.get("failing_job", "?"))
    st.markdown(f"**Failing step:** `{d.get('failing_step','?')}`")
    st.markdown(f"**Root cause:** {d.get('root_cause','—')}")
    st.markdown("**Evidence (real log lines)**"); st.code(d.get("evidence", "—"))
    st.markdown(f"**Suggested fix:** {d.get('fix','—')}")
    st.caption(f"source: {d.get('source','—')}")

    st.subheader("Post triage (human-gated)")
    st.markdown(f"Action: **post a triage comment** on commit `{ss.run['sha']}`  ·  "
                f"risk: `low` (a comment; no code change)")
    execute = st.toggle("Actually post the comment to GitHub", value=False)
    if execute:
        st.warning("⚠️ This posts a public comment on the commit in your repo.")
    col = st.columns(2)
    if col[0].button("✅ Approve & post", type="primary"):
        with st.spinner("Resuming the graph…"):
            final = GRAPH.invoke(
                Command(resume={"approved": True, "execute": execute}), ss.thread)
        ss.result = final.get("result"); ss.paused = False
    if col[1].button("🚫 Reject"):
        final = GRAPH.invoke(Command(resume={"approved": False}), ss.thread)
        ss.result = final.get("result"); ss.paused = False

    if ss.get("result"):
        r = ss.result
        (st.success if r.get("ok") else st.error)(f"**{r['mode']}** — {r['message']}")
        if r.get("url"):
            st.markdown(f"[↗ view the posted comment]({r['url']})")
        if r.get("preview"):
            with st.expander("Comment preview (Markdown)", expanded=not r.get("url")):
                st.markdown(r["preview"])

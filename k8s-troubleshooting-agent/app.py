"""
Kubernetes Troubleshooting Agent — Streamlit demo.

Flow:  pick a namespace  →  see unhealthy pods  →  the agent reads status/events/logs
and DIAGNOSES the root cause (gpt-4o)  →  it proposes a fix  →  a human approves before
any remediation runs.

Run:  streamlit run app.py
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import k8s_tools as k8s
from k8s_agent import diagnose, has_key, MODEL
import remediation

st.set_page_config(page_title="K8s Troubleshooting Agent", page_icon="🩺", layout="wide")
ss = st.session_state

st.title("🩺 Kubernetes Troubleshooting Agent")
st.caption("Point it at a namespace. It finds broken pods, reads their events + logs, "
           "explains the root cause, and proposes a fix — nothing is changed without your approval.")

cluster = "🟢 live cluster" if k8s._real_enabled() else "🧪 mock cluster"
brain = f"🟢 gpt-4o" if has_key() else "🟡 offline heuristic"
st.markdown(f"**Cluster:** {cluster} · `{k8s.cluster_context()}`  ·  **Diagnosis:** {brain}")

# ── namespace picker ──────────────────────────────────────────────────────
namespaces = k8s.list_namespaces()
col = st.columns([2, 1, 3])
ns = col[0].selectbox("Namespace", namespaces, index=0)
only_bad = col[1].toggle("Only unhealthy", value=True)

pods = k8s.unhealthy_pods(ns) if only_bad else k8s.list_pods(ns)

# ── pod table ─────────────────────────────────────────────────────────────
st.subheader(f"Pods in `{ns}`")
if not pods:
    st.success("🎉 No unhealthy pods in this namespace.")
else:
    import pandas as pd
    df = pd.DataFrame([{
        "": "❌" if not p["healthy"] else "✅",
        "pod": p["name"], "phase": p["phase"], "reason": p["reason"],
        "restarts": p["restarts"], "ready": p["ready"], "node": p["node"],
    } for p in pods])
    st.dataframe(df, use_container_width=True, hide_index=True)

    names = [p["name"] for p in pods]
    pick = st.selectbox("Diagnose which pod?", names)

    if st.button("🔎 Diagnose", type="primary"):
        bundle = k8s.get_pod_bundle(ns, pick)
        with st.spinner("Reading events + logs, reasoning about the failure…"):
            ss.diag = diagnose(bundle)
        ss.bundle = bundle
        ss.remediated = None

# ── diagnosis + remediation ───────────────────────────────────────────────
if ss.get("diag") and ss.get("bundle"):
    d, b = ss.diag, ss.bundle
    st.divider()
    st.subheader(f"Diagnosis · `{b['name']}`")

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"**Failure class:** `{d.get('reason','?')}`  \n"
                    f"**Root cause:** {d.get('root_cause','—')}")
        if d.get("evidence"):
            ev = d["evidence"] if isinstance(d["evidence"], str) else "\n".join(d["evidence"])
            st.markdown("**Evidence**")
            st.code(ev)
        st.markdown(f"**Fix:** {d.get('fix','—')}")
        st.caption(f"source: {d.get('source','—')}")
    with c2:
        st.markdown("**Events**")
        st.code("\n".join(b.get("events", [])) or "(none)")
        with st.expander("Log tail"):
            st.code(b.get("logs", "") or "(no logs)")

    st.markdown("**Suggested command**")
    st.code(d.get("command", "—"), language="bash")

    # ── human-gated remediation ───────────────────────────────────────────
    st.subheader("Remediation (human-gated)")
    action = d.get("action", "manual")
    if action == "manual":
        st.info("🔧 No safe automated action — this needs a manual fix (see the steps above).")
    else:
        risk = remediation.RISK.get(action, "n/a")
        st.markdown(f"Proposed action: **{remediation.HUMAN[action]}**  ·  risk: `{risk}`")
        target = d.get("deployment") if action != "delete_pod" else b["name"]
        replicas = 2
        if action == "scale_deployment":
            replicas = st.number_input("Replicas", 0, 20, 3)
        execute = st.toggle("Execute for real (changes the cluster)", value=False)
        if execute:
            st.warning("⚠️ This will modify your live cluster.")
        if st.button("✅ Approve & remediate"):
            ss.remediated = remediation.run_action(
                action, b["namespace"], target, execute=execute, replicas=replicas)
        if ss.get("remediated"):
            r = ss.remediated
            (st.success if r["ok"] else st.error)(f"**{r['mode']}** — {r['message']}")

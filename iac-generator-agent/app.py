"""
IaC Generator Agent — Streamlit demo.

Flow:  plain English  →  Terraform HCL (gpt-4o)  →  terraform plan  →  the agent
explains the diff  →  policy-as-code check  →  human approval gate before apply.

Run:  streamlit run app.py
"""

import os
import shutil
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from iac_agent import generate_hcl, explain_plan, has_key, MODEL
from terraform_runner import run_plan, _real_enabled
import policy

st.set_page_config(page_title="IaC Generator Agent", page_icon="🏗️", layout="wide")
ss = st.session_state

st.title("🏗️ IaC Generator Agent")
st.caption("Describe infrastructure in plain English → get reviewed Terraform, a `terraform plan`, "
           "and a plain-English explanation. Nothing is applied without your approval.")

tf = "🟢 terraform CLI" if _real_enabled() else "🧪 mock plan"
brain = "🟢 gpt-4o" if has_key() else "🟡 offline sample"
st.markdown(f"**Plan engine:** {tf}  ·  **Generator:** {brain}")

EXAMPLES = [
    "A private S3 bucket for app assets with versioning and encryption.",
    "An S3 bucket for public website hosting.",
    "A security group for a web server allowing HTTP and SSH from anywhere.",
    "A DynamoDB table 'orders' with on-demand billing and a 'status' GSI.",
]
choice = st.selectbox("Try an example (or write your own below):", ["—"] + EXAMPLES)
default = choice if choice != "—" else ""
req = st.text_area("Describe the infrastructure you want:", value=default, height=80,
                   placeholder="e.g. a private S3 bucket with versioning and encryption")

if st.button("⚙️ Generate & plan", type="primary") and req.strip():
    with st.spinner("Generating Terraform…"):
        ss.hcl = generate_hcl(req.strip())
    with st.spinner("Running terraform plan…"):
        ss.plan = run_plan(ss.hcl)
    with st.spinner("Reviewing the plan…"):
        ss.explain = explain_plan(ss.plan["plan_text"])
    ss.findings = policy.check(ss.hcl)
    ss.verdict = policy.verdict(ss.findings)
    ss.applied = None

if "hcl" in ss:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("1 · Generated Terraform")
        st.code(ss.hcl, language="hcl")
    with c2:
        st.subheader(f"2 · terraform plan  ·  {ss.plan['mode']}")
        cc = ss.plan["counts"]
        m1, m2, m3 = st.columns(3)
        m1.metric("add", cc["add"]); m2.metric("change", cc["change"]); m3.metric("destroy", cc["destroy"])
        st.code(ss.plan["plan_text"], language="hcl")
        if ss.plan.get("note"):
            st.caption(ss.plan["note"])

    st.subheader("3 · The agent's review")
    st.info(ss.explain)

    st.subheader("4 · Policy check")
    for f in ss.findings:
        icon = "✅" if f["status"] == "PASS" else "❌"
        st.markdown(f"{icon} **{f['id']}** — {f['message']}")
    if ss.verdict == "DENY":
        st.error("🚫 Policy DENY — fix the flagged issues before this can be applied.")
    else:
        st.success("✅ Policy PASS — eligible for approval.")

    st.subheader("5 · Apply (human-gated)")
    if ss.verdict == "DENY":
        st.caption("Apply is blocked while policy fails.")
    else:
        real_apply = st.toggle("Actually run `terraform apply` (creates real AWS resources)", value=False)
        if real_apply:
            st.warning("⚠️ This will create real infrastructure in your AWS account.")
        if st.button("✅ Approve & apply"):
            if real_apply and _real_enabled():
                import subprocess
                from terraform_runner import WORKDIR
                with st.spinner("Applying…"):
                    r = subprocess.run(["terraform", "apply", "-auto-approve", "-input=false", "-no-color"],
                                       cwd=WORKDIR, capture_output=True, text=True, timeout=300)
                ss.applied = (r.stdout + r.stderr)[-1500:]
            else:
                ss.applied = "DRY-RUN: approved — would run `terraform apply`. (Enable the toggle to apply for real.)"
        if ss.get("applied"):
            st.code(ss.applied)
else:
    st.info("Pick an example or describe infrastructure, then click **Generate & plan**.")

"""
S3 Freshness page — a second page in the same Streamlit app.

Audits every S3 bucket: PASS if an object was modified within the chosen window
(default 30 days), otherwise FAIL. Powered by the LangChain tool/agent in s3_status.py.
"""

import os
import sys

import streamlit as st
from dotenv import load_dotenv

# make the app root importable + load the same .env the chat uses
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
load_dotenv(os.path.join(_ROOT, ".env"))
load_dotenv(os.path.join(_ROOT, "env"))

from s3_status import s3_bucket_freshness, ask_s3_agent  # noqa: E402

st.set_page_config(page_title="S3 Freshness", page_icon="🪣", layout="centered")

ss = st.session_state
real = os.getenv("USE_REAL_AWS", "false").lower() in ("1", "true", "yes")
has_key = bool(os.getenv("OPENAI_API_KEY"))

st.title("🪣 S3 Freshness Audit")
st.caption("A bucket **PASSES** if any object was updated within the window, else it **FAILS** (stale). "
           "Built with LangChain.")
st.markdown(f"**Cloud:** {'🟢 REAL AWS (boto3)' if real else '🧪 MOCK (safe demo data)'} · "
            f"**Agent:** {'🟢 gpt-4o (LangChain)' if has_key else '🟡 no key — table still works'}")

days = st.slider("Freshness window (days)", min_value=1, max_value=180, value=30, step=1)

col_run, col_note = st.columns([1, 2])
if col_run.button("▶️ Run freshness check", type="primary", use_container_width=True):
    with st.spinner("Scanning buckets…"):
        ss.s3_rows = s3_bucket_freshness(days)
        ss.s3_days = days
col_note.caption("Active buckets return fast (we stop at the first recent object); "
                 "only stale buckets are fully scanned.")


def _badge(status: str) -> str:
    color = {"PASS": "#1f9d55", "FAIL": "#e3342f", "ERROR": "#b08900"}.get(status, "#6b7280")
    return (f'<span style="background:{color};color:#fff;padding:2px 11px;border-radius:6px;'
            f'font-size:12px;font-weight:700;letter-spacing:.03em">{status}</span>')


rows = ss.get("s3_rows")
if rows:
    npass = sum(1 for r in rows if r["status"] == "PASS")
    nfail = sum(1 for r in rows if r["status"] == "FAIL")
    nerr = sum(1 for r in rows if r["status"] == "ERROR")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Buckets", len(rows))
    m2.metric("✅ PASS", npass)
    m3.metric("❌ FAIL", nfail)
    m4.metric("⚠️ Error", nerr)

    html = ["<table style='width:100%;border-collapse:collapse;font-size:14px'>",
            "<tr style='text-align:left;border-bottom:1px solid #444'>"
            "<th style='padding:8px 6px'>Bucket</th><th>Status</th>"
            "<th>Newest object</th><th>Note</th></tr>"]
    for r in sorted(rows, key=lambda x: (x["status"] != "FAIL", x["bucket"])):
        when = r["latest"].strftime("%Y-%m-%d %H:%M UTC") if r["latest"] else "—"
        html.append(
            "<tr style='border-bottom:1px solid #2a2a2a'>"
            f"<td style='padding:8px 6px;font-family:monospace'>{r['bucket']}</td>"
            f"<td>{_badge(r['status'])}</td>"
            f"<td style='color:#9aa7bd'>{when}</td>"
            f"<td style='color:#9aa7bd'>{r['note']}</td></tr>")
    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)

    if nfail:
        st.warning(f"{nfail} bucket(s) had no updates in the last {ss.get('s3_days', days)} days — "
                   "candidates for archival or cleanup.")
    else:
        st.success("Every bucket is fresh within the window. ✅")
else:
    st.info("Set a window and click **Run freshness check** to audit your buckets.")

# ── LangChain agent — natural-language questions over the audit ──
st.divider()
st.subheader("Ask the LangChain agent")
q = st.text_input("e.g. “which buckets are stale?” or “are any backups older than 90 days?”")
if st.button("Ask") and q:
    with st.spinner("LangChain agent (gpt-4o) is checking…"):
        st.markdown(ask_s3_agent(q))

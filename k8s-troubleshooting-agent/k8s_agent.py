"""
Kubernetes Troubleshooting Agent — the brain (OpenAI gpt-4o).

Given a pod's status + events + logs (from k8s_tools.get_pod_bundle), the agent
returns a structured diagnosis:
  • root_cause  — what actually went wrong, in plain English
  • evidence    — the exact lines it keyed off
  • fix         — the concrete remediation steps
  • command     — a single suggested kubectl/action to fix it
  • action      — a machine key the remediation layer understands (or "manual")

The agent only READS and REASONS. It never changes the cluster — remediation is a
separate, human-gated step (see remediation.py + the Streamlit app).
"""

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _here = Path(__file__).resolve().parent
    load_dotenv(_here / ".env")
    load_dotenv(_here / "env")
except ImportError:
    pass

MODEL = os.getenv("MODEL", "gpt-4o")


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


# --------------------------------------------------------------------------- #
#  Heuristic first pass — a fast, offline label + suggested action.
#  (The LLM refines this; if there's no key, this IS the answer.)
# --------------------------------------------------------------------------- #
def classify(bundle: dict) -> dict:
    reason = ""
    for c in bundle.get("containers", []):
        if c.get("reason"):
            reason = c["reason"]
            break
    reason = reason or bundle.get("phase", "")
    text = (json.dumps(bundle.get("events", [])) + bundle.get("logs", "")).lower()

    table = {
        "CrashLoopBackOff": (
            "The container starts, crashes, and Kubernetes keeps restarting it with a growing back-off.",
            "Read the crash logs to find why it exits (bad config, missing env var, failed dependency). "
            "Fix the root cause, then roll the deployment. A restart alone won't help if config is wrong.",
            "kubectl -n {ns} rollout restart deploy/{dep}", "restart_deployment"),
        "ImagePullBackOff": (
            "The image can't be pulled — wrong tag, private registry without credentials, or the image doesn't exist.",
            "Verify the image name/tag exists and the node can authenticate to the registry "
            "(imagePullSecrets). Set a valid tag and redeploy.",
            "kubectl -n {ns} describe pod {pod}   # confirm the image, then fix the tag", "manual"),
        "ErrImagePull": (
            "The image pull failed outright — tag/registry issue.",
            "Correct the image tag or registry credentials, then redeploy.",
            "kubectl -n {ns} describe pod {pod}", "manual"),
        "OOMKilled": (
            "The container used more memory than its limit, so the kernel killed it (exit 137).",
            "Raise the memory limit, or fix the workload's memory usage (batch smaller, stream instead of buffer).",
            "kubectl -n {ns} set resources deploy/{dep} --limits=memory=512Mi", "manual"),
        "Unschedulable": (
            "No node can fit this pod — usually insufficient CPU/memory or a taint/affinity mismatch.",
            "Add capacity (scale the node group / cluster-autoscaler), lower the pod's requests, "
            "or fix nodeSelector/affinity/tolerations.",
            "kubectl -n {ns} describe pod {pod}   # read the FailedScheduling reason", "manual"),
        "Unhealthy": (
            "The pod runs but a readiness/liveness probe fails, so it never becomes Ready (or is restarted).",
            "Check the probe path/port and whether the app's dependency is up. Fix the dependency or "
            "relax the probe (initialDelaySeconds / correct path).",
            "kubectl -n {ns} describe pod {pod}   # inspect the probe + its target", "manual"),
        "CreateContainerConfigError": (
            "The container can't be created because a referenced Secret or ConfigMap is missing.",
            "Create the missing Secret/ConfigMap (or fix the reference name), then the pod will start.",
            "kubectl -n {ns} create secret generic <name> ...   # then redeploy", "manual"),
    }
    if reason in table:
        rc, fix, cmd, action = table[reason]
    elif "oom" in text or "exit code 137" in text:
        rc, fix, cmd, action = table["OOMKilled"]
        reason = "OOMKilled"
    else:
        rc = f"Pod is in state '{reason or 'Unknown'}'."
        fix = "Inspect events and logs to determine the cause."
        cmd = "kubectl -n {ns} describe pod {pod}"
        action = "manual"

    dep = bundle.get("deployment", bundle.get("name", "").rsplit("-", 2)[0])
    fmt = dict(ns=bundle.get("namespace", ""), pod=bundle.get("name", ""), dep=dep)
    return {
        "reason": reason,
        "root_cause": rc,
        "fix": fix,
        "command": cmd.format(**fmt),
        "action": action,
        "deployment": dep,
    }


_SYSTEM = (
    "You are an expert Kubernetes SRE. You are given a single pod's status, container "
    "states, recent events, and a log tail. Diagnose the problem precisely and return "
    "STRICT JSON with these keys:\n"
    '  "reason"      : the k8s failure class (e.g. CrashLoopBackOff, ImagePullBackOff, '
    'OOMKilled, Unschedulable, Unhealthy, CreateContainerConfigError, or Healthy)\n'
    '  "root_cause"  : 1-2 sentences, plain English, pointing at the ACTUAL cause\n'
    '  "evidence"    : the exact event/log line(s) that prove it (short)\n'
    '  "fix"         : concrete remediation steps, plain English\n'
    '  "command"     : ONE suggested kubectl command to remediate (use the real namespace/name)\n'
    '  "action"      : one of restart_deployment | scale_deployment | delete_pod | manual\n'
    "Pick 'restart_deployment' ONLY when a rollout restart genuinely fixes it; otherwise "
    "'manual'. Base everything on the evidence — do not invent resources. Output JSON only."
)


def diagnose(bundle: dict) -> dict:
    """Full diagnosis. Uses gpt-4o when a key is present; else the heuristic."""
    base = classify(bundle)
    if not has_key() or bundle.get("error"):
        base.setdefault("evidence", (bundle.get("logs", "") or "").strip().splitlines()[-1:] or ["—"])
        base["evidence"] = base["evidence"] if isinstance(base["evidence"], str) else " ".join(base["evidence"])
        base["source"] = "offline heuristic"
        return base

    from openai import OpenAI
    client = OpenAI()
    payload = {
        "namespace": bundle.get("namespace"), "pod": bundle.get("name"),
        "phase": bundle.get("phase"), "containers": bundle.get("containers"),
        "events": bundle.get("events"), "logs": (bundle.get("logs") or "")[-3500:],
    }
    try:
        resp = client.chat.completions.create(
            model=MODEL, temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": json.dumps(payload)}],
        )
        out = json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        base["source"] = f"heuristic (LLM error: {e})"
        base.setdefault("evidence", "—")
        return base

    # merge: prefer the LLM, but keep the heuristic's machine action + deployment
    out.setdefault("action", base["action"])
    if out.get("action") not in ("restart_deployment", "scale_deployment", "delete_pod", "manual"):
        out["action"] = base["action"]
    out["deployment"] = base["deployment"]
    out.setdefault("reason", base["reason"])
    out.setdefault("command", base["command"])
    out["source"] = f"gpt-4o ({MODEL})"
    return out

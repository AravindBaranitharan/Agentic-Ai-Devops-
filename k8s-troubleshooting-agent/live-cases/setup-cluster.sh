#!/usr/bin/env bash
# Spin up a REAL local Kubernetes cluster and load it with the live failure cases.
# The agent then reads these live via the Kubernetes API (USE_REAL_K8S=true).
#
# Prereqs: Docker running, plus `kind` and `kubectl`  (brew install kind kubectl).
#
#   ./setup-cluster.sh          # create cluster + apply cases
#   ./setup-cluster.sh clean    # delete the cluster
set -euo pipefail

CLUSTER="k8s-troubleshooter"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "clean" ]]; then
  kind delete cluster --name "$CLUSTER"
  exit 0
fi

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "▶ creating kind cluster '$CLUSTER'…"
  kind create cluster --name "$CLUSTER"
fi

echo "▶ applying live failure cases…"
kubectl apply -f "$HERE/live-cases.yaml"

echo "▶ waiting ~60s for pods to reach steady failure states…"
sleep 60

echo
echo "▶ current pods (this is what the agent will read LIVE):"
kubectl get pods -A -l 'app' -o wide || kubectl get pods -n shop -n platform

cat <<EOF

✅ Live cluster ready.

Point the agent at it:
   export USE_REAL_K8S=true          # (or set it in .env)
   streamlit run app.py

Tear down when done:
   ./setup-cluster.sh clean
EOF

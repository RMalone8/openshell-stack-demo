#!/usr/bin/env bash
# Apply the OpenClaw launcher; requires 00 and 01 to have succeeded.
set -euo pipefail
cd "$(dirname "$0")/.."
NS="${NS:-openshell}"
oc apply -k manifests
oc -n "$NS" rollout status deploy/openclaw-launcher --timeout=300s
echo "Logs: oc -n $NS logs -f deploy/openclaw-launcher"

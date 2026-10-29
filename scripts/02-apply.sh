#!/usr/bin/env bash
# Apply vLLM and Praxis; requires 00 and 01 to have succeeded.
set -euo pipefail
cd "$(dirname "$0")/.."
NS="${NS:-openshell-demo}"
oc apply -k manifests

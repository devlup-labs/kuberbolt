#!/usr/bin/env bash
# ==============================================================================
# Start Kuberbolt Financial Pod (gRPC Server on port 6001)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

mkdir -p "${HOME}/.kuberbolt/provider"
cd "${REPO_ROOT}/agent-pod/financial-pod"

echo "=================================================================="
echo "⚡ Starting Financial Pod gRPC Server (:6001)"
echo "=================================================================="

exec go run ./cmd/financialpod --config "${REPO_ROOT}/kuberbolt-config/seller.yaml"
#!/usr/bin/env bash
# Build and push the internal Renovate image to registry.cern.ch.
# Usage: ./build-renovate-image.sh <INTERNAL_TAG>
# Example: ./build-renovate-image.sh 2026.04
#
# Requires: docker, yq, docker login to registry.cern.ch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSIONS_FILE="${SCRIPT_DIR}/renovate-versions.yml"
REGISTRY="registry.cern.ch/dsb/devops/devtools/renovate"

INTERNAL_TAG="${1:-}"
if [ -z "$INTERNAL_TAG" ]; then
    echo "Usage: $0 <INTERNAL_TAG>"
    echo "Available tags:"
    yq 'keys | .[]' "$VERSIONS_FILE"
    exit 1
fi

RENOVATE_TAG=$(yq ".\"${INTERNAL_TAG}\"" "$VERSIONS_FILE")
if [ -z "$RENOVATE_TAG" ] || [ "$RENOVATE_TAG" = "null" ]; then
    echo "ERROR: No upstream tag found for '${INTERNAL_TAG}' in ${VERSIONS_FILE}"
    exit 1
fi

echo "Building ${REGISTRY}:${INTERNAL_TAG} from renovate/renovate:${RENOVATE_TAG}"
docker build \
    --build-arg RENOVATE_TAG="${RENOVATE_TAG}" \
    -t "${REGISTRY}:${INTERNAL_TAG}" \
    -f "${SCRIPT_DIR}/Dockerfile.renovate" \
    "${SCRIPT_DIR}/.."

echo "Pushing ${REGISTRY}:${INTERNAL_TAG}"
docker push "${REGISTRY}:${INTERNAL_TAG}"
echo "Done."

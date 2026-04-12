#!/usr/bin/env bash
# Build and push the internal Renovate image to registry.cern.ch.
# Usage: ./build-renovate-image.sh <INTERNAL_TAG> [UPSTREAM_TAG]
# Example: ./build-renovate-image.sh 2026.05
#          ./build-renovate-image.sh 2026.05 43.200.0-full
#
# Requires: docker, yq, curl, docker login to registry.cern.ch

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSIONS_FILE="${SCRIPT_DIR}/renovate-versions.yml"
REGISTRY="registry.cern.ch/dsb/devops/devtools/renovate"

INTERNAL_TAG="${1:-}"
if [ -z "$INTERNAL_TAG" ]; then
    echo "Usage: $0 <INTERNAL_TAG> [UPSTREAM_TAG]"
    echo ""
    echo "Existing mappings:"
    yq 'to_entries | .[] | .key + " -> " + .value' "$VERSIONS_FILE"
    exit 1
fi

# Check if mapping already exists
EXISTING=$(yq ".\"${INTERNAL_TAG}\"" "$VERSIONS_FILE")

if [ -n "$EXISTING" ] && [ "$EXISTING" != "null" ]; then
    SUGGESTED="$EXISTING"
else
    # Fetch latest -full tag from Docker Hub
    echo "Fetching latest renovate/renovate -full tags from Docker Hub..."
    SUGGESTED=$(curl -s "https://hub.docker.com/v2/repositories/renovate/renovate/tags?page_size=50" \
        | grep -o '"name":"[^"]*-full"' \
        | head -1 \
        | sed 's/"name":"//;s/"//')
    if [ -z "$SUGGESTED" ]; then
        SUGGESTED="latest-full"
    fi
fi

# Allow override via second argument or interactive prompt
if [ -n "${2:-}" ]; then
    RENOVATE_TAG="$2"
else
    echo "Suggested upstream tag: ${SUGGESTED}"
    read -rp "Upstream Renovate tag [-full required, enter to accept]: " INPUT
    RENOVATE_TAG="${INPUT:-$SUGGESTED}"
fi

# Validate -full suffix
if [[ "$RENOVATE_TAG" != *-full ]]; then
    echo "ERROR: upstream tag must end in -full (got '${RENOVATE_TAG}')"
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

# Update versions file
if [ "$EXISTING" != "$RENOVATE_TAG" ]; then
    yq -i ".\"${INTERNAL_TAG}\" = \"${RENOVATE_TAG}\"" "$VERSIONS_FILE"
    echo "Updated ${VERSIONS_FILE}: ${INTERNAL_TAG} -> ${RENOVATE_TAG}"

    cd "${SCRIPT_DIR}/.."
    git add .gitlab/renovate-versions.yml
    git commit -m "chore: record renovate image ${INTERNAL_TAG} -> ${RENOVATE_TAG}"
    echo "Committed mapping update. Don't forget to push."
else
    echo "Mapping already up to date."
fi

echo "Done."

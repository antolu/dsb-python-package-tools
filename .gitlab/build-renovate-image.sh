#!/usr/bin/env bash
# Build and push the internal Renovate image to registry.cern.ch.
# Usage: ./build-renovate-image.sh <INTERNAL_TAG> [UPSTREAM_TAG]
# Example: ./build-renovate-image.sh 2026.05
#          ./build-renovate-image.sh 2026.05 43.200.0
#
# Requires: docker, python3 (with ruamel.yaml), curl
# docker login to registry.cern.ch must be done beforehand

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSIONS_FILE="${SCRIPT_DIR}/renovate-versions.yml"
REGISTRY="registry.cern.ch/dsb-devtools/renovate"

_py() {
    python3 - "$@" <<'EOF'
import sys
from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True

def read(path):
    with open(path) as f:
        return yaml.load(f)

def write(path, data):
    with open(path, "w") as f:
        yaml.dump(data, f)

def get(path, key):
    d = read(path)
    val = d.get(key)
    print(val if val is not None else "")

def set_(path, key, value):
    d = read(path)
    d[key] = value
    write(path, d)

def list_keys(path):
    d = read(path)
    for k, v in d.items():
        if not str(k).startswith("#"):
            print(f"{k} -> {v}")

cmd = sys.argv[1]
if cmd == "get":
    get(sys.argv[2], sys.argv[3])
elif cmd == "set":
    set_(sys.argv[2], sys.argv[3], sys.argv[4])
elif cmd == "list":
    list_keys(sys.argv[2])
EOF
}

INTERNAL_TAG="${1:-}"
if [ -z "$INTERNAL_TAG" ]; then
    echo "Usage: $0 <INTERNAL_TAG> [UPSTREAM_TAG]"
    echo ""
    echo "Existing mappings:"
    _py list "$VERSIONS_FILE"
    exit 1
fi

# Check if mapping already exists
EXISTING=$(_py get "$VERSIONS_FILE" "$INTERNAL_TAG")

if [ -n "$EXISTING" ]; then
    SUGGESTED="$EXISTING"
else
    # Fetch latest slim (no suffix) versioned tag from Docker Hub
    echo "Fetching latest renovate/renovate slim tags from Docker Hub..."
    SUGGESTED=$(curl -s "https://hub.docker.com/v2/repositories/renovate/renovate/tags?page_size=50" \
        | python3 -c "
import json, sys, re
tags = [t['name'] for t in json.load(sys.stdin)['results']]
slim = [t for t in tags if re.fullmatch(r'[0-9]+\.[0-9]+(\.[0-9]+)?', t)]
print(slim[0] if slim else '')
") || true
    if [ -z "$SUGGESTED" ]; then
        SUGGESTED=""
    fi
fi

# Allow override via second argument or interactive prompt
if [ -n "${2:-}" ]; then
    RENOVATE_TAG="$2"
else
    echo "Suggested upstream tag: ${SUGGESTED:-none found}"
    read -rp "Upstream Renovate tag (e.g. 43.129, enter to accept): " INPUT
    RENOVATE_TAG="${INPUT:-$SUGGESTED}"
fi

# Validate: must be a versioned slim tag (digits and dots only, no suffix)
if [[ ! "$RENOVATE_TAG" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "ERROR: upstream tag must be a versioned slim tag like '43.129' or '43.129.0' (got '${RENOVATE_TAG}')"
    exit 1
fi

echo "Building ${REGISTRY}:${INTERNAL_TAG} from renovate/renovate:${RENOVATE_TAG}"
docker buildx build \
    --build-arg RENOVATE_TAG="${RENOVATE_TAG}" \
    -t "${REGISTRY}:${INTERNAL_TAG}" \
    -f "${SCRIPT_DIR}/Dockerfile.renovate" \
    --load \
    "${SCRIPT_DIR}/.."

echo "Pushing ${REGISTRY}:${INTERNAL_TAG}"
docker push "${REGISTRY}:${INTERNAL_TAG}"

# Update versions file if needed
if [ "$EXISTING" != "$RENOVATE_TAG" ]; then
    _py set "$VERSIONS_FILE" "$INTERNAL_TAG" "$RENOVATE_TAG"
    echo ""
    echo "Updated ${VERSIONS_FILE}: ${INTERNAL_TAG} -> ${RENOVATE_TAG}"
    read -rp "Commit mapping update? [y/N] " CONFIRM
    if [[ "${CONFIRM,,}" == "y" ]]; then
        cd "${SCRIPT_DIR}/.."
        git add .gitlab/renovate-versions.yml
        git commit -m "chore: record renovate image ${INTERNAL_TAG} -> ${RENOVATE_TAG}"
        echo "Committed. Don't forget to push."
    else
        echo "Skipped commit. To commit manually:"
        echo "  git add .gitlab/renovate-versions.yml"
        echo "  git commit -m \"chore: record renovate image ${INTERNAL_TAG} -> ${RENOVATE_TAG}\""
    fi
else
    echo "Mapping already up to date."
fi

echo "Done."

#!/usr/bin/env bash
# =============================================================================
# PH Agent Hub — Build & Push Script
# =============================================================================
# Builds backend and frontend Docker images, then optionally pushes them to
# Docker Hub (or another registry).
#
# Usage:
#   ./build.sh                          # Build both images with :latest tag
#   ./build.sh -t v1.2.3                # Build with a specific version tag
#   ./build.sh -t v1.2.3 -p             # Build and push to registry
#   ./build.sh -t v1.2.3 -p --no-cache  # Build without cache and push
#
# Prerequisites:
#   - Docker installed and running
#   - Logged into the registry (docker login) if using --push
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Configuration ──────────────────────────────────────────────────────────
REGISTRY="phalouvas"           # Docker Hub user or full registry URL
BACKEND_IMAGE="${REGISTRY}/ph-agent-hub-backend"
FRONTEND_IMAGE="${REGISTRY}/ph-agent-hub-frontend"
TAG="latest"
PUSH=false
NO_CACHE=""

# ── Help ───────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -t, --tag TAG       Image tag (default: latest)
  -p, --push          Push to registry after building
  --no-cache          Build without Docker cache
  -h, --help          Show this help
EOF
  exit 0
}

# ── Parse arguments ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--tag) TAG="$2"; shift 2 ;;
    -p|--push) PUSH=true; shift ;;
    --no-cache) NO_CACHE="--no-cache"; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# ── Build backend ──────────────────────────────────────────────────────────
echo "========================================"
echo " Building backend: ${BACKEND_IMAGE}:${TAG}"
echo "========================================"
docker build $NO_CACHE \
  -t "${BACKEND_IMAGE}:${TAG}" \
  -f "${PROJECT_DIR}/backend/Dockerfile" \
  "${PROJECT_DIR}/backend"

# ── Build frontend ─────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " Building frontend: ${FRONTEND_IMAGE}:${TAG}"
echo "========================================"
docker build $NO_CACHE \
  -t "${FRONTEND_IMAGE}:${TAG}" \
  -f "${PROJECT_DIR}/frontend/Dockerfile.prod" \
  "${PROJECT_DIR}/frontend"

# ── Push (optional) ────────────────────────────────────────────────────────
if $PUSH; then
  echo ""
  echo "========================================"
  echo " Pushing images to ${REGISTRY} ..."
  echo "========================================"
  docker push "${BACKEND_IMAGE}:${TAG}"
  docker push "${FRONTEND_IMAGE}:${TAG}"
  echo ""
  echo "Done — both images pushed with tag '${TAG}'."
else
  echo ""
  echo "Done — images built with tag '${TAG}'. Use --push to push to registry."
fi

#!/usr/bin/env bash
#
# Deploy the Obi frontend (Railway service "obi-web") from the repo root.
#
# Why this script exists
# ----------------------
# The frontend and backend live in one monorepo and deploy from the same repo
# root, but the root `railway.json`, `Dockerfile` and `.dockerignore` are
# BACKEND-ONLY (Python image, Dockerfile builder, /health check, and a
# dockerignore that strips the frontend out of the build context). Railway's
# config-as-code OVERRIDES per-service settings, and the per-service config
# path is deprecated (the modern IaC route needs the Railway TS SDK), so a
# plain `railway up` for obi-web would rebuild the BACKEND image and fail.
#
# The fix: move those three backend-only files aside for the upload only, run
# `railway up` (obi-web then builds with Railpack via its own service settings:
# build `pnpm --filter web build`, start `pnpm --filter web start`), and
# restore the three files immediately — even on error — via an EXIT trap. The
# backend is never modified and never redeployed.
#
# Usage:  scripts/deploy-frontend.sh ["deploy message"]
#
# Notes:
# - Run with bash (not sh/zsh): it uses a bash array.
# - OBI_ORIGIN is baked into obi.js at BUILD time. If the frontend's public
#   URL changes, set the OBI_ORIGIN service variable first, then run this.
set -euo pipefail

SERVICE="obi-web"
MSG="${1:-obi frontend deploy}"

# This script lives in <repo-root>/scripts/.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HIDE=(railway.json Dockerfile .dockerignore)
STASH="$(mktemp -d)"

restore() {
  local f
  for f in "${HIDE[@]}"; do
    if [ -f "$STASH/$f" ]; then
      mv -f "$STASH/$f" "$ROOT/$f"
    fi
  done
  rmdir "$STASH" 2>/dev/null || true
  echo "[deploy-frontend] restored backend-only files: ${HIDE[*]}"
}
trap restore EXIT

for f in "${HIDE[@]}"; do
  if [ -f "$ROOT/$f" ]; then
    mv -f "$ROOT/$f" "$STASH/$f"
  fi
done
echo "[deploy-frontend] hid backend-only files for upload: ${HIDE[*]}"

RAILWAY_CALLER="skill:use-railway@1.2.1" \
RAILWAY_AGENT_SESSION="deploy-frontend-$(date +%s)" \
  railway up --service "$SERVICE" --detach -m "$MSG"

echo "[deploy-frontend] upload submitted for service '$SERVICE'; watch the build in the Railway dashboard."

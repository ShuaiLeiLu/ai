#!/usr/bin/env bash

if [[ -z "${BASH_VERSION:-}" ]]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_PID=""
WEB_PID=""
STATUS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/cyber-invest-dev.XXXXXX")"
PNPM_CMD="${PNPM:-}"

if [[ -z "$PNPM_CMD" ]]; then
  if command -v pnpm >/dev/null 2>&1; then
    PNPM_CMD="pnpm"
  elif command -v corepack >/dev/null 2>&1; then
    PNPM_CMD="corepack pnpm"
  else
    echo "pnpm is required. Install pnpm or enable Corepack first."
    exit 1
  fi
fi

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  echo
  echo "Stopping dev servers..."

  if [[ -n "$API_PID" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi

  if [[ -n "$WEB_PID" ]]; then
    kill "$WEB_PID" 2>/dev/null || true
  fi

  if [[ -n "$API_PID" ]]; then
    wait "$API_PID" 2>/dev/null || true
  fi

  if [[ -n "$WEB_PID" ]]; then
    wait "$WEB_PID" 2>/dev/null || true
  fi

  rm -rf "$STATUS_DIR"

  exit "$exit_code"
}

trap cleanup EXIT INT TERM

echo "Starting backend: make dev-api"
(
  set +e
  make dev-api
  echo $? > "$STATUS_DIR/api.status"
) &
API_PID=$!

echo "Starting frontend: make dev-web"
(
  set +e
  make PNPM="$PNPM_CMD" dev-web
  echo $? > "$STATUS_DIR/web.status"
) &
WEB_PID=$!

echo
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://localhost:3001"
echo "Press Ctrl+C to stop both."
echo

while true; do
  if [[ -f "$STATUS_DIR/api.status" ]]; then
    exit "$(cat "$STATUS_DIR/api.status")"
  fi

  if [[ -f "$STATUS_DIR/web.status" ]]; then
    exit "$(cat "$STATUS_DIR/web.status")"
  fi

  sleep 1
done

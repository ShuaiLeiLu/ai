#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <prompt-file> [model]"
  exit 1
fi

PROMPT_FILE="$1"
MODEL="${2:-gemini-2.5-pro}"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE"
  exit 1
fi

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY is required"
  exit 1
fi

if [[ -z "${GOOGLE_GEMINI_BASE_URL:-}" ]]; then
  echo "GOOGLE_GEMINI_BASE_URL is required"
  exit 1
fi

PROMPT_CONTENT="$(cat "$PROMPT_FILE")"

npx -y @google/gemini-cli \
  -m "$MODEL" \
  --approval-mode yolo \
  --output-format text \
  -p "$PROMPT_CONTENT"

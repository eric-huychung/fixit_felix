#!/usr/bin/env bash
#
# Run every gate CI runs, and report all failures instead of stopping at the first.
#
# Usage:
#   scripts/check.sh                # lint + tests + web typecheck/lint/build
#   scripts/check.sh --fix          # format and autofix lint first
#   scripts/check.sh --python-only  # skip the web checks
#   scripts/check.sh --no-cov       # skip coverage reporting

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FIX=0
PYTHON_ONLY=0
COV=1
for arg in "$@"; do
  case "$arg" in
    --fix) FIX=1 ;;
    --python-only|--python) PYTHON_ONLY=1 ;;
    --no-cov) COV=0 ;;
    -h|--help) sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Plain string, not an array: bash 3.2 (macOS default) errors on empty array
# expansion under `set -u`.
failures=""

step() {
  local name="$1"; shift
  printf '\n\033[1m-- %s\033[0m\n' "$name"
  if "$@"; then
    printf '\033[32mPASS  %s\033[0m\n' "$name"
  else
    printf '\033[31mFAIL  %s\033[0m\n' "$name"
    failures="${failures}${failures:+, }${name}"
  fi
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

if ! uv sync --quiet; then
  echo "uv sync failed - resolve the environment before running checks." >&2
  exit 1
fi

if [[ $FIX -eq 1 ]]; then
  step "ruff format" uv run ruff format .
  step "ruff lint (fixing)" uv run ruff check . --fix
else
  step "ruff format --check" uv run ruff format --check .
  step "ruff lint" uv run ruff check .
fi

if [[ $COV -eq 1 ]]; then
  step "pytest" uv run pytest -q --cov=felix --cov-report=term-missing
else
  step "pytest" uv run pytest -q
fi

if [[ $PYTHON_ONLY -eq 0 ]]; then
  if command -v npm >/dev/null 2>&1; then
    [[ -d web/node_modules ]] || (cd web && npm install --silent)
    step "web typecheck" npm --prefix web run typecheck
    step "web lint" npm --prefix web run lint
    step "web build" npm --prefix web run build
  else
    printf '\n\033[33mSKIP  web checks (npm not found)\033[0m\n'
  fi
fi

printf '\n'
if [[ -n "$failures" ]]; then
  printf '\033[31mFailed: %s\033[0m\n' "$failures"
  exit 1
fi
printf '\033[32mAll checks passed.\033[0m\n'

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

mkdir -p .shux/out

run_case() {
  local name="$1"
  local command="$2"
  local wait_text="$3"
  local refresh_text="$4"

  shux session kill "$name" >/dev/null 2>&1 || true
  shux session create "$name" -d -- "$command" >/dev/null
  shux pane wait-for -s "$name" --text "$wait_text" --timeout-ms 15000

  shux --format json pane capture -s "$name" > ".shux/out/${name}-capture.json"
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}.png"

  shux pane send-keys -s "$name" --text "r"
  shux pane wait-for -s "$name" --text "$refresh_text" --timeout-ms 15000
  shux pane send-keys -s "$name" --text "?"
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-help.png"
  shux pane send-keys -s "$name" --text "q"
  sleep 0.2
  shux session kill "$name" >/dev/null 2>&1 || true
}

run_case "hews-top-visual" "$ROOT/.shux/scripts/run-fake-tui-top.sh" "Top fixture story" "refreshed"
run_case "hews-search-visual" "$ROOT/.shux/scripts/run-fake-tui-search.sh" "Search fixture story for python" "python refreshed"

printf 'shux visual smoke passed\n'

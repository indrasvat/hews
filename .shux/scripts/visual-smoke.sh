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

  shux pane send-keys -s "$name" --data "DQ=="
  shux pane wait-for -s "$name" --text "This deterministic comment can be upvoted" --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-comments-loaded.png"
  shux pane send-keys -s "$name" --text "u"
  shux pane wait-for -s "$name" --text "Upvoted comment." --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-comment-upvoted.png"
  shux pane send-keys -s "$name" --text "c"
  shux pane wait-for -s "$name" --text "Reply to comment by alice" --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-reply-prompt.png"
  shux pane send-keys -s "$name" --text "Visual reply from shux"
  shux pane send-keys -s "$name" --data "DQ=="
  shux pane wait-for -s "$name" --text "Comment posted." --timeout-ms 15000
  shux pane wait-for -s "$name" --text "Visual reply from shux" --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-reply-posted.png"
  shux pane send-keys -s "$name" --text "b"
  shux pane wait-for -s "$name" --text "$wait_text" --timeout-ms 15000

  shux pane send-keys -s "$name" --text "r"
  shux pane wait-for -s "$name" --text "$refresh_text" --timeout-ms 15000
  shux pane send-keys -s "$name" --text "a"
  shux pane wait-for -s "$name" --text "(ask)" --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-ask.png"
  shux pane send-keys -s "$name" --text "/"
  shux pane wait-for -s "$name" --text "Search HN" --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-search-prompt.png"
  shux pane send-keys -s "$name" --text "database"
  shux pane send-keys -s "$name" --data "DQ=="
  shux pane wait-for -s "$name" --text "Search fixture story for database" --timeout-ms 15000
  shux --format json pane snapshot -s "$name" \
    | jq -r .png_base64 \
    | base64 -d > ".shux/out/${name}-search-results.png"
  shux pane send-keys -s "$name" --data "G1tE"
  shux pane wait-for -s "$name" --text "(ask)" --timeout-ms 15000
  shux pane send-keys -s "$name" --text "?"
  shux pane wait-for -s "$name" --text "Upvote: u | Comment: c" --timeout-ms 15000
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

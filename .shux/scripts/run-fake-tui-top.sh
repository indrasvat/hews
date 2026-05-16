#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec uv run python .shux/scripts/fake_hn_tui.py --section top

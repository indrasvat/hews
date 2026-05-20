#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export HN_USERNAME="${HN_USERNAME:-visual-user}"
export HN_PASSWORD="${HN_PASSWORD:-visual-password}"
exec uv run python .shux/scripts/fake_hn_tui.py --search python

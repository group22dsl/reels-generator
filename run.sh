#!/bin/bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PROJECT="$HOME/Documents/Projects/motivation-reels"

cd "$PROJECT"

echo "=================================="
echo "Starting Motivational Reel Generator"
echo "=================================="

exec "$PROJECT/.venv/bin/python" "$PROJECT/generate.py"

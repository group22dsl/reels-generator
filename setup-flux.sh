#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# Python 3.11 has prebuilt dependencies and matches the existing image environment.
if [ ! -x flux-venv/bin/python ]; then
  python3.11 -m venv flux-venv
fi
flux-venv/bin/python -m pip install -r requirements-flux.txt
flux-venv/bin/mflux-generate-flux2 --help

#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete. Activate the virtualenv and run ./run_tests.sh"
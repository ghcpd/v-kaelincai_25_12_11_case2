#!/usr/bin/env bash
# Setup helper: create venv and install requirements
python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt

echo "To run tests: ./run_tests.sh"
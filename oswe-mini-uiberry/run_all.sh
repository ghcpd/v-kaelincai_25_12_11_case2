#!/usr/bin/env bash
set -euo pipefail
# Convenience wrapper for POSIX environments. On Windows use run_tests.sh directly.
if [ ! -d ".venv" ]; then
  echo "Creating virtualenv and installing requirements..."
  bash setup.sh
fi

bash run_tests.sh

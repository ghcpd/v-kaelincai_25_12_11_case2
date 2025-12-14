#!/usr/bin/env bash

set -e

echo "Running legacy project tests"
pushd ../issue_project
python -m pytest -q | tee ../oswe-mini-prime-270/results/results_legacy.txt
popd

echo "Running new scheduler tests"
./run_tests.sh

echo "Collecting reports"
cp results/tests_output.txt results/report_new.txt || true
cp ../oswe-mini-prime-270/results/results_post.json results/report_new_metrics.json || true


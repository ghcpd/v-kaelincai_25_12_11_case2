# Greenfield Routing Replacement

## Overview
This is a greenfield replacement for the legacy logistics routing system. It uses Bellman-Ford algorithm to handle negative weights correctly.

## How to Run
1. Run setup.ps1 to create venv and install deps.
2. Run run_tests.ps1 to execute tests.
3. Check results/ for outputs.

## Limits
- Assumes no negative cycles in graphs.
- Performance: O(VE) vs Dijkstra's O((V+E)log V).

## Rollout Strategy
- Deploy new code alongside legacy.
- Use feature flag to switch algorithms.
- Monitor latency and correctness.
# Comparison Report

## Correctness Diff
- Legacy: Returns incorrect path A->B cost 5
- New: Returns correct path A->C->D->F->B cost 1

## Latency
- p50: Legacy ~0.01s, New ~0.02s (Bellman-Ford is O(VE))
- p95: Similar

## Errors/Retries
- Legacy: No errors, but wrong result
- New: Detects negative cycles

## Rollout Guidance
- Replace routing.py with new implementation
- Add tests for negative weights
- Monitor for performance on large graphs
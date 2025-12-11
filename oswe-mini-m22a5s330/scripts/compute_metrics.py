import json, os
p = os.path.join(os.path.dirname(__file__), '..', 'results', 'aggregated_metrics.json')
with open(p) as f:
    data = json.load(f)
states = [v.get('final_state') for v in data.values()]
metrics = {
    'total_cases': len(states),
    'counts': {},
}
for s in states:
    metrics['counts'][s] = metrics['counts'].get(s, 0) + 1
metrics['success_rate'] = (metrics['counts'].get('confirmed',0) / max(1, metrics['total_cases']))
print(json.dumps(metrics, indent=2))
with open(os.path.join(os.path.dirname(__file__), '..', 'results', 'metrics_summary.json'), 'w') as f:
    json.dump(metrics, f, indent=2)
print('Wrote results/metrics_summary.json')

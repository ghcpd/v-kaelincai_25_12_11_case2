import json, glob
res={}
for p in glob.glob('**/results_post.json', recursive=True):
    with open(p) as f:
        d=json.load(f)
        res[p]=d

import os
out_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
out_dir = os.path.normpath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'aggregated_metrics.json')
with open(out_path,'w') as f:
    json.dump(res,f,indent=2)
print('Wrote', out_path)

import urllib.request,time,json,sys
from pathlib import Path
out=Path('outputs/page_performance_20261025'); label=sys.argv[1]
results=[]
for path in ['/api/workspace','/api/overview?light=true','/api/documents','/api/dataset?light=true','/api/evaluation?light=true','/api/bad-cases','/api/optimization?light=true','/api/optimization','/api/versions','/api/readiness','/api/monitoring','/api/governance/summary','/api/governance/generation-runs?light=true','/api/governance/candidates']:
 t=time.perf_counter()
 try:
  with urllib.request.urlopen('http://127.0.0.1:8010'+path,timeout=120) as r: body=r.read(); status=r.status
  row={'path':path,'seconds':round(time.perf_counter()-t,4),'bytes':len(body),'status':status}
 except Exception as e: row={'path':path,'seconds':round(time.perf_counter()-t,4),'error':str(e)}
 results.append(row);print(row,flush=True);(out/f'api_{label}.json').write_text(json.dumps(results,indent=2))

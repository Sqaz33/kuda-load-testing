import collections, csv, json, math, pathlib, statistics, subprocess, urllib.parse, urllib.request

ROOT = pathlib.Path('D:/kuda-load-testing')
RUN = pathlib.Path((ROOT/'stand/laptop-current-run.txt').read_text().strip())
OUT = RUN/'go-analysis'
OUT.mkdir(exist_ok=True)
status = json.loads((RUN/'status.json').read_text())
origin = json.loads((RUN/'phases.json').read_text())[0]['stages'][0]['started']
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
queries = {
 'windows_cpu': '100*(1-avg by(job)(rate(windows_cpu_time_seconds_total{mode="idle"}[1m])))',
 'windows_free_memory': 'windows_memory_available_bytes',
 'container_cpu_cores': 'rate(docker_container_cpu_usage_total{cpu="cpu-total"}[1m])/1e9',
 'container_memory': 'docker_container_mem_usage',
 'pool_acquired': 'kuda_db_pool_acquired',
 'pool_wait_seconds_per_second': 'rate(kuda_db_pool_acquire_wait_seconds_total[1m])',
 'wal_sync_seconds': 'rate(kuda_pg_wal_sync_time_seconds_total[20s])/clamp_min(rate(kuda_pg_wal_sync_total[20s]),.001)',
 'waiting_locks': 'kuda_pg_waiting_locks',
 'sse_connections': 'kuda_sse_connections',
}
metrics = {}
for name, query in queries.items():
 params = urllib.parse.urlencode(dict(query=query,start=origin+180,end=origin+600,step=5))
 with opener.open('http://127.0.0.1:9090/api/v1/query_range?'+params,timeout=30) as response:
  rows = json.load(response)['data']['result']
 metrics[name] = rows
(OUT/'prometheus-series.json').write_text(json.dumps(metrics,indent=2))
stats = {}
for name, rows in metrics.items():
 stats[name] = []
 for row in rows:
  values = [float(x[1]) for x in row['values'] if math.isfinite(float(x[1]))]
  if values:
   stats[name].append(dict(labels=row['metric'],mean=statistics.mean(values),min=min(values),max=max(values)))
(OUT/'prometheus-summary.json').write_text(json.dumps(stats,indent=2))
print(json.dumps(stats,indent=2))

# Trace decoding uses the same Go toolchain version as the captured executable.
profile_dir = RUN/'go-profiles'
for kind in ['sched','sync','net','syscall']:
 target = OUT/f'trace-{kind}.pprof'
 with target.open('wb') as out, (OUT/f'trace-{kind}-decode.log').open('wb') as err:
  result = subprocess.run(['docker','run','--rm','-v',str(profile_dir)+':/profiles:ro',
   'golang:1.27.1-alpine','go','tool','trace','-pprof='+kind,'/profiles/execution-trace.out'],stdout=out,stderr=err,timeout=90)
 if result.returncode:
  print('Trace decode failed',kind);continue
 with (OUT/f'trace-{kind}-top.txt').open('w',encoding='utf8') as out:
  subprocess.run(['C:/Program Files/Go/bin/go.exe','tool','pprof','-top','-nodecount=12',str(target)],stdout=out,stderr=subprocess.STDOUT,timeout=30)

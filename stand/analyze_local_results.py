import pathlib,json,csv,math,urllib.request,urllib.parse,concurrent.futures,statistics,re,datetime
R=pathlib.Path('D:/kuda-load-testing/out/20261125-013925-local-capacity');phases=json.loads((R/'phases.json').read_text());out={'windows':[],'sql':{},'logs':{},'gc':{}}
queries={'host_cpu':'100*(1-avg by(job)(rate(windows_cpu_time_seconds_total{mode="idle"}[30s])))','container_cpu_cores':'sum by(com_docker_compose_service)(rate(docker_container_cpu_usage_total{cpu="cpu-total"}[30s]))/1e9','pool_busy':'kuda_db_pool_acquired','pool_wait_seconds_per_second':'rate(kuda_db_pool_acquire_wait_seconds_total[30s])','api_inflight':'kuda_http_requests_inflight','api_mean_seconds':'sum(rate(kuda_http_request_duration_seconds_sum{route=~"/v1/.*"}[30s]))/sum(rate(kuda_http_request_duration_seconds_count{route=~"/v1/.*"}[30s]))','api_rps':'sum(rate(kuda_http_request_duration_seconds_count{route=~"/v1/.*"}[30s]))','free_memory':'windows_memory_available_bytes{job="stand-windows"}','probe':'kuda_network_probe_duration_seconds','go_gc':'rate(go_gc_duration_seconds_sum{job="kuda-api"}[30s])','pg_cache_hit':'100*rate(pg_stat_database_blks_hit{datname="kuda"}[30s])/clamp_min(rate(pg_stat_database_blks_hit{datname="kuda"}[30s])+rate(pg_stat_database_blks_read{datname="kuda"}[30s]),.001)','deadlocks':'pg_stat_database_deadlocks{datname="kuda"}','pg_cpu_throttled':'rate(docker_container_cpu_throttling_throttled_time{com_docker_compose_service="postgres"}[30s])/1e9','api_cpu_throttled':'rate(docker_container_cpu_throttling_throttled_time{com_docker_compose_service="api"}[30s])/1e9'}
for p in phases:
 rows=[r for r in csv.DictReader((R/f"phase-{p['number']}/results.csv").open(encoding='utf-8-sig',newline='')) if r.get('URL','').startswith('http')]
 for i,stage in enumerate(p['stages']):
  end=stage['time'];start=end-60;at=p['started']+i*p['stepSeconds'];ops={};n=err=0;created=0
  for r in rows:
   ts=int(r['timeStamp'])/1000
   if not start<=ts<end:continue
   n+=1;err+=r['success']!='true';path=urllib.parse.urlsplit(r['URL']).path
   if path=='/v1/rooms':key='create';created+=r['success']=='true'
   elif path.endswith('/votes'):key='votes'
   elif path.endswith('/start'):key='start'
   elif path.startswith('/v1/rooms/') and path.count('/')==3:key='read'
   else:continue
   ops.setdefault(key,[]).append(int(r['elapsed']))
  w={'phase':p['number'],'rate':stage['rate'],'start':start,'end':end,'stageStart':at,'secondsSinceStageStart':end-at,'originalVerdict':stage['pass'],'httpRps':n/60,'createdPerMinute':created,'httpErrors':err,'critical':{k:{'samples':len(v),'p95ms':sorted(v)[math.ceil(.95*len(v))-1],'meanMs':statistics.mean(v),'maxMs':max(v)} for k,v in ops.items()}}
  out['windows'].append(w)
# Extract exact SQL profile and distinguish monitoring SQL from application SQL.
sql=list(csv.DictReader((R/'stand-logs/pg-stat-statements.csv').open(encoding='utf-8-sig',newline='')))
app=[r for r in sql if r.get('calls') and not any(x in r.get('query','') for x in ['pg_stat_','pg_settings','pg_locks','pg_database_size','pg_extension'])]
total=sum(float(r['total_exec_time']) for r in app)
for tag,needle in [('catalog','FROM venues v JOIN cities'),('room_lock','FOR UPDATE OF s'),('swipe_upserts','INSERT INTO swipes'),('candidate_upserts','INSERT INTO session_candidates'),('advisory_lock','pg_advisory_xact_lock')]:
 r=next((r for r in app if needle in r['query']),None)
 if r:out['sql'][tag]={k:(r[k] if k=='query' else float(r[k])) for k in ['calls','rows','total_exec_time','mean_exec_time','max_exec_time','shared_blks_hit','shared_blks_read','query']};out['sql'][tag]['percent_app_exec_time']=float(r['total_exec_time'])/total*100
pg=(R/'stand-logs/postgres.log').read_text(encoding='utf-8-sig',errors='replace');lines=pg.splitlines()
wait=[l for l in lines if 'still waiting for' in l];acquired=[l for l in lines if 'acquired' in l and ' after ' in l]
out['logs']={'postgresWaitCount':len(wait),'postgresAcquiredAfterWaitCount':len(acquired),'waitExamples':wait[:5],'acquiredExamples':acquired[:5],'deadlockLines':sum('deadlock detected' in l.lower() for l in lines)}
for p in phases:
 gc=(R/f"phase-{p['number']}/gc.log").read_text(errors='replace');times=[float(v) for v in re.findall(r', (\d+\.\d+) secs\]',gc)]
 out['gc'][str(p['number'])]={'count':len(times),'maxPauseSeconds':max(times,default=0),'sumPauseSeconds':sum(times),'fullGcCount':gc.count('[Full GC')}
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def fetch(t):
 wi,key,q=t;w=out['windows'][wi]
 try:
  data=json.load(op.open('http://127.0.0.1:9090/api/v1/query_range?'+urllib.parse.urlencode({'query':q,'start':w['start'],'end':w['end'],'step':5}),timeout=20))['data']['result'];result=[]
  for s in data:
   values=[float(v[1]) for v in s['values'] if v[1] not in ['NaN','+Inf','-Inf']]
   if values:result.append({'labels':s['metric'],'mean':statistics.mean(values),'min':min(values),'max':max(values)})
  return wi,key,result
 except Exception as e:return wi,key,{'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 for wi,key,result in ex.map(fetch,[(i,k,q) for i in range(len(out['windows'])) for k,q in queries.items()]):out['windows'][wi].setdefault('metrics',{})[key]=result
(R/'analysis-evidence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
for w in out['windows']:
 print('WINDOW',w['phase'],w['rate'],'age',round(w['secondsSinceStageStart']),'RPS',round(w['httpRps'],1),'p95ms',{k:v['p95ms'] for k,v in w['critical'].items()})
 for key in ['host_cpu','container_cpu_cores','pool_busy','pool_wait_seconds_per_second','api_mean_seconds','api_inflight']:
  print(key,[(x['labels'],round(x['mean'],3),round(x['max'],3)) for x in w['metrics'][key]])
print('SQL',json.dumps({k:{x:v[x] for x in v if x!='query'} for k,v in out['sql'].items()},ensure_ascii=False))
print('LOGS',json.dumps(out['logs'],ensure_ascii=False));print('GC',out['gc'])

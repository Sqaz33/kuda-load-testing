"""Save observed resource evidence for each stage of the current local run."""
import collections
import concurrent.futures
import datetime
import json
import math
import pathlib
import re
import statistics
import subprocess
import time
import urllib.parse
import urllib.request

stand=pathlib.Path(__file__).parent
run=pathlib.Path((stand/'local-current-run.txt').read_text().strip())
output=run/'analysis'
output.mkdir(exist_ok=True)
phases=json.loads((run/'phases.json').read_text(encoding='utf8'))[0]
stages=phases['stages']
start=stages[0]['started']
end=min(time.time(),stages[-1].get('finished',time.time()))
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
queries={
 'host_cpu_percent':'100*(1-avg(rate(windows_cpu_time_seconds_total{job="stand-windows",mode="idle"}[30s])))',
 'host_available_mib':'windows_memory_available_bytes{job="stand-windows"}/1024/1024',
 'host_commit_percent':'100*windows_memory_committed_bytes{job="stand-windows"}/windows_memory_commit_limit_bytes{job="stand-windows"}',
 'swap_pages_in_per_second':'rate(windows_memory_swap_pages_read_total{job="stand-windows"}[30s])',
 'swap_pages_out_per_second':'rate(windows_memory_swap_pages_written_total{job="stand-windows"}[30s])',
 'process_cpu_cores':'sum by(process)(rate(windows_process_cpu_time_seconds_total{job="stand-windows"}[30s]))',
 'container_cpu_cores':'sum by(container_name)(rate(docker_container_cpu_usage_total{job="stand-docker",cpu="cpu-total"}[30s]))/1e9',
 'container_memory_mib':'docker_container_mem_usage{job="stand-docker"}/1024/1024',
 'db_pool_acquired':'kuda_db_pool_acquired{job="kuda-api"}',
 'db_pool_wait_seconds_per_second':'rate(kuda_db_pool_acquire_wait_seconds_total{job="kuda-api"}[30s])',
 'db_activity':'sum by(type,event)(kuda_pg_activity{state="active"})',
 'wal_fsync_ms':'1000*rate(kuda_pg_wal_sync_time_seconds_total[30s])/clamp_min(rate(kuda_pg_wal_sync_total[30s]),.001)',
 'wal_fsyncs_per_second':'rate(kuda_pg_wal_sync_total[30s])',
 'wal_mib_per_second':'rate(kuda_pg_wal_bytes_total[30s])/1024/1024',
 'disk_write_ms':'1000*rate(windows_physical_disk_write_seconds_total{job="stand-windows"}[30s])/clamp_min(rate(windows_physical_disk_writes_total{job="stand-windows"}[30s]),.001)',
 'disk_queue':'windows_physical_disk_requests_queued{job="stand-windows"}',
 'go_gc_seconds_per_second':'rate(go_gc_duration_seconds_sum{job="kuda-api"}[30s])',
 'go_heap_mib':'go_memstats_heap_alloc_bytes{job="kuda-api"}/1024/1024',
 'room_creates_per_minute':'sum(rate(kuda_http_request_duration_seconds_count{job="kuda-api",route="/v1/rooms",method="POST",status=~"2.."}[1m]))*60',
 'sse_streams':'kuda_test_active_streams',
 'member_queue':'kuda_test_member_queue',
 'sse_queue':'kuda_test_poll_queue',
}
def fetch(item):
    name,query=item
    params=urllib.parse.urlencode({'query':query,'start':start,'end':end,'step':10})
    data=json.load(opener.open('http://127.0.0.1:9090/api/v1/query_range?'+params,timeout=30))
    if data['status']!='success':raise RuntimeError(data)
    return name,data['data']['result']
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    raw=dict(pool.map(fetch,queries.items()))
(output/'prometheus-evidence.json').write_text(json.dumps({'queries':queries,'series':raw},ensure_ascii=False),encoding='utf8')
report=[]
def distribution(values):
    values=sorted(values)
    if not values:return None
    return {'mean':round(statistics.mean(values),3),'p95':round(values[max(0,math.ceil(len(values)*.95)-1)],3),
            'min':round(values[0],3),'max':round(values[-1],3)}
for stage in stages:
    a,b=stage['started'],stage.get('finished',end)
    entry={'rate':stage['rate'],'outcome':stage.get('outcome'),'started':a,'finished':b,'metrics':{}}
    for name,series in raw.items():
        summaries=[]
        for metric in series:
            values=[float(v) for t,v in metric['values'] if a<=float(t)<=b and math.isfinite(float(v))]
            if values:summaries.append({'labels':metric['metric'],**distribution(values)})
        if name=='process_cpu_cores':summaries=sorted(summaries,key=lambda row:row['mean'],reverse=True)[:8]
        entry['metrics'][name]=summaries
    report.append(entry)
(output/'stage-resources.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')

gc=(run/'phase-1/gc.log').read_text(encoding='utf8',errors='replace')
pauses=[(float(a),float(b)) for a,b in re.findall(r'(?m)^(\d+\.\d+): \[(?:GC pause|Full GC).*?, ([\d.]+) secs\]',gc)]
origin=phases.get('ramp',{}).get('started',phases['started'])
gc_report=[]
for stage in stages:
    values=[pause for at,pause in pauses if stage['started']<=origin+at<=stage.get('finished',end)]
    gc_report.append({'rate':stage['rate'],'pauses':len(values),'totalSeconds':round(sum(values),3), 'duration':distribution(values)})
(output/'jmeter-gc.json').write_text(json.dumps(gc_report,indent=2),encoding='utf8')

since=datetime.datetime.fromtimestamp(phases['started'],datetime.timezone.utc).isoformat()
logs=subprocess.check_output(['docker','logs','--timestamps','--since',since,'kuda-backend-postgres-1'],stderr=subprocess.STDOUT).decode('utf8',errors='replace')
(output/'postgres-during-analysis.log').write_text(logs,encoding='utf8')
lines=logs.splitlines()
shm=[]
for index,line in enumerate(lines):
    if 'ERROR:' in line and ('shared memory' in line or 'No space' in line):
        shm.append('\n'.join(lines[index:index+3]))
(output/'shared-memory-errors.json').write_text(json.dumps(shm,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'run':str(run),'stages':[(r['rate'],r['outcome']) for r in report],
                  'gc':gc_report,'sharedMemoryErrors':len(shm),'firstSharedMemoryErrors':shm[:2]},ensure_ascii=False))
for row in report:
    print('RATE',row['rate'])
    for name in ('host_cpu_percent','host_available_mib','host_commit_percent','swap_pages_in_per_second','swap_pages_out_per_second','container_cpu_cores','container_memory_mib','db_pool_acquired','db_pool_wait_seconds_per_second','db_activity','wal_fsync_ms','disk_write_ms','disk_queue','process_cpu_cores'):
        print(name,json.dumps(row['metrics'][name],ensure_ascii=False))

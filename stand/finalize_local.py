"""Bundle immutable run evidence, reports and a restorable Prometheus snapshot."""
import collections,csv,datetime,hashlib,json,math,pathlib,shutil,subprocess,sys,time,urllib.request,urllib.parse
ROOT=pathlib.Path('D:/kuda-load-testing');STAND=ROOT/'stand'
PWSH=shutil.which('pwsh') or 'powershell'
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
RUN=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path((STAND/'latest-run.txt').read_text().strip())
status=json.loads((RUN/'status.json').read_text(encoding='utf8'))
if status.get('running'):raise SystemExit('The load test is still running')
phases=json.loads((RUN/'phases.json').read_text(encoding='utf8'))
shutil.copytree(STAND,RUN/'configuration',ignore=shutil.ignore_patterns('*.tar','*.exe','__pycache__','active.*','latest-run.txt','*-metrics.txt','*.log','inspect*','concurrency-template.jmx'),dirs_exist_ok=True)
subprocess.run(['git','-C','D:/venue-backend','rev-parse','HEAD'],stdout=(RUN/'backend-commit.txt').open('w'))
subprocess.run(['git','-C','D:/venue-backend','diff'],stdout=(RUN/'backend-changes.patch').open('w',encoding='utf8'))
shutil.copy2('D:/venue-backend/Dockerfile.local',RUN/'configuration/Dockerfile.local')

samples=collections.defaultdict(list);totals=collections.defaultdict(lambda:collections.Counter());rooms=[];helper_errors=[]
header=None;first=10**20;last=0;errors=0;count=0
with (RUN/'results.csv').open('w',encoding='utf8',newline='') as out:
    writer=None
    for phase in phases:
        if phase.get('calibration'):continue
        folder=pathlib.Path(phase['directory'])
        with (folder/'results.csv').open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            if writer is None:header=reader.fieldnames;writer=csv.DictWriter(out,fieldnames=header);writer.writeheader()
            for r in reader:
                if not r.get('URL','').startswith('http'):
                    if r.get('success')=='false':helper_errors.append(r)
                    continue
                writer.writerow(r);label=r['label'];duration=int(r['elapsed']);start=int(r['timeStamp']);end=start+duration
                samples[label].append(duration);samples['TOTAL'].append(duration)
                ok=r['success']=='true';errors+=not ok;count+=1;first=min(first,start);last=max(last,end)
                for key in (label,'TOTAL'):
                    a=totals[key];a['count']+=1;a['errors']+=not ok;a['bytes']+=int(r['bytes']);a['sentBytes']+=int(r.get('sentBytes') or 0)
                    a['first']=min(a.get('first',start),start);a['last']=max(a.get('last',end),end)
        with (folder/'rooms.csv').open(encoding='utf-8-sig',newline='') as f:rooms.extend(csv.DictReader(f))
with (RUN/'rooms.csv').open('w',encoding='utf8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['roomId','result','winnerId','elapsedMs','reason']);w.writeheader();w.writerows(rooms)
with (RUN/'scenario-errors.csv').open('w',encoding='utf8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=header or []);w.writeheader();w.writerows(helper_errors)

def quantile(v,q):return v[max(0,math.ceil(len(v)*q)-1)]
aggregate=[]
for label,values in sorted(samples.items(),key=lambda pair:pair[0]=='TOTAL'):
    values.sort();a=totals[label];seconds=max(.001,(a['last']-a['first'])/1000)
    aggregate.append({'Label':label,'# Samples':len(values),'Average':round(sum(values)/len(values),2),'Median':quantile(values,.5),'90% Line':quantile(values,.9),'95% Line':quantile(values,.95),'99% Line':quantile(values,.99),'Min':values[0],'Max':values[-1],'Error %':round(a['errors']/a['count']*100,4),'Throughput':round(a['count']/seconds,3),'Received KB/sec':round(a['bytes']/1024/seconds,3),'Sent KB/sec':round(a['sentBytes']/1024/seconds,3)})
if aggregate:
    with (RUN/'aggregate.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=aggregate[0].keys());w.writeheader();w.writerows(aggregate)

summary={'run':RUN.name,'status':status,'httpSamples':count,'httpErrors':errors,'roomCount':len(rooms),'successfulRooms':sum(r['result']=='success' for r in rooms),'failedRooms':sum(r['result']!='success' for r in rooms),'helperErrorCount':len(helper_errors),'phases':phases,'aggregate':aggregate,'excludedCalibrationPhases':[p['number'] for p in phases if p.get('calibration')],'measurementNote':'Only HTTP samples from measured phases are in combined results.csv; original phase files retain calibration, Transaction Controller and helper samples. Capacity verdict uses steady rolling windows, not the whole-run aggregate.'}
(RUN/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')

# Export the metrics in a native, restorable snapshot after the final stopped metric was scraped.
if not (RUN/'prometheus-snapshot.json').exists():
    time.sleep(15)
    request=urllib.request.Request('http://127.0.0.1:9090/api/v1/admin/tsdb/snapshot',data=b'',method='POST')
    snapshot=json.load(urllib.request.urlopen(request,timeout=60))['data']['name']
    flags=json.load(urllib.request.urlopen('http://127.0.0.1:9090/api/v1/status/flags',timeout=15))['data']
    workdir=subprocess.check_output(['docker','inspect','kuda-monitoring-prometheus-1','--format','{{.Config.WorkingDir}}'],text=True).strip()
    storage=pathlib.PurePosixPath(flags['storage.tsdb.path'])
    if not storage.is_absolute():storage=pathlib.PurePosixPath(workdir)/storage
    subprocess.run(['docker','exec','kuda-monitoring-prometheus-1','tar','czf','/tmp/kuda-metrics.tar.gz','-C',str(storage/'snapshots'),snapshot],check=True)
    subprocess.run(['docker','cp','kuda-monitoring-prometheus-1:/tmp/kuda-metrics.tar.gz',str(RUN/'prometheus-snapshot.tar.gz')],check=True)
    (RUN/'prometheus-snapshot.json').write_text(json.dumps({'snapshot':snapshot,'runStart':status['started'],'runEnd':status.get('ended'),'retentionDays':15}),encoding='utf8')

# Save local container logs and SQL profiles without SSH.
logs=RUN/'stand-logs';logs.mkdir(exist_ok=True)
since=datetime.datetime.fromtimestamp(status['started'],datetime.timezone.utc).isoformat()
until=datetime.datetime.fromtimestamp(status.get('ended',time.time()),datetime.timezone.utc).isoformat()
for service in ['api','postgres','redis','postgres-exporter']:
    name='kuda-backend-'+service+'-1'
    with (logs/(service+'.log')).open('wb') as f:
        subprocess.run(['docker','logs','--timestamps','--since',since,'--until',until,name],stdout=f,stderr=subprocess.STDOUT,check=True)
    with (logs/(service+'-inspect.json')).open('wb') as f:
        subprocess.run(['docker','inspect',name],stdout=f,check=True)
sql="COPY (SELECT queryid,calls,total_exec_time,mean_exec_time,max_exec_time,rows,shared_blks_hit,shared_blks_read,temp_blks_written,query FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) ORDER BY total_exec_time DESC LIMIT 200) TO STDOUT WITH CSV HEADER"
if not (logs/'pg-stat-statements.csv').exists():
    with (logs/'pg-stat-statements.csv').open('wb') as f:
        subprocess.run(['docker','exec','kuda-backend-postgres-1','psql','-X','-U','kuda','-d','kuda','-c',sql],stdout=f,check=True)
for source in ['compose.yaml']:
    shutil.copy2(pathlib.Path('D:/venue-backend')/source,logs/source)
shutil.copy2(STAND/'compose.desktop.yaml',logs/'compose.desktop.yaml')
shutil.copy2(STAND/'telegraf.desktop.conf',logs/'telegraf.desktop.conf')
import zipfile
with zipfile.ZipFile(RUN/'stand-logs.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in logs.iterdir():z.write(f,f.name)

# Generate the standard JMeter HTML dashboard from the combined HTTP CSV.
command=['D:/apache-jmeter-5.6.3/bin/jmeter.bat','-g',str(RUN/'results.csv'),'-o',str(RUN/'report'),'-j',str(RUN/'report-generation.log'),'-Jjmeterengine.force.system.exit=true']
with (RUN/'report-generation-console.log').open('w') as f:
    report=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=300)
if report.returncode or not (RUN/'report/index.html').exists():raise RuntimeError('JMeter HTML report generation failed')

start_ms=int(status['started']*1000);end_ms=int(status.get('ended',time.time())*1000)
url=f'http://localhost:3001/d/kuda-load-test?from={start_ms}&to={end_ms}'
if status.get('kind')=='fixed_diagnostic':
    profile_notes='''Fixed diagnostic profile: 100 rooms/min for 240 seconds, then 240 rooms/min for 360 seconds.
The transition uses one JMeter engine without a pause. Final room drain follows the 600-second arrival schedule.
The test continues for the requested duration when SLA is exceeded. This run does not search for a maximum.
Database/WAL/wait samples and Linux pressure/cgroup counters: db-diagnostics.jsonl.
'''
else:
    criteria=json.loads((RUN/'criteria.json').read_text(encoding='utf8'))
    profile_notes=(f"Ramp: {criteria['rampSeconds']} seconds to {criteria['firstStageRoomsPerMinute']} rooms/min.\n"
                   f"First hold: {criteria['initialStageSeconds']} seconds.\n"
                   f"Stages: {criteria['stageSeconds']} seconds, increase by {criteria['increaseStepRoomsPerMinute']} rooms/min, ceiling {criteria['maximumProbeRate']}.\n"
                   "After a failed candidate capacity_policy.py bisects the bounds to 1 room/min and confirms the passing rate.\n"
                   f"SLA mode: {criteria['slaMode']}. {criteria['slaEvaluation']}\n")
notes=f'''Local Kuda load test: {RUN.name}
Grafana: {url}
Target API: http://127.0.0.1:8787 (this PC).
The backend and JMeter share the same Windows host and CPU/RAM.
{profile_notes}
Existing rooms continue between stages; active rooms drain only at the end of the test.
maximumConfirmed in status.json distinguishes confirmation from a budget/resource limit.
SLA and exact run configuration: criteria.json, status.json, phases.json.
Combined HTTP results: results.csv. Full room results: rooms.csv.
JMeter HTML dashboard: report/index.html. SQL profile: stand-logs/pg-stat-statements.csv.
Raw phase files include JMX, runtime properties, CSV/XML and JMeter/GC logs.
Server logs: stand-logs.zip. Metrics: prometheus-snapshot.tar.gz.
Final passing level: {status.get('lastPassingRoomsPerMinute')} rooms/min.
First failing level: {status.get('firstFailingRoomsPerMinute')} rooms/min.
An absent failing level means the service maximum was not bracketed.
The total host CPU load includes both target and generator; it is not a generator-only limit.
No remote services or remote maintenance settings are changed by this run.
'''
(RUN/'README.txt').write_text(notes,encoding='utf8')
(STAND/'links.txt').write_text(url+'\nhttp://localhost:9090\n',encoding='utf8')
manifest={}
for p in RUN.rglob('*'):
    if p.is_file() and p.name not in ('manifest-sha256.json','DONE.json'):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        manifest[str(p.relative_to(RUN))]={'sha256':h.hexdigest(),'bytes':p.stat().st_size}
(RUN/'manifest-sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
(RUN/'DONE.json').write_text(json.dumps({'finished':time.time(),'artifactsReady':True,'grafanaUrl':url,'httpSamples':count,'rooms':len(rooms)},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'run':str(RUN),'grafana':url,'httpSamples':count,'rooms':len(rooms),'status':status['status']},ensure_ascii=False),flush=True)

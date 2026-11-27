"""Bundle immutable run evidence, reports and a restorable Prometheus snapshot."""
import collections,csv,datetime,hashlib,json,math,pathlib,shutil,subprocess,sys,time,urllib.request,urllib.parse
ROOT=pathlib.Path('D:/kuda-load-testing');STAND=ROOT/'stand'
PWSH=shutil.which('pwsh') or 'powershell'
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
RUN=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path((STAND/'latest-run.txt').read_text().strip())
status=json.loads((RUN/'status.json').read_text(encoding='utf8'))
if status.get('running'):raise SystemExit('The load test is still running')
if not (RUN/'maintenance-restored.json').exists():
    subprocess.run([PWSH,'-NoProfile','-File',str(STAND/'remote.ps1'),'ps',str(STAND/'restore-maintenance.ps1')],check=True)
    subprocess.run([PWSH,'-NoProfile','-File',str(STAND/'remote.ps1'),'get','C:/Users/mset6/kuda-nt/maintenance-restored.json',str(RUN/'maintenance-restored.json')],check=True)
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

# Fetch logs and query profiles over the already authorized SSH connection.
if not (RUN/'stand-logs/pg-stat-statements.csv').exists():
    subprocess.run([PWSH,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(STAND/'collect-stand.ps1'),'-RunDirectory',str(RUN)],check=True)

# Generate the standard JMeter HTML dashboard from the combined HTTP CSV.
command=['D:/apache-jmeter-5.6.3/bin/jmeter.bat','-g',str(RUN/'results.csv'),'-o',str(RUN/'report'),'-j',str(RUN/'report-generation.log'),'-Jjmeterengine.force.system.exit=true']
with (RUN/'report-generation-console.log').open('w') as f:
    report=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=300)
if report.returncode or not (RUN/'report/index.html').exists():raise RuntimeError('JMeter HTML report generation failed')

start_ms=int(status['started']*1000);end_ms=int(status.get('ended',time.time())*1000)
url=f'http://localhost:3001/d/kuda-load-test?from={start_ms}&to={end_ms}'
notes=f'''Куда — материалы прогона {RUN.name}

Grafana: {url}
Prometheus: http://localhost:9090
Swagger стенда: http://192.168.0.213:8787/docs/
Grafana: admin / admin1 (существующая локальная учётная запись).

Нагрузка завершена. status.json содержит running=0 и статус остановки.
DONE.json означает, что сохранены также логи, метрики и отчёт.
Максимальный прошедший уровень: {status.get('lastPassingRoomsPerMinute')} комнат/мин.
Первый не прошедший уровень: {status.get('firstFailingRoomsPerMinute')} комнат/мин.
Это измеренная граница в заданном профиле и с рабочими критериями criteria.json.
Пустая верхняя граница означает, что максимум системы не подтверждён.
Профиль: 4 участника, 12 карточек, фоновые чтения с паузой 4 с, экран комнаты 180 с.
Интенсивность организаторов задаётся независимо от времени ответа.
Участники и фоновые запросы используют растущие динамические пулы потоков.
Сохранена бизнес-логика первоначального тест-плана; все Groovy-скрипты внутри JMX.

Основные файлы:
  report/index.html — стандартный HTML-отчёт JMeter.
  results.csv — объединённые результаты отдельных HTTP-запросов.
  aggregate.csv — сводка Average, Median, p90, p95, p99, ошибки и интенсивность.
  rooms.csv — исход каждого полного бизнес-сценария комнаты.
  phases.json, monitor.jsonl, events.jsonl — ступени, контроль и причины остановок.
  phase-*/ — исходные результаты, ошибки XML, логи JMeter/GC и копии JMX/параметров.
  stand-logs/ — API, PostgreSQL, Redis, экспортеры, ресурсы, события Windows.
  stand-logs/pg-stat-statements.csv — профиль нормализованных SQL-запросов.
  prometheus-snapshot.tar.gz — снимок хранилища метрик для последующего восстановления.
  configuration/ — конфигурации стенда, мониторинга и Grafana.
  backend-commit.txt и backend-changes.patch — версия и изменения бэкенда ветки nt.

Стенд: 192.168.0.213, i3-10110U, 2 ядра / 4 логических CPU, 8 ГБ RAM,
Windows 11, Docker Desktop / WSL2 (4 CPU, около 3.75 ГиБ памяти).
Сеть: генератор — Ethernet 1 Гбит/с; стенд — Wi-Fi, соединение 650 Мбит/с.
Скорость подключения Wi-Fi не является измеренной полезной пропускной способностью.
Лимиты памяти: API 1 ГиБ, PostgreSQL 1500 МиБ, Redis 128 МиБ.
Пул соединений API к PostgreSQL: исходные 10 соединений.
Windows/WSL и сетевые задержки являются частью результатов этого стенда.
API и БД пишут журналы в Docker с ротацией до 10 файлов по 100 МБ.
Медленные SQL: от 250 мс, также включены журнал ожидания блокировок и pg_stat_statements.

Повторно забрать логи:
  powershell -File D:\\kuda-load-testing\\stand\\collect-stand.ps1 -RunDirectory "{RUN}"
SSH-пароль хранится отдельно от проекта в шифрованном виде Windows DPAPI.
Настройки и данные стенда сохраняются в C:\\Users\\mset6\\kuda-nt на удалённом ПК.
После перезагрузки удалённого ПК нужен запущенный Docker Desktop.
Мониторинг оставлен включённым. Нагрузочный генератор остановлен.
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

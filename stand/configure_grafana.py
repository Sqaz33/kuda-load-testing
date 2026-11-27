import os
import base64,json,pathlib,urllib.request
ROOT=pathlib.Path(__file__).parent
AUTH='Basic '+base64.b64encode((os.environ.get('KUDA_GRAFANA_USER','admin')+':'+os.environ['KUDA_GRAFANA_PASSWORD']).encode()).decode()
def api(method,path,data=None):
    req=urllib.request.Request('http://127.0.0.1:3001/api/'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':AUTH,'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=20))
ds={'name':'Куда Prometheus','uid':'kuda-prometheus','type':'prometheus','access':'proxy','url':'http://127.0.0.1:9090','jsonData':{'httpMethod':'POST','timeInterval':'10s'}}
try: api('POST','datasources',ds)
except urllib.error.HTTPError as e:
    if e.code!=409:raise
    api('PUT','datasources/uid/kuda-prometheus',ds)

PANELS=[];Y=0;ID=0
def row(title):
    global Y,ID
    ID+=1;PANELS.append({'id':ID,'type':'row','title':title,'collapsed':False,'gridPos':{'x':0,'y':Y,'w':24,'h':1}});Y+=1
def panel(title,queries,unit='short',stat=False,description='',threshold=None):
    global Y,ID
    ID+=1
    # Three panels per row; full-width rows reset this position naturally.
    x=sum(p['type']!='row' and p['gridPos']['y']==Y for p in PANELS)*8
    if x>=24:Y+=8;x=0
    defaults={'unit':unit,'color':{'mode':'palette-classic'},'custom':{'drawStyle':'line','lineWidth':1,'fillOpacity':10,'showPoints':'never'},'thresholds':{'mode':'absolute','steps':[{'color':'green','value':None}]+([{'color':'red','value':threshold}] if threshold else [])}}
    p={'id':ID,'type':'stat' if stat else 'timeseries','title':title,'description':description,'gridPos':{'x':x,'y':Y,'w':8,'h':8},'datasource':{'type':'prometheus','uid':'kuda-prometheus'},'targets':[{'expr':q,'legendFormat':legend,'refId':chr(65+i)} for i,(q,legend) in enumerate(queries)],'fieldConfig':{'defaults':defaults,'overrides':[]},'options':{'legend':{'displayMode':'table','placement':'bottom','calcs':['lastNotNull','max']},'tooltip':{'mode':'multi'}}}
    if stat:p['options']={'reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'colorMode':'value','graphMode':'area','textMode':'auto'}
    PANELS.append(p)
def nextrow(title):
    global Y
    if PANELS and PANELS[-1]['type']!='row':Y+=8
    row(title)

row('Прогон — состояние и подача нагрузки')
panel('Тест работает: 1 — да, 0 — остановлен',[('kuda_test_running','работает')],stat=True)
panel('Тест завершён: 1 — да',[('kuda_test_finished','завершён')],stat=True)
panel('До предельного окончания',[('clamp_min(kuda_test_deadline_timestamp_seconds-time(),0)','осталось')],'s',True)
panel('Ступени — комнат в минуту',[('kuda_test_target_rooms_per_minute','план'),('sum(rate(kuda_http_request_duration_seconds_count{route="/v1/rooms",method="POST",status=~"2.."}[2m]))*60','факт создания')])
panel('Компании: запущено / завершено / ошибки',[('kuda_test_started_rooms','запущено'),('kuda_test_completed_rooms','успешно'),('kuda_test_failed_rooms','ошибки'),('kuda_test_active_rooms','активно')])
panel('Очереди генератора',[('kuda_test_member_queue','участники'),('kuda_test_poll_queue','опрос')],description='Постоянный рост означает нехватку рабочих потоков генератора.')
panel('Возраст заданий в очереди',[('kuda_test_member_queue_oldest_seconds','участники'),('kuda_test_poll_queue_oldest_seconds','опрос')],'s',threshold=10)
panel('RPS — клиент и сервер',[('sum(rate(jmeter_http_requests_total[1m]))','JMeter завершённые HTTP'),('sum(rate(kuda_http_request_duration_seconds_count{route=~"/v1/.*"}[1m]))','API завершённые')],'reqps')
panel('Ошибки HTTP и проверок JMeter',[('100*sum(rate(jmeter_http_requests_total{success="false"}[2m]))/clamp_min(sum(rate(jmeter_http_requests_total[2m])),0.001)','ошибки, %')],'percent',threshold=.1)
nextrow('Ответы сервиса — клиентские измерения и SLA')
panel('p95 по операциям API — JMeter',[('histogram_quantile(.95,sum by(le,operation)(rate(jmeter_operation_duration_seconds_bucket[2m])))','{{operation}}')],'s',threshold=.5)
panel('p50 / p95 / p99 всех HTTP',[('histogram_quantile(.50,sum by(le)(rate(jmeter_http_duration_seconds_bucket[2m])))','p50'),('histogram_quantile(.95,sum by(le)(rate(jmeter_http_duration_seconds_bucket[2m])))','p95'),('histogram_quantile(.99,sum by(le)(rate(jmeter_http_duration_seconds_bucket[2m])))','p99')],'s')
panel('RPS по операциям',[('sum by(label)(rate(jmeter_http_requests_total[1m]))','{{label}}')],'reqps')
panel('p95 обработки на сервере',[('histogram_quantile(.95,sum by(le,route)(rate(kuda_http_request_duration_seconds_bucket[2m])))','{{route}}')],'s')
panel('Коды ответа API',[('sum by(status)(rate(kuda_http_request_duration_seconds_count{route=~"/v1/.*"}[1m]))','{{status}}')],'reqps')
panel('Запросов одновременно на сервере',[('kuda_http_requests_inflight','обрабатываются')])
nextrow('Стенд Windows / WSL и отдельные контейнеры')
panel('CPU Windows — стенд и генератор',[('100*(1-avg by(job)(rate(windows_cpu_time_seconds_total{mode="idle"}[1m])))','{{job}}')],'percent',threshold=85)
panel('Свободная память Windows',[('windows_memory_available_bytes','{{job}}')],'bytes')
panel('CPU контейнеров — занятые ядра',[('rate(docker_container_cpu_usage_total{cpu="cpu-total"}[1m])/1e9','{{container_name}}')],'short',description='1 = одно логическое ядро. Локальному Docker доступны 12 логических процессоров.')
panel('Память контейнеров',[('docker_container_mem_usage','{{container_name}}')],'bytes')
panel('Лимит памяти контейнеров, %',[('docker_container_mem_usage_percent','{{container_name}}')],'percent',threshold=85)
panel('Перезапуски и OOM',[('docker_container_status_restart_count','{{container_name}} перезапуски'),('docker_container_status_oomkilled','{{container_name}} OOM')])
panel('Сеть контейнеров — байт/с',[('rate(docker_container_net_rx_bytes{network="total"}[1m])','{{container_name}} RX'),('rate(docker_container_net_tx_bytes{network="total"}[1m])','{{container_name}} TX')],'Bps')
panel('Диск контейнеров — байт/с',[('rate(docker_container_blkio_io_service_bytes_recursive_read{device="total"}[1m])','{{container_name}} чтение'),('rate(docker_container_blkio_io_service_bytes_recursive_write{device="total"}[1m])','{{container_name}} запись')],'Bps')
panel('Сеть Windows — байт/с',[('rate(windows_net_bytes_received_total{job="stand-windows"}[1m])','{{nic}} RX'),('rate(windows_net_bytes_sent_total{job="stand-windows"}[1m])','{{nic}} TX')],'Bps')
panel('Свободное место на стенде',[('windows_logical_disk_free_bytes{job="stand-windows"}','{{volume}}')],'bytes')
panel('Средняя задержка физического диска',[('rate(windows_physical_disk_read_seconds_total{job="stand-windows"}[1m])/clamp_min(rate(windows_physical_disk_reads_total{job="stand-windows"}[1m]),.001)','{{disk}} чтение'),('rate(windows_physical_disk_write_seconds_total{job="stand-windows"}[1m])/clamp_min(rate(windows_physical_disk_writes_total{job="stand-windows"}[1m]),.001)','{{disk}} запись')],'s')
panel('Go — горутины и GC',[('go_goroutines{job="kuda-api"}','горутины'),('rate(go_gc_duration_seconds_sum{job="kuda-api"}[1m])*100','GC % времени')])
panel('Фоновые процессы Windows — занятые ядра',[('sum by(process)(rate(windows_process_cpu_time_seconds_total{job="stand-windows"}[1m]))','{{process}}')])
panel('Системные службы Windows — по PID',[('sum by(process_id)(rate(windows_process_cpu_time_seconds_total{job="stand-windows",process="svchost"}[1m]))','PID {{process_id}}')])
panel('Проверка HTTP по локальной сети',[('kuda_network_probe_duration_seconds','/health: сеть + Docker + минимальная обработка')],'s',description='Отдельный лёгкий запрос каждые 5 секунд. Это не чистый ping и не замер полосы сети.')
nextrow('PostgreSQL и пул соединений бэкенда')
panel('Пул соединений — занято / всего / лимит',[('kuda_db_pool_acquired','занято'),('kuda_db_pool_connections','создано'),('kuda_db_pool_max','лимит')])
panel('Получение соединения — суммарное время/с',[('rate(kuda_db_pool_acquire_wait_seconds_total[1m])','секунд получения / секунду')],'s',description='Включает и немедленное получение, и ожидание; рост при заполненном пуле указывает на очередь к БД.')
panel('Соединения PostgreSQL',[('pg_stat_database_numbackends{datname="kuda"}','соединения')])
panel('Транзакции БД — commit / rollback',[('rate(pg_stat_database_xact_commit{datname="kuda"}[1m])','commit'),('rate(pg_stat_database_xact_rollback{datname="kuda"}[1m])','rollback')],'ops')
panel('Попадания в буферный кеш БД',[('100*rate(pg_stat_database_blks_hit{datname="kuda"}[1m])/clamp_min(rate(pg_stat_database_blks_hit{datname="kuda"}[1m])+rate(pg_stat_database_blks_read{datname="kuda"}[1m]),.001)','cache hit')],'percent')
panel('Блокировки и deadlock',[('sum by(mode)(pg_locks_count{datname="kuda"})','{{mode}}'),('increase(pg_stat_database_deadlocks{datname="kuda"}[5m])','deadlocks / 5 минут')])
panel('БД — строки чтения / изменения',[('rate(pg_stat_database_tup_returned{datname="kuda"}[1m])','чтение'),('rate(pg_stat_database_tup_inserted{datname="kuda"}[1m])','INSERT'),('rate(pg_stat_database_tup_updated{datname="kuda"}[1m])','UPDATE')],'ops')
panel('БД — временные файлы',[('rate(pg_stat_database_temp_bytes{datname="kuda"}[1m])','temp')],'Bps')
panel('Доступность всех источников метрик',[('up','{{job}}')],description='Для каждого источника должно быть 1. Источники опрашиваются раз в 10 секунд.')

nextrow('Диагностика диска и ожиданий PostgreSQL')
panel('WAL — среднее время синхронизации',[
    ('rate(kuda_pg_wal_sync_time_seconds_total[20s])/clamp_min(rate(kuda_pg_wal_sync_total[20s]),.001)', 'WAL sync')], 's')
panel('WAL — среднее время записи',[
    ('rate(kuda_pg_wal_write_time_seconds_total[20s])/clamp_min(rate(kuda_pg_wal_write_total[20s]),.001)', 'WAL write')], 's')
panel('WAL — байт/с и заполнения буфера',[
    ('rate(kuda_pg_wal_bytes_total[20s])', 'WAL байт/с')], 'Bps')
panel('База — активные ожидания',[
    ('sum by(type,event)(kuda_pg_activity{state="active"})', '{{type}} / {{event}}')])
panel('База — ожидающие блокировки',[
    ('kuda_pg_waiting_locks', '{{locktype}} / {{mode}}')])
panel('WSL — доля времени с ожиданием I/O',[
    ('100*rate(kuda_linux_pressure_seconds_total{resource="io"}[20s])', '{{scope}}')], 'percent')
panel('Диск — задержка записи за 20 секунд',[
    ('rate(windows_physical_disk_write_seconds_total{job="stand-windows"}[20s])/clamp_min(rate(windows_physical_disk_writes_total{job="stand-windows"}[20s]),.001)', '{{disk}}')], 's')
panel('Диск — очередь запросов',[
    ('windows_physical_disk_requests_queued{job="stand-windows"}', '{{disk}}')])
panel('PostgreSQL — запись и fsync файлов данных',[
    ('sum(rate(kuda_pg_io_write_time_seconds_total[20s]))', 'запись, секунд/с'),
    ('sum(rate(kuda_pg_io_fsync_time_seconds_total[20s]))', 'fsync, секунд/с')], 's')
panel('Checkpoint — время записи и синхронизации',[
    ('rate(kuda_pg_checkpoint_write_time_seconds_total[20s])', 'запись, секунд/с'),
    ('rate(kuda_pg_checkpoint_sync_time_seconds_total[20s])', 'синхронизация, секунд/с')], 's')
panel('JMeter и процессы Windows — занятые ядра',[
    ('sum by(process)(rate(windows_process_cpu_time_seconds_total{job="stand-windows"}[20s]))', '{{process}}')])
panel('Давность диагностического снимка',[
    ('time()-kuda_pg_diagnostics_timestamp_seconds', 'возраст')], 's', threshold=5)

dashboard={'uid':'kuda-load-test','title':'Куда — поиск максимальной производительности','schemaVersion':39,'version':1,'tags':['kuda','load-test'],'timezone':'browser','refresh':'10s','time':{'from':'now-1h','to':'now'},'panels':PANELS,'annotations':{'list':[{'name':'Ступени и остановки','type':'dashboard','datasource':{'type':'grafana','uid':'-- Grafana --'},'enable':True,'iconColor':'orange','builtIn':1}]}}
(ROOT/'dashboard.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2),encoding='utf8')
print(api('POST','dashboards/db',{'dashboard':dashboard,'overwrite':True,'message':'Load test observability'}))

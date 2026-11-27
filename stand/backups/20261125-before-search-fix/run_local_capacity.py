"""Supervised one-hour room workload, followed by artifact collection."""
import base64,csv,datetime,json,math,os,pathlib,shutil,socket,subprocess,time,urllib.request,urllib.parse
ROOT=pathlib.Path('D:/kuda-load-testing');STAND=ROOT/'stand';JMETER='D:/apache-jmeter-5.6.3/bin/jmeter.bat'
VERIFY=os.environ.get('KUDA_VERIFY')=='1';DRAIN=40 if VERIFY else 210
RESUME=os.environ.get('KUDA_RESUME')
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
RUN=pathlib.Path(os.environ['KUDA_LOCAL_RUN_DIR']) if os.environ.get('KUDA_LOCAL_RUN_DIR') else ROOT/'out'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-local-capacity')
RUN.mkdir(parents=True,exist_ok=bool(os.environ.get("KUDA_LOCAL_RUN_DIR")))
PREVIOUS=json.loads((RUN/'status.json').read_text(encoding='utf8')) if RESUME else {}
START=PREVIOUS.get('started',time.time());DEADLINE=PREVIOUS.get('deadline',START+(120 if VERIFY else 3600))
STATE={'started':START,'deadline':DEADLINE,'running':1,'status':'starting','directory':str(RUN),'target':0,'stage':0,'runDirectory':str(RUN),'host':'127.0.0.1','stepSeconds':240,'topology':'backend and generator share this PC'}
PHASES=[]
EVENTS=[json.loads(x) for x in (RUN/'events.jsonl').read_text(encoding='utf8').splitlines()] if RESUME else []
if RESUME:
    for p in PHASES:p.update(calibration=True,calibrationReason='Host automatic disk/.NET maintenance was active; excluded from capacity verdict.')
LAST_PASS=0;FIRST_FAIL=None;PROCESS=None
def write_state(**kw):
    STATE.update(kw);STATE['updated']=time.time()
    data=json.dumps(STATE,ensure_ascii=False,indent=2)
    temp=STAND/'active.tmp';temp.write_text(data,encoding='utf8');os.replace(temp,STAND/'active.json')
    (RUN/'status.json').write_text(data,encoding='utf8')
def request(url):return json.load(urllib.request.urlopen(url,timeout=8))
def query(expr):
    try:
        rows=request('http://127.0.0.1:9090/api/v1/query?'+urllib.parse.urlencode({'query':expr}))['data']['result']
        return float(rows[0]['value'][1]) if rows else None
    except Exception:return None
def event(text,**extra):
    item={'time':time.time(),'text':text,**extra};EVENTS.append(item)
    with (RUN/'events.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(item,ensure_ascii=False)+'\n')
    print(datetime.datetime.now().isoformat(timespec='seconds'),text,flush=True)
    try:
        payload=json.dumps({'dashboardUID':'kuda-load-test','time':int(time.time()*1000),'tags':['kuda','capacity'],'text':text},ensure_ascii=False).encode()
        req=urllib.request.Request('http://127.0.0.1:3001/api/annotations',data=payload,headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((os.environ.get('KUDA_GRAFANA_USER','admin')+':'+os.environ['KUDA_GRAFANA_PASSWORD']).encode()).decode()})
        urllib.request.urlopen(req,timeout=3).close()
    except Exception:pass
def verdict(s):
    stats=s.get('rollingOperations120',{});count=sum(x['count'] for x in stats.values());errors=sum(x['errors'] for x in stats.values())
    reasons=[];hard=[]
    if count>=100 and errors/count>.001:reasons.append(f'Ошибки {100*errors/count:.2f}% > 0.1%')
    if count>=100 and errors/count>.05:hard.append(f'Ошибки {100*errors/count:.2f}% > 5%')
    for name,v in stats.items():
        if v['count']<5:continue
        limits={'/v1/rooms':1,'/v1/rooms/{id}/start':1,'/v1/rooms/{id}':.5,'/v1/rooms/{id}/votes':.5}
        if name not in limits:continue
        limit=limits[name]
        if v['p95']>limit:reasons.append(f'{name}: p95 {v["p95"]:.3f}s > {limit}s')
        if v['p95']>max(2,limit*4):hard.append(f'{name}: p95 {v["p95"]:.3f}s')
    tele=s.get('telemetry',{});finished=tele.get('completed_rooms',0)+tele.get('failed_rooms',0)
    if finished>=5 and tele.get('failed_rooms',0)/finished>.01:reasons.append('Более 1% бизнес-сценариев комнат завершились ошибкой')
    return reasons,hard,count,errors
def shutdown(port=4455,command='Shutdown'):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.sendto(command.encode(),('127.0.0.1',port));sock.close()
def phase(number,rates,step):
    global PROCESS,LAST_PASS,FIRST_FAIL
    folder=RUN/f'phase-{number}';folder.mkdir()
    shutil.copy2(ROOT/'kuda.jmx',folder/'kuda.jmx')
    # Keep finite worker pools sized for the expected in-flight room population.
    top=max(rates);members=3 if VERIFY else min(1500,max(24,math.ceil(top*3*90/60*1.3)));polls=4 if VERIFY else min(3800,max(32,math.ceil(top*4*195/60*1.15)))
    env=os.environ.copy();env['HEAP']='-Xms1g -Xmx6g -XX:MaxMetaspaceSize=512m';env['JVM_ARGS']='-Xss512k -Xloggc:'+str(folder/'gc.log').replace('\\','/')+' -XX:+PrintGCDetails -XX:+PrintGCTimeStamps'
    properties=folder/'run.properties'
    properties.write_text('stageRates='+'|'.join(map(str,rates))+'\n'+('roomViewSeconds=25\npollDelayMs=500\nvotePauseMs=100\nvoteSpreadMs=100\n' if VERIFY else ''),encoding='ascii')
    args=[JMETER,'-n','-t',str(folder/'kuda.jmx'),'-q',str(properties),'-Jhost=127.0.0.1','-Jmode=load',f'-JstepSeconds={step}',f'-JparticipantThreads={members}',f'-JpollThreads={polls}',f'-JdrainSeconds={DRAIN}',f'-JoutDir={folder}', '-Jjmeterengine.nongui.port=4455','-Jjmeterengine.nongui.maxport=4455','-Jjmeterengine.force.system.exit=true','-Jdynamic_tg.properties_caching_validity=1000','-Jjmeter.save.saveservice.autoflush=true','-j',str(folder/'jmeter.log')]
    # A pipe character in a property must be quoted for cmd.exe.
    command=' '.join('"'+a+'"' if ('|' in a or ' ' in a) else a for a in args)
    stdout=(folder/'console.log').open('w',encoding='utf8')
    PROCESS=subprocess.Popen([os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',command],env=env,stdout=stdout,stderr=subprocess.STDOUT)
    began=time.time();arrival_end=began+step*len(rates);stop=None;bad_since=None;hard_since=None;generator_since=None;current=-1;checked={};stop_reason='completed'
    record={'number':number,'rates':rates,'stepSeconds':step,'members':members,'polls':polls,'started':began,'directory':str(folder),'stages':[]};PHASES.append(record)
    write_state(directory=str(folder),phase=number,status='running',running=1)
    event(f'Фаза {number}: '+ ' → '.join(map(str,rates))+' комнат/мин',members=members,polls=polls)
    while PROCESS.poll() is None:
        now=time.time();elapsed=now-began;index=min(len(rates)-1,int(elapsed//step))
        if index!=current and stop is None:
            if current>=0:
                previous=checked.get(current,{'pass':False,'reason':['Нет устойчивого окна измерения']});record['stages'].append({'rate':rates[current],**previous})
                if previous['pass']:LAST_PASS=max(LAST_PASS,rates[current])
                elif FIRST_FAIL is None:FIRST_FAIL=rates[current]
            current=index;bad_since=hard_since=generator_since=None
            event(f'Ступень: {rates[index]} комнат/мин')
        write_state(target=0 if stop or now>=arrival_end else rates[index],stage=index+1,status='draining' if stop else 'running')
        try:s=request('http://127.0.0.1:9199/state')
        except Exception:s={}
        reasons,hard,count,errors=verdict(s)
        tele=s.get('telemetry',{});stage_age=elapsed-index*step
        cpu=query('100*(1-avg(rate(windows_cpu_time_seconds_total{job="generator-windows",mode="idle"}[1m])))')
        rps=query('sum(rate(jmeter_http_requests_total[1m]))')
        queues=max(tele.get('member_queue_oldest_seconds',0),tele.get('poll_queue_oldest_seconds',0))
        generators=([f'CPU генератора {cpu:.1f}%'] if False else [])+([f'Задания ждут {queues:.1f}s'] if queues>10 else [])
        sample={'time':now,'phase':number,'stage':index+1,'target':rates[index],'rps':rps,'generatorCpu':cpu,'generatorReasons':generators,'telemetry':tele,'slaReasons':reasons,'rolling120':s.get('rolling120',{})}
        with (RUN/'monitor.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(sample,ensure_ascii=False)+'\n')
        if stop is None:
            if stage_age>=180 and count>=100:
                checked[index]={'pass':not reasons and not generators,'reason':reasons+generators,'rps':rps,'time':now}
                bad_since=(bad_since or now) if reasons else None
            hard_since=(hard_since or now) if hard and elapsed>=60 else None
            generator_since=(generator_since or now) if generators and elapsed>=60 else None
            if generator_since and now-generator_since>=60:stop_reason='stopped_generator';stop='; '.join(generators)
            elif hard_since and now-hard_since>=90:stop_reason='stopped_sla';stop='Жёсткое превышение: '+'; '.join(hard)
            elif bad_since and now-bad_since>=45:stop_reason='stopped_sla';stop='Устойчивое превышение SLA: '+'; '.join(reasons)
            elif now>=DEADLINE-DRAIN:stop='Резерв на завершение комнат';stop_reason='completed'
            elif now>=arrival_end:stop='Все ступени фазы выполнены';stop_reason='completed'
            if stop:
                (folder/'stop-arrivals').write_text(stop,encoding='utf8');record['stopAt']=now;record['stopReason']=stop_reason;record['stopDetails']=stop
                if stop_reason=='stopped_sla':
                    FIRST_FAIL=rates[index] if FIRST_FAIL is None else min(FIRST_FAIL,rates[index])
                    checked[index]={'pass':False,'reason':reasons,'rps':rps,'time':now}
                event('Новые комнаты остановлены: '+stop)
        else:
            # Let all actual room participants finish before stopping the idle scheduler.
            finished=0
            if (folder/'rooms.csv').exists():
                with (folder/'rooms.csv').open(encoding='utf-8-sig',newline='') as f:finished=sum(1 for _ in csv.DictReader(f))
            if now-record['stopAt']>=15 and finished>=tele.get('started_rooms',10**9) and tele.get('active_rooms',1)==0:
                event('Все комнаты завершены; остановлен оставшийся планировщик')
                shutdown(command='StopTestNow');break
            if now-record['stopAt']>DRAIN+5 or now>DEADLINE:
                event('Достигнут предел завершения; отправлена команда остановки')
                shutdown(command='StopTestNow');break
        time.sleep(10)
    try:PROCESS.wait(timeout=30)
    except subprocess.TimeoutExpired:
        shutdown(command='StopTestNow')
        try:PROCESS.wait(timeout=15)
        except subprocess.TimeoutExpired:subprocess.run(['taskkill','/PID',str(PROCESS.pid),'/T','/F'],capture_output=True)
    stdout.close();record['finished']=time.time();record['exitCode']=PROCESS.returncode
    if current>=0:
        final=checked.get(current,{'pass':False,'reason':['Недостаточно времени на стабильную ступень']});record['stages'].append({'rate':rates[current],**final})
        if final['pass']:LAST_PASS=max(LAST_PASS,rates[current])
    (RUN/'phases.json').write_text(json.dumps(PHASES,ensure_ascii=False,indent=2),encoding='utf8')
    console=(folder/'console.log').read_text(encoding='utf8',errors='replace')
    fatal=any(x in console for x in ['Uncaught Exception','OutOfMemoryError','StackOverflowError','Failed to create UDP port'])
    if record['exitCode']!=0 or fatal or not (folder/'rooms.csv').exists():
        raise RuntimeError(f'JMeter failed to run phase {number}, exit {record["exitCode"]}; see console.log')
    PROCESS=None
    event(f'Фаза {number} завершена',lastPass=LAST_PASS,firstFail=FIRST_FAIL)
    return stop_reason

try:
    write_state();shutil.copy2(ROOT/'kuda.jmx',RUN/'kuda.jmx')
    (RUN/'criteria.json').write_text(json.dumps({'durationLimitSeconds':3600,'readVoteP95Seconds':.5,'createStartP95Seconds':1,'latencyOperations':['GET /v1/rooms/{id}','PUT /v1/rooms/{id}/votes','POST /v1/rooms','POST /v1/rooms/{id}/start'],'otherOperations':'record latency; enforce error rate only','errorRateMax':.001,'roomFailureRateMax':.01,'rollingWindowSeconds':120,'stageSeconds':240,'steadyWindowAfterSeconds':180,'softFailureSustainedSeconds':45,'hardErrorRate':.05,'hardP95Seconds':2,'hardFailureSustainedSeconds':90,'drainReserveSeconds':210,'sharedHostCpuIsNotGeneratorOnly':True,'slaStatus':'working assumptions, not a signed SLA'},indent=2),encoding='utf8')
    event('Продолжен прогон после приостановки обслуживания Windows; исходный часовой предел сохранён.' if RESUME else 'Начат часовой поиск производительности. SLA — рабочее допущение.')
    initial=len(PHASES)+1
    result=phase(initial,[15],4) if VERIFY else phase(initial,[16,32,64,128,256],240)
    remaining=DEADLINE-time.time();number=initial+1
    while not VERIFY and result!='stopped_generator' and remaining>=465:
        precise=FIRST_FAIL is not None and LAST_PASS>0 and FIRST_FAIL-LAST_PASS<=max(1,math.ceil(FIRST_FAIL*.1))
        if precise:target=LAST_PASS
        elif FIRST_FAIL is not None:target=max(1,round((LAST_PASS+FIRST_FAIL)/2))
        else:target=512
        duration=240
        event(f'Уточнение/подтверждение границы: {target} комнат/мин, {duration}s новых входов')
        result=phase(number,[target],duration)
        number+=1;remaining=DEADLINE-time.time()
        if precise:break
    write_state(running=0,target=0,status=result,ended=time.time(),lastPassingRoomsPerMinute=LAST_PASS,firstFailingRoomsPerMinute=FIRST_FAIL)
    event('Нагрузочная часть завершена. Сохранение артефактов.')
except BaseException as exc:
    event('Ошибка контроллера: '+repr(exc))
    if PROCESS is not None:
        shutdown(command='StopTestNow')
        try:PROCESS.wait(timeout=30)
        except Exception:pass
    write_state(running=0,target=0,status='failed',error=repr(exc),ended=time.time())
finally:
    (RUN/'events.json').write_text(json.dumps(EVENTS,ensure_ascii=False,indent=2),encoding='utf8')
    (STAND/'latest-run.txt').write_text(str(RUN),encoding='utf8')
    print('ARTIFACTS',RUN,flush=True)

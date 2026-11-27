"""Read JMeter CSV incrementally; export cumulative histograms and live run state."""
import collections, csv, io, json, math, os, pathlib, re, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=pathlib.Path('/work'); LOCK=threading.RLock()
BOUNDS=[.005,.01,.025,.05,.1,.25,.5,1,2,5,10,30,float('inf')]
HIST={}; OP_HIST={}; STATE={}; PROBE={}; RECENT=collections.deque(); CURSOR=0; CURRENT=None; HEADER=None
def operation(url):
    p=urllib.parse.urlsplit(url).path
    p=re.sub(r'/v1/rooms/[^/]+','/v1/rooms/{id}',p)
    return re.sub(r'/v1/invites/[^/]+','/v1/invites/{token}',p)
def probe():
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while True:
        started=time.perf_counter();success=0
        try:
            with opener.open(os.environ.get('KUDA_PROBE_URL','http://192.168.0.213:8787/health'),timeout=3) as response:
                response.read();success=int(response.status==200)
        except Exception:pass
        with LOCK:PROBE.update(duration=time.perf_counter()-started,success=success)
        time.sleep(5)
def path(s):
    s=s.replace('\\','/')
    return ROOT/s.split('kuda-load-testing/',1)[-1] if 'kuda-load-testing/' in s else pathlib.Path(s)
def update():
    global CURRENT,CURSOR,HEADER,STATE
    while True:
        try:
            active=json.loads((ROOT/'stand/active.json').read_text(encoding='utf-8-sig'))
            STATE=active
            directory=path(active['directory'])
            filename=directory/'results.csv'
            if str(filename)!=CURRENT: CURRENT=str(filename);CURSOR=0;HEADER=None
            if filename.exists():
                with filename.open(encoding='utf-8-sig',newline='') as f:
                    f.seek(CURSOR); block=f.read();end=f.tell()
                if block and block.endswith('\n'):
                    rows=list(csv.reader(io.StringIO(block),strict=True))
                    if HEADER is None: HEADER=rows.pop(0)
                    with LOCK:
                        for row in rows:
                            if len(row)!=len(HEADER): continue
                            r=dict(zip(HEADER,row))
                            if not r.get('URL','').startswith('http'): continue
                            elapsed=float(r['elapsed'])/1000;ok=r['success']=='true'
                            label=r['label'];key=(label,'true' if ok else 'false');op=operation(r['URL'])
                            hist=HIST.setdefault(key,{'count':0,'sum':0,'buckets':[0]*len(BOUNDS)})
                            hist['count']+=1;hist['sum']+=elapsed
                            for i,b in enumerate(BOUNDS): hist['buckets'][i]+=elapsed<=b
                            oh=OP_HIST.setdefault((op,key[1]),{'count':0,'sum':0,'buckets':[0]*len(BOUNDS)})
                            oh['count']+=1;oh['sum']+=elapsed
                            for i,b in enumerate(BOUNDS):oh['buckets'][i]+=elapsed<=b
                            RECENT.append((int(r['timeStamp'])/1000,label,elapsed,ok,op))
                        CURSOR=end
                        while RECENT and RECENT[0][0]<time.time()-120: RECENT.popleft()
            telemetry=directory/'telemetry.json'
            if telemetry.exists():
                try: STATE['telemetry']=json.loads(telemetry.read_text(encoding='utf8'))
                except (ValueError,OSError):pass
            # Browser/runner-readable exact rolling quantiles, separate from histogram approximations.
            with LOCK:
                by=collections.defaultdict(list);by_op=collections.defaultdict(list)
                for t,label,elapsed,ok,op in RECENT:
                    by[label].append((elapsed,ok));by_op[op].append((elapsed,ok))
                summary={}
                for label,values in by.items():
                    ordered=sorted(x[0] for x in values)
                    summary[label]={'count':len(values),'p95':ordered[max(0,math.ceil(.95*len(values))-1)],'errors':sum(not x[1] for x in values)}
                STATE['rolling120']=summary
                STATE['rollingOperations120']={}
                for op,values in by_op.items():
                    ordered=sorted(x[0] for x in values)
                    STATE['rollingOperations120'][op]={'count':len(values),'p95':ordered[max(0,math.ceil(.95*len(values))-1)],'errors':sum(not x[1] for x in values)}
                STATE['observedAt']=time.time()
        except Exception as e:
            STATE['exporterMessage']=str(e)
        time.sleep(2)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        with LOCK:
            if self.path=='/state': body=json.dumps(STATE,ensure_ascii=False).encode()
            else:
                lines=[]
                def emit(name,value,labels=''):
                    if isinstance(value,(int,float)) and math.isfinite(value):lines.append(f'{name}{labels} {value}')
                for (label,ok),h in HIST.items():
                    labels=f'label={json.dumps(label,ensure_ascii=False)},success="{ok}"'
                    emit('jmeter_http_requests_total',h['count'],'{'+labels+'}')
                    emit('jmeter_http_duration_seconds_sum',h['sum'],'{'+labels+'}')
                    emit('jmeter_http_duration_seconds_count',h['count'],'{'+labels+'}')
                    for b,v in zip(BOUNDS,h['buckets']):
                        emit('jmeter_http_duration_seconds_bucket',v,'{'+labels+',le="'+('+Inf' if math.isinf(b) else str(b))+'"}')
                for (op,ok),h in OP_HIST.items():
                    labels='operation='+json.dumps(op)+',success="'+ok+'"'
                    emit('jmeter_operation_requests_total',h['count'],'{'+labels+'}')
                    emit('jmeter_operation_duration_seconds_count',h['count'],'{'+labels+'}')
                    emit('jmeter_operation_duration_seconds_sum',h['sum'],'{'+labels+'}')
                    for b,v in zip(BOUNDS,h['buckets']):
                        emit('jmeter_operation_duration_seconds_bucket',v,'{'+labels+',le="'+('+Inf' if math.isinf(b) else str(b))+'"}')
                emit('kuda_test_running',STATE.get('running',0))
                emit('kuda_test_started_timestamp_seconds',STATE.get('started',0))
                emit('kuda_test_deadline_timestamp_seconds',STATE.get('deadline',0))
                emit('kuda_test_target_rooms_per_minute',STATE.get('target',0))
                emit('kuda_test_stage',STATE.get('stage',0))
                emit('kuda_test_finished',int(STATE.get('status') in ['completed','stopped_sla','stopped_generator','failed']))
                emit('kuda_test_exporter_timestamp_seconds',STATE.get('observedAt',0))
                emit('kuda_network_probe_duration_seconds',PROBE.get('duration',0))
                emit('kuda_network_probe_success',PROBE.get('success',0))
                for name,val in STATE.get('telemetry',{}).items():emit('kuda_test_'+name,val)
                body=('\n'.join(lines)+'\n').encode()
        self.send_response(200);self.send_header('Content-Type','application/json' if self.path=='/state' else 'text/plain; version=0.0.4; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

threading.Thread(target=update,daemon=True).start()
threading.Thread(target=probe,daemon=True).start()
ThreadingHTTPServer(('0.0.0.0',9199),Handler).serve_forever()

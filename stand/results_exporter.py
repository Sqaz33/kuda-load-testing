"""Read JMeter CSV incrementally; export cumulative histograms and live run state."""
import collections, csv, io, json, math, os, pathlib, re, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=pathlib.Path('/work'); LOCK=threading.RLock()
BOUNDS=[.005,.01,.025,.05,.1,.25,.5,1,2,5,10,30,float('inf')]
HIST={}; OP_HIST={}; STATE={}; PROBE={}; RECENT=collections.deque(); CURSOR=0; CURRENT=None; HEADER=None; LAST_INGEST_AT=0
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
def update_once():
    global CURRENT,CURSOR,HEADER,STATE,LAST_INGEST_AT
    active=json.loads((ROOT/'stand/active.json').read_text(encoding='utf-8-sig'))
    directory=path(active['directory'])
    filename=directory/'results.csv'
    changed=str(filename)!=CURRENT
    rows=None;end=0
    if filename.exists():
        with filename.open(encoding='utf-8-sig',newline='') as f:
            f.seek(0 if changed else CURSOR);block=f.read();end=f.tell()
        if block and block.endswith('\n'):
            rows=list(csv.reader(io.StringIO(block),strict=True))
    telemetry=directory/'telemetry.json'
    if telemetry.exists():
        try: active['telemetry']=json.loads(telemetry.read_text(encoding='utf8'))
        except (ValueError,OSError):
            # A concurrent telemetry write may briefly be incomplete. Retain the last
            # complete reading only when it belongs to this same result directory.
            with LOCK:
                if not changed and 'telemetry' in STATE:active['telemetry']=STATE['telemetry']
    with LOCK:
        if changed:
            CURRENT=str(filename);CURSOR=0;HEADER=None;LAST_INGEST_AT=0;RECENT.clear()
        if rows is not None:
            if HEADER is None:HEADER=rows.pop(0)
            for row in rows:
                if len(row)!=len(HEADER):continue
                r=dict(zip(HEADER,row))
                if not r.get('URL','').startswith('http'):continue
                elapsed=float(r['elapsed'])/1000;ok=r['success']=='true'
                label=r['label'];key=(label,'true' if ok else 'false');op=operation(r['URL'])
                hist=HIST.setdefault(key,{'count':0,'sum':0,'buckets':[0]*len(BOUNDS)})
                hist['count']+=1;hist['sum']+=elapsed
                for i,b in enumerate(BOUNDS):hist['buckets'][i]+=elapsed<=b
                oh=OP_HIST.setdefault((op,key[1]),{'count':0,'sum':0,'buckets':[0]*len(BOUNDS)})
                oh['count']+=1;oh['sum']+=elapsed
                for i,b in enumerate(BOUNDS):oh['buckets'][i]+=elapsed<=b
                RECENT.append((int(r['timeStamp'])/1000,label,elapsed,ok,op))
            CURSOR=end
            if rows:LAST_INGEST_AT=time.time()
        # Publish one complete snapshot. HTTP readers never see an intermediate
        # active.json without observedAt, telemetry or the calculated windows.
        fresh=[r for r in RECENT if r[0]>=time.time()-600]
        RECENT.clear();RECENT.extend(fresh)
        by=collections.defaultdict(list);by_op=collections.defaultdict(list)
        for t,label,elapsed,ok,op in RECENT:
            if t < time.time()-120:continue
            by[label].append((elapsed,ok));by_op[op].append((elapsed,ok))
        def summarize(grouped):
            summary={}
            for label,values in grouped.items():
                ordered=sorted(x[0] for x in values)
                summary[label]={'count':len(values),'p95':ordered[max(0,math.ceil(.95*len(values))-1)],'errors':sum(not x[1] for x in values)}
            return summary
        active['rolling120']=summarize(by)
        active['rollingOperations120']=summarize(by_op)
        active['observedAt']=time.time()
        active['lastIngestAt']=LAST_INGEST_AT
        STATE=active

def update():
    while True:
        try:update_once()
        except Exception as e:
            with LOCK:STATE['exporterMessage']=str(e)
        time.sleep(2)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        parsed=urllib.parse.urlsplit(self.path)
        with LOCK:
            if parsed.path=='/window':
                try:
                    params=urllib.parse.parse_qs(parsed.query)
                    start=float(params['from'][0]);end=float(params['to'][0])
                    if not math.isfinite(start) or not math.isfinite(end) or not 0<end-start<=120:
                        raise ValueError('Window must be finite and no longer than 120 seconds')
                    if start<time.time()-600:
                        raise ValueError('Requested window is no longer retained')
                    operations=collections.defaultdict(list)
                    for t,label,elapsed,ok,op in RECENT:
                        if start<=t<end:operations[op].append((elapsed,ok))
                    result={}
                    for op,values in operations.items():
                        ordered=sorted(v[0] for v in values)
                        result[op]={'count':len(values),'errors':sum(not v[1] for v in values),
                                    'p95':ordered[max(0,math.ceil(.95*len(values))-1)]}
                    body=json.dumps({'from':start,'to':end,'directory':STATE.get('directory'),
                                     'lastIngestAt':LAST_INGEST_AT,'observedAt':time.time(),
                                     'operations':result},ensure_ascii=False).encode()
                except (ValueError,KeyError) as exc:
                    body=json.dumps({'error':str(exc)}).encode()
                    self.send_response(400);self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
                    return
            elif parsed.path=='/state': body=json.dumps(STATE,ensure_ascii=False).encode()
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
                emit('kuda_test_finished',int(STATE.get('running')==0 and bool(STATE.get('ended'))))
                emit('kuda_test_exporter_timestamp_seconds',STATE.get('observedAt',0))
                emit('kuda_network_probe_duration_seconds',PROBE.get('duration',0))
                emit('kuda_network_probe_success',PROBE.get('success',0))
                for name,val in STATE.get('telemetry',{}).items():emit('kuda_test_'+name,val)
                body=('\n'.join(lines)+'\n').encode()
        self.send_response(200);self.send_header('Content-Type','application/json' if parsed.path in ('/state','/window') else 'text/plain; version=0.0.4; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

if __name__=='__main__':
    threading.Thread(target=update,daemon=True).start()
    threading.Thread(target=probe,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',9199),Handler).serve_forever()

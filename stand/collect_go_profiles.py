"""Collect non-overlapping Go profiles on the laptop's private loopback endpoint."""
import argparse, datetime, hashlib, json, pathlib, shutil, threading, time, urllib.request

BASE='http://127.0.0.1:6060'
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
SCHEDULE=[
 (0,'heap-early.pprof','/debug/pprof/heap?gc=1',0,0),
 (5,'allocs-early.pprof','/debug/pprof/allocs',0,0),
 (15,'goroutines-early.txt','/debug/pprof/goroutine?debug=2',0,0),
 (180,'cpu-1.pprof','/debug/pprof/profile?seconds=60',0,0),
 (245,'heap-steady.pprof','/debug/pprof/heap?gc=1',0,0),
 (260,'cpu-2.pprof','/debug/pprof/profile?seconds=60',0,0),
 (335,'block-30s.pprof','/debug/pprof/block?seconds=30',1000000,0),
 (380,'mutex-30s.pprof','/debug/pprof/mutex?seconds=30',0,5),
 (425,'execution-trace.out','/debug/pprof/trace?seconds=5',0,0),
 (450,'cpu-3.pprof','/debug/pprof/profile?seconds=60',0,0),
 (525,'heap-after.pprof','/debug/pprof/heap?gc=1',0,0),
 (530,'allocs-after.pprof','/debug/pprof/allocs',0,0),
 (540,'goroutines-after.pprof','/debug/pprof/goroutine',0,0),
 (545,'goroutines-after.txt','/debug/pprof/goroutine?debug=2',0,0),
 (550,'threads.pprof','/debug/pprof/threadcreate',0,0),
]

def controls(block=0,mutex=0):
 data=json.dumps({'blockRate':block,'mutexFraction':mutex}).encode()
 request=urllib.request.Request(BASE+'/debug/profile-control',data=data,method='PUT',headers={'Content-Type':'application/json'})
 with OPENER.open(request,timeout=10) as response:return json.load(response)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('run',type=pathlib.Path);args=parser.parse_args()
 output=args.run/'go-profiles';output.mkdir(parents=True,exist_ok=True)
 origin_file=args.run/'profile-origin.json'
 deadline=time.time()+120
 while not origin_file.exists():
  if time.time()>deadline:raise RuntimeError('Load origin was not supplied')
  time.sleep(.5)
 origin=json.loads(origin_file.read_text(encoding='utf-8-sig'))['started']
 (output/'schedule.json').write_text(json.dumps({'origin':origin,'loadSeconds':600,'profiles':SCHEDULE,'note':'CPU, block, mutex and trace windows are sequential. Heap gc=1 forces collection outside CPU windows.'},indent=2),encoding='utf8')
 stop=threading.Event()
 def runtime_snapshots():
  with (output/'runtime.jsonl').open('a',encoding='utf8') as log:
   while not stop.is_set():
    try:
     with OPENER.open(BASE+'/debug/runtime',timeout=10) as response:data=json.load(response)
     log.write(json.dumps({'collectedAt':time.time(),'data':data})+'\n');log.flush()
    except Exception as exc:log.write(json.dumps({'collectedAt':time.time(),'error':repr(exc)})+'\n');log.flush()
    stop.wait(30)
 thread=threading.Thread(target=runtime_snapshots,daemon=True);thread.start()
 results=[]
 try:
  controls()
  with (output/'collection-events.jsonl').open('a',encoding='utf8') as events:
   for offset,name,url,block,mutex in SCHEDULE:
    while time.time()<origin+offset:time.sleep(max(.001,min(1,origin+offset-time.time())))
    item={'file':name,'url':url,'scheduledOffset':offset,'started':time.time(),'blockRate':block,'mutexFraction':mutex}
    if time.time()>origin+600:
     item.update(status='skipped',reason='load window ended');results.append(item);continue
    temporary=output/(name+'.tmp')
    try:
     controls(block,mutex)
     with OPENER.open(BASE+url,timeout=120) as response,temporary.open('wb') as target:shutil.copyfileobj(response,target,65536)
     temporary.replace(output/name)
     item.update(status='ok',bytes=(output/name).stat().st_size,sha256=hashlib.file_digest((output/name).open('rb'),'sha256').hexdigest())
    except Exception as exc:item.update(status='failed',error=repr(exc))
    finally:
     try:controls()
     except Exception as exc:item['resetError']=repr(exc)
    item['finished']=time.time();results.append(item);events.write(json.dumps(item)+'\n');events.flush()
 finally:
  stop.set();thread.join(timeout=12)
  try:controls();reset=True
  except Exception:reset=False
  done={'finished':time.time(),'samplingReset':reset,'success':all(x['status']=='ok' for x in results) and len(results)==len(SCHEDULE),'profiles':results}
  (output/'PROFILE_COLLECTION_DONE.json').write_text(json.dumps(done,indent=2),encoding='utf8')

if __name__=='__main__':main()


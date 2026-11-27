$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$env:PYTHONIOENCODING='utf-8'
Set-Location C:/Users/mset6/kuda-pgrust
$code=@"
import subprocess,json,collections,re,pathlib,time
r=subprocess.run(['docker','logs','--since','2026-11-27T19:18:40Z','kuda-pgrust-postgres-1'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=40)
p=pathlib.Path('C:/Users/mset6/kuda-pgrust/pgrust-analysis-current.log');p.write_bytes(r.stdout)
s=r.stdout.decode('utf8',errors='replace');lines=s.splitlines()
errors=collections.Counter(re.sub(r'^.*? (ERROR|FATAL|PANIC):\s*',r'\1: ',l) for l in lines if re.search(r'\b(ERROR|FATAL|PANIC):',l))
print(json.dumps({'file':str(p),'bytes':len(r.stdout),'errors':errors.most_common(12)},ensure_ascii=False))
for pattern in ['out of memory','panicked at','Failed process was running','memory watchdog','memory budget','not enough memory']:
 hits=[i for i,l in enumerate(lines) if pattern in l]
 print(json.dumps({'pattern':pattern,'count':len(hits),'examples':[lines[max(0,i-1):i+5] for i in hits[:2]]},ensure_ascii=False))
"@
C:/Python313/python.exe -c $code
docker stats --no-stream --format '{{json .}}'

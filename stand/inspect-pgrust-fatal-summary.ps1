$ProgressPreference='SilentlyContinue'
$env:PYTHONIOENCODING='utf-8'
$code=@"
import subprocess,re,json,collections
r=subprocess.run(['docker','logs','--since','8m','--tail','60000','kuda-pgrust-postgres-1'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',timeout=20)
lines=r.stdout.splitlines();errors=[s for s in lines if re.search(r'\b(?:ERROR|FATAL|PANIC):|panicked at|terminated by signal',s)]
print(json.dumps({'errorLines':len(errors),'recent':errors[-14:]},ensure_ascii=False))
for i,s in enumerate(lines):
 if 'Failed process was running' in s:print(json.dumps({'crashQuery':lines[i:i+5]},ensure_ascii=False))
"@
C:/Python313/python.exe -c $code

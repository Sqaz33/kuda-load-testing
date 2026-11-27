$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$env:PYTHONIOENCODING='utf-8'
$code=@"
import subprocess,time,json,pathlib
out=pathlib.Path('C:/Users/mset6/kuda-pgrust/idle-pool-experiment.json');data={'started':time.time(),'loadRunning':False,'steps':[]}
def read(label):
 r=subprocess.run(['docker','exec','kuda-pgrust-postgres-1','cat','/sys/fs/cgroup/memory.current'],capture_output=True,text=True,timeout=8,check=True)
 q=subprocess.run(['docker','exec','kuda-pgrust-postgres-1','psql','-XAt','-U','kuda','-d','kuda','-c',\"SELECT count(*) FROM pg_stat_activity WHERE application_name='venue-backend';\"],capture_output=True,text=True,timeout=8)
 data['steps'].append({'label':label,'time':time.time(),'cgroupMemoryBytes':int(r.stdout),'apiConnections':q.stdout.strip(),'sqlExit':q.returncode})
read('before_api_stop')
try:
 subprocess.run(['docker','stop','--time','5','kuda-pgrust-api-1'],capture_output=True,timeout=20,check=True)
 time.sleep(5);read('api_stopped_5s')
 time.sleep(5);read('api_stopped_10s')
finally:
 r=subprocess.run(['docker','start','kuda-pgrust-api-1'],capture_output=True,text=True,timeout=20);data['apiRestartExit']=r.returncode
 out.write_text(json.dumps(data,indent=2));print(json.dumps(data))
"@
C:/Python313/python.exe -c $code

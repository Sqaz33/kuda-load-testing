"""Launch the local PostgreSQL run and independent evidence finalization."""
import json
import datetime
import os
import pathlib
import subprocess
import sys
import time

stand=pathlib.Path(__file__).parent
hint=stand/'local-next-run.txt'
run=(pathlib.Path(hint.read_text().strip()) if hint.exists()
     else stand.parent/'out'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-capacity'))
run.mkdir(parents=True,exist_ok=True)
if (run/'status.json').exists():
    raise RuntimeError('This run has already been launched')
env=os.environ.copy()
env.update(KUDA_LOCAL_RUN_DIR=str(run), KUDA_TARGET_HOST='127.0.0.1', KUDA_STAND_LOCATION='local',
           KUDA_COMPOSE_PROJECT='kuda-backend', KUDA_REMOTE_ROOT='', KUDA_BACKEND_ENGINE='postgres',
           KUDA_START_RATE='352', KUDA_INCREMENT='64', KUDA_RAMP_SECONDS='300',
           KUDA_INITIAL_STAGE_SECONDS='180', KUDA_STAGE_SECONDS='480', KUDA_MAX_RATE='1024',
           KUDA_DURATION_LIMIT='7200', KUDA_SLA_MODE='latency_only', PYTHONIOENCODING='utf-8')
(run/'launch-settings.json').write_text(json.dumps({key:value for key,value in env.items() if key.startswith('KUDA_') and not any(secret in key for secret in ('PASSWORD','SECRET','TOKEN'))},indent=2),encoding='utf8')
(run/'run-started.txt').write_text(str(time.time()))
with (run/'backend-commit.txt').open('w') as target:
    subprocess.run(['git','-C','D:/venue-backend','rev-parse','HEAD'],stdout=target,check=True)
subprocess.run(['git','-C','D:/venue-backend','archive','--format=zip',f'--output={run / "backend-source.zip"}','HEAD'],check=True)
subprocess.run(['docker','exec','kuda-backend-postgres-1','psql','-X','-v','ON_ERROR_STOP=1','-U','kuda','-d','kuda','-c','SELECT pg_stat_statements_reset();'],check=True,stdout=subprocess.DEVNULL)
processes={}
def launch(name, command):
    output=(run/(name+'.log')).open('w',encoding='utf8')
    process=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    output.close()
    processes[name]=process.pid
    return process
launch('diagnostics',[sys.executable,'-u','-X','utf8',str(stand/'collect_laptop_diagnostics.py'),str(run),'--project','kuda-backend'])
launch('controller',[sys.executable,'-u','-X','utf8',str(stand/'run_laptop_capacity.py')])
for attempt in range(20):
    if (run/'status.json').exists():break
    time.sleep(.5)
else:
    raise RuntimeError('Controller did not create run status')
launch('finalization',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(stand/'finish-local-run.ps1'),'-RunDirectory',str(run)])
(run/'processes.json').write_text(json.dumps(processes,indent=2),encoding='utf8')
(stand/'local-current-run.txt').write_text(str(run),encoding='utf8')
print(json.dumps({'directory':str(run),'processes':processes},indent=2))

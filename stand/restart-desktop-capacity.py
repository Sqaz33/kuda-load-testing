"""Stop the current local engine, preserve its SQL evidence, start the new profile."""
import datetime
import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

stand=pathlib.Path(__file__).parent
previous=pathlib.Path((stand/'local-current-run.txt').read_text().strip())
state=json.loads((previous/'status.json').read_text(encoding='utf8'))
if state.get('standLocation')!='local' or state.get('host')!='127.0.0.1':
    raise RuntimeError('Expected the active desktop run')
if state.get('running'):
    (previous/'stop-requested').write_text('Restart requested with updated launch profile',encoding='utf8')
    for attempt in range(20):
        state=json.loads((previous/'status.json').read_text(encoding='utf8'))
        if state.get('status')=='draining' or not state.get('running'):break
        time.sleep(.5)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as channel:
        channel.sendto(b'StopTestNow',('127.0.0.1',4455))
    for attempt in range(45):
        state=json.loads((previous/'status.json').read_text(encoding='utf8'))
        if not state.get('running'):break
        time.sleep(1)
    else:
        raise RuntimeError('The previous controller is still running')
(previous/'stop-diagnostics').touch()
sql='COPY (SELECT queryid,calls,total_exec_time,mean_exec_time,max_exec_time,rows,shared_blks_hit,shared_blks_read,temp_blks_written,query FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) ORDER BY total_exec_time DESC LIMIT 200) TO STDOUT WITH CSV HEADER'
logs=previous/'stand-logs'
logs.mkdir(exist_ok=True)
if not (logs/'pg-stat-statements.csv').exists():
    with (logs/'pg-stat-statements.csv').open('wb') as target:
        subprocess.run(['docker','exec','kuda-backend-postgres-1','psql','-X','-v','ON_ERROR_STOP=1','-U','kuda','-d','kuda','-c',sql],stdout=target,check=True)
# The diagnostic exporter owns port 9200; do not start its replacement until it exits.
for attempt in range(40):
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:9200/state',timeout=1).close()
    except OSError:
        break
    time.sleep(1)
else:
    raise RuntimeError('Previous diagnostics have not released port 9200')
run=stand.parent/'out'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-capacity')
run.mkdir()
(stand/'local-next-run.txt').write_text(str(run),encoding='utf8')
print('Previous run stopped:',previous,flush=True)
subprocess.run([sys.executable,'-X','utf8',str(stand/'start-desktop-capacity.py')],check=True)

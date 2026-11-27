import csv
import os
import pathlib
import subprocess

stand=pathlib.Path(__file__).parent
run=pathlib.Path((stand/'local-next-run.txt').read_text().strip())/'smoke'
run.mkdir()
args=['D:/apache-jmeter-5.6.3/bin/jmeter.bat','-n','-t',str(stand.parent/'kuda.jmx'),
      '-Jhost=127.0.0.1','-Jmode=smoke','-JsmokeRooms=2','-JvotePauseMs=20','-JvoteSpreadMs=0',
      '-JroomViewSeconds=6','-JdrainSeconds=25','-JjoinTimeoutSeconds=15','-JvotingTimeoutSeconds=20',
      '-JparticipantThreads=8','-JpollThreads=12',f'-JoutDir={run}',
      '-Jjmeterengine.force.system.exit=true','-j',str(run/'jmeter.log')]
with (run/'console.log').open('w') as output:
    subprocess.run([os.environ['COMSPEC'],'/d','/s','/c',subprocess.list2cmdline(args)],stdout=output,stderr=subprocess.STDOUT,check=True,timeout=120)
with (run/'rooms.csv').open(encoding='utf-8-sig') as source:
    rooms=list(csv.DictReader(source))
print(rooms)
if len(rooms)!=2 or any(room['result']!='success' for room in rooms):
    raise RuntimeError('Room smoke test failed')

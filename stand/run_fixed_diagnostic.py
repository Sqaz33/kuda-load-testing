"""Run one uninterrupted JMeter profile: 100 rooms/min for 4 min, then 240 for 6 min."""
import csv
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import time
import urllib.parse

from run_continuous_capacity import ROOT, STAND, atomic_json, request, stop_engine

PROFILE = [(100, 240), (240, 360)]
DRAIN = 210


def main():
    run = pathlib.Path(os.environ['KUDA_LOCAL_RUN_DIR'])
    folder = run/'phase-1'
    folder.mkdir()
    started = time.time()
    state = dict(started=started, deadline=started+600+DRAIN+30, running=1, status='starting',
                 directory=str(folder), runDirectory=str(run), host='127.0.0.1', target=100,
                 stage=1, phase=1, continuous=True, kind='fixed_diagnostic',
                 topology='backend and generator share this PC', maximumConfirmed=False)
    phases = [dict(number=1, rates=[100, 240], continuous=True, started=started,
                   directory=str(folder), stages=[])]
    events = []
    process = collector = console = collector_console = None

    def save(**updates):
        state.update(updates, updated=time.time())
        atomic_json(STAND/'active.json', state)
        atomic_json(run/'status.json', state)
        atomic_json(run/'phases.json', phases)

    def event(text):
        item = dict(time=time.time(), text=text)
        events.append(item)
        with (run/'events.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps(item)+'\n')
        print(datetime.datetime.now().isoformat(), text, flush=True)

    def rate(value):
        atomic_json(folder/'load-control.json', dict(rate=value, updated=time.time()))

    try:
        for destination in (run, folder):
            shutil.copy2(ROOT/'kuda.jmx', destination/'kuda.jmx')
        for source, name in [(pathlib.Path(__file__), 'controller-used.py'),
                             (STAND/'run_continuous_capacity.py', 'controller-common-used.py'),
                             (STAND/'collect_db_diagnostics.py', 'db-collector-used.py'),
                             (STAND/'results_exporter.py', 'results-exporter-used.py')]:
            shutil.copy2(source, run/name)
        atomic_json(run/'criteria.json', dict(kind='fixed_diagnostic', profile=[
            dict(rate=rate, durationSeconds=seconds) for rate, seconds in PROFILE],
            loadSeconds=600, drainReserveSeconds=DRAIN, stopOnSlaFailure=False,
            latencyLimitsSeconds={'/v1/rooms': 1, '/v1/rooms/{id}/start': 1,
                                  '/v1/rooms/{id}': .5, '/v1/rooms/{id}/votes': .5},
            note='Fixed reproduction profile. Assess full stages and time series after completion.'))
        properties = folder/'run.properties'
        properties.write_text('stageRates=100\nstepSeconds=240\nroomViewSeconds=180\n'
                              'continuous=true\narrivalCeiling=240\nloadSeconds=600\n'
                              f'responseTimeoutMs=10000\ndrainSeconds={DRAIN}\n', encoding='ascii')
        rate(100)
        save(status='running')
        collector_console = (run/'diagnostics-collector-console.log').open('w', encoding='utf8')
        collector = subprocess.Popen(['python', '-u', str(STAND/'collect_db_diagnostics.py'), str(run)],
                                     stdout=collector_console, stderr=subprocess.STDOUT)
        env = os.environ.copy()
        env['HEAP'] = '-Xms1g -Xmx6g -XX:MaxMetaspaceSize=512m'
        env['JVM_ARGS'] = '-Xss512k -Xloggc:'+str(folder/'gc.log').replace('\\', '/')+(
            ' -XX:+PrintGCDetails -XX:+PrintGCTimeStamps')
        args = ['D:/apache-jmeter-5.6.3/bin/jmeter.bat', '-n', '-t', str(folder/'kuda.jmx'),
                '-q', str(properties), '-Jhost=127.0.0.1', '-Jmode=load',
                '-JparticipantThreads=1500', '-JpollThreads=3800', f'-JoutDir={folder}',
                '-Jjmeterengine.nongui.port=4455', '-Jjmeterengine.nongui.maxport=4455',
                '-Jjmeterengine.force.system.exit=true', '-Jdynamic_tg.properties_caching_validity=1000',
                '-Jjmeter.save.saveservice.autoflush=true', '-j', str(folder/'jmeter.log')]
        console = (folder/'console.log').open('w', encoding='utf8')
        process = subprocess.Popen([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c',
                                    subprocess.list2cmdline(args)], env=env, stdout=console,
                                   stderr=subprocess.STDOUT)
        origin = drain_started = None
        result = 'completed'
        next_window = 60
        event('Fixed diagnostic profile: 100/min for 240s, then 240/min for 360s')
        while process.poll() is None:
            now = time.time()
            telemetry = {}
            try:
                telemetry = json.loads((folder/'telemetry.json').read_text(encoding='utf8'))
            except (OSError, ValueError):
                pass
            if not origin and telemetry.get('phase_started_seconds'):
                origin = telemetry['phase_started_seconds']
                phases[0]['stages'].append(dict(rate=100, started=origin, durationSeconds=240, purpose='warmup'))
                save()
            elapsed = now-origin if origin else 0
            with (run/'monitor.jsonl').open('a', encoding='utf8') as f:
                f.write(json.dumps(dict(time=now, target=state['target'], stage=state['stage'],
                                       telemetry=telemetry))+'\n')
            if origin:
                if next_window <= 600 and elapsed >= next_window+15:
                    try:
                        params = urllib.parse.urlencode({'from': origin+next_window-60, 'to': origin+next_window})
                        atomic_json(folder/f'measurement-minute-{next_window//60}.json', request('/window?'+params))
                    except Exception as exc:
                        event('Window collection error: '+repr(exc))
                    next_window += 60
                if elapsed >= 240 and state['stage'] == 1 and not drain_started:
                    phases[0]['stages'][0]['finished'] = now
                    phases[0]['stages'].append(dict(rate=240, started=now, durationSeconds=360, purpose='diagnostic'))
                    rate(240)
                    save(stage=2, target=240)
                    event('240 rooms/min: six-minute diagnostic stage started')
            stop_requested = (run/'stop-requested').exists()
            if not drain_started and ((origin and elapsed >= 600) or stop_requested):
                result = 'user_stopped' if stop_requested else 'completed'
                drain_started = now
                rate(0)
                (folder/'stop-arrivals').write_text(result, encoding='utf8')
                if phases[0]['stages']:
                    phases[0]['stages'][-1]['finished'] = now
                save(status='draining', target=0)
                event('New arrivals stopped; finishing existing rooms')
            if drain_started:
                drained = telemetry and telemetry.get('active_rooms') == 0 and not telemetry.get('member_queue') and not telemetry.get('poll_queue')
                if now-drain_started >= 15 and drained:
                    stop_engine()
                    break
                if now-drain_started >= DRAIN:
                    result = 'inconclusive_drain'
                    stop_engine()
                    break
            if not origin and now-started > 60:
                raise RuntimeError('JMeter did not publish startup telemetry')
            if collector.poll() is not None:
                raise RuntimeError('Database diagnostics collector stopped')
            if now >= state['deadline']:
                raise RuntimeError('Run exceeded its time limit')
            time.sleep(1)
        process.wait(timeout=30)
        if process.returncode:
            result = 'inconclusive_engine'
        elif not drain_started:
            result = 'inconclusive_engine'
        phases[0].update(exitCode=process.returncode, finished=time.time())
        rows_file = folder/'rooms.csv'
        rows = list(csv.DictReader(rows_file.open(encoding='utf-8-sig', newline=''))) if rows_file.exists() else []
        phases[0].update(roomCount=len(rows), failedRooms=sum(r['result'] != 'success' for r in rows))
        save(running=0, status=result, target=0, ended=time.time())
        event('Run finished: '+result)
    except BaseException as exc:
        if process and process.poll() is None:
            stop_engine()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        save(running=0, target=0, status='failed', error=repr(exc), ended=time.time())
        raise
    finally:
        if console:
            console.close()
        (run/'stop-diagnostics').touch()
        if collector:
            collector.wait(timeout=20)
        if collector_console:
            collector_console.close()
        atomic_json(run/'events.json', events)
        (STAND/'latest-run.txt').write_text(str(run), encoding='utf8')


if __name__ == '__main__':
    main()

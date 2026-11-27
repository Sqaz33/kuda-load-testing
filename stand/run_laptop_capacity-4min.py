"""One JMeter engine; change room arrival rate without draining between stages."""
import base64
import csv
import datetime
import json
import os
import pathlib
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request

from capacity_policy import CapacitySearch

ROOT = pathlib.Path('D:/kuda-load-testing')
STAND = ROOT / 'stand'
STEP, WARMUP, MEASURE, SETTLE, DRAIN = 240, 180, 45, 15, 210
LIMITS = {'/v1/rooms': 1, '/v1/rooms/{id}/start': 1,
          '/v1/rooms/{id}': .5, '/v1/rooms/{id}/votes': .5}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def atomic_json(filename, data):
    temporary = filename.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')
    # Readers on Windows may briefly open the destination without delete sharing.
    deadline = time.monotonic() + 8
    delay = .02
    while True:
        try:
            os.replace(temporary, filename)
            return
        except PermissionError as exc:
            if getattr(exc, 'winerror', None) not in (5, 32, 33) or time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, .25)


def request(path):
    with OPENER.open('http://127.0.0.1:9199' + path, timeout=5) as response:
        return json.load(response)


def stop_engine():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(b'StopTestNow', ('127.0.0.1', 4455))


def reasons_for(operations, severe=False):
    count = sum(v['count'] for v in operations.values())
    errors = sum(v['errors'] for v in operations.values())
    reasons = []
    if count >= 100 and errors / count > (.05 if severe else .001):
        reasons.append(f'HTTP/assertion errors: {errors}/{count}')
    for name, limit in LIMITS.items():
        value = operations.get(name)
        threshold = max(2, 4 * limit) if severe else limit
        if value and value['count'] >= 5 and value['p95'] > threshold:
            reasons.append(f'{name}: p95={value["p95"]:.3f}s > {threshold}s')
    return reasons


def score(window, folder, rate, end):
    normalize = lambda p: str(p or '').replace('\\', '/').lower()
    if normalize(window.get('directory')) != normalize(folder):
        return 'inconclusive_monitoring', ['Wrong result directory']
    if window.get('lastIngestAt', 0) < end:
        return 'inconclusive_monitoring', ['Results have not reached the measured window end']
    operations = window.get('operations', {})
    missing = [key for key in LIMITS if operations.get(key, {}).get('count', 0) < 5]
    if missing:
        return 'inconclusive_samples', ['Too few measured samples: ' + ', '.join(missing)]
    reasons = reasons_for(operations)
    if reasons:
        return 'failed', reasons
    creates = operations['/v1/rooms']['count'] - operations['/v1/rooms']['errors']
    if creates < rate * MEASURE / 60 * .85:
        return 'inconclusive_delivery', ['Generator did not deliver the requested creation rate']
    return 'passed', []


def main():
    run = pathlib.Path(os.environ['KUDA_LOCAL_RUN_DIR']) if os.environ.get('KUDA_LOCAL_RUN_DIR') else (
        ROOT / 'out' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-laptop-capacity'))
    run.mkdir(parents=True, exist_ok=True)
    if (run / 'phases.json').exists():
        raise RuntimeError('Existing run cannot be overwritten')
    folder = run / 'phase-1'
    folder.mkdir()
    started = time.time()
    deadline = started + 3600
    search = CapacitySearch(start=16, ceiling=512, resolution=1)
    state = {'started': started, 'deadline': deadline, 'running': 1, 'status': 'starting',
             'directory': str(folder), 'runDirectory': str(run), 'host': '192.168.0.213',
             'stepSeconds': STEP, 'measurementSeconds': MEASURE, 'target': 0, 'stage': 0,
             'phase': 1, 'continuous': True, 'topology': 'backend on laptop 192.168.0.213; generator on desktop'}
    phases = [{'number': 1, 'rates': [], 'stepSeconds': STEP, 'warmupSeconds': WARMUP,
               'measurementSeconds': MEASURE, 'settleSeconds': SETTLE, 'continuous': True,
               'started': started, 'directory': str(folder), 'stages': []}]
    events = []
    process = None
    stdout = None

    def write_state(**values):
        state.update(values)
        state.update(updated=time.time(), lastPassingRoomsPerMinute=search.low,
                     firstFailingRoomsPerMinute=search.high, maximumConfirmed=search.confirmed)
        atomic_json(STAND / 'active.json', state)
        atomic_json(run / 'status.json', state)
        atomic_json(run / 'phases.json', phases)
        atomic_json(run / 'search-history.json', search.history)

    def event(text, **details):
        item = {'time': time.time(), 'text': text, **details}
        events.append(item)
        with (run / 'events.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
        print(datetime.datetime.now().isoformat(timespec='seconds'), text, flush=True)
        try:
            body = json.dumps({'dashboardUID': 'kuda-load-test', 'time': int(item['time'] * 1000),
                               'tags': ['kuda', 'capacity'], 'text': text}).encode()
            req = urllib.request.Request('http://127.0.0.1:3001/api/annotations', data=body,
                headers={'Content-Type': 'application/json',
                         'Authorization': 'Basic ' + base64.b64encode((os.environ.get('KUDA_GRAFANA_USER','admin')+':'+os.environ['KUDA_GRAFANA_PASSWORD']).encode()).decode()})
            OPENER.open(req, timeout=2).close()
        except Exception:
            pass

    def set_rate(rate):
        atomic_json(folder / 'load-control.json', {'rate': rate, 'updated': time.time()})

    try:
        for target in (run, folder):
            shutil.copy2(ROOT / 'kuda.jmx', target / 'kuda.jmx')
        shutil.copy2(__file__, run / 'controller-used.py')
        shutil.copy2(STAND / 'capacity_policy.py', run / 'capacity-policy-used.py')
        shutil.copy2(STAND / 'results_exporter.py', run / 'results-exporter-used.py')
        atomic_json(run / 'criteria.json', {
            'durationLimitSeconds': 3600, 'stageSeconds': STEP, 'warmupSeconds': WARMUP,
            'measurementSeconds': MEASURE, 'settleSeconds': SETTLE, 'continuous': True,
            'latencyLimitsSeconds': LIMITS, 'errorRateMax': .001, 'roomFailureRateMax': .01,
            'resolutionRoomsPerMinute': 1, 'maximumProbeRate': search.ceiling,
            'drainReserveSeconds': DRAIN, 'hardFailureSustainedSeconds': 90,
            'slaStatus': 'working assumptions',
            'arrivalControl': 'Even Open Model potential starts; admission accumulator reads load-control.json. Rejected starts send no HTTP.',
            'stageTransition': 'Change rate in the same JMeter process; existing rooms continue. Drain only at test end.'})
        decision = search.next()
        set_rate(decision.rate)
        properties = folder / 'run.properties'
        properties.write_text(f'stageRates=16\nstepSeconds={STEP}\nroomViewSeconds=180\n'
                              f'continuous=true\narrivalCeiling={search.ceiling}\nloadSeconds={3600-DRAIN}\n'
                              f'responseTimeoutMs=10000\ndrainSeconds={DRAIN}\n', encoding='ascii')
        env = os.environ.copy()
        env['HEAP'] = '-Xms1g -Xmx6g -XX:MaxMetaspaceSize=512m'
        env['JVM_ARGS'] = '-Xss512k -Xloggc:' + str(folder / 'gc.log').replace('\\', '/') + (
            ' -XX:+PrintGCDetails -XX:+PrintGCTimeStamps')
        args = ['D:/apache-jmeter-5.6.3/bin/jmeter.bat', '-n', '-t', str(folder / 'kuda.jmx'),
                '-q', str(properties), '-Jhost=192.168.0.213', '-Jmode=load',
                '-JparticipantThreads=1500', '-JpollThreads=3800', f'-JoutDir={folder}',
                '-Jjmeterengine.nongui.port=4455', '-Jjmeterengine.nongui.maxport=4455',
                '-Jjmeterengine.force.system.exit=true', '-Jdynamic_tg.properties_caching_validity=1000',
                '-Jjmeter.save.saveservice.autoflush=true', '-j', str(folder / 'jmeter.log')]
        write_state(status='running', target=16, stage=1)
        stdout = (folder / 'console.log').open('w', encoding='utf8')
        process = subprocess.Popen([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c',
                                    subprocess.list2cmdline(args)], env=env,
                                   stdout=stdout, stderr=subprocess.STDOUT)
        event('Continuous run: 16 rooms/min; 4-minute stages, no intermediate drain')
        origin, stage_start, current = None, None, None
        monitoring_seen_at = started
        severe_since, queue_since, drain_started = None, None, None
        baseline_failed = baseline_completed = None
        last_telemetry = {}
        result = None
        while process.poll() is None:
            now = time.time()
            try:
                sample = request('/state')
                if str(sample.get('directory', '')).replace('\\', '/').lower() != str(folder).replace('\\', '/').lower():
                    sample = {}
            except Exception:
                sample = {}
            telemetry = sample.get('telemetry', {})
            if sample.get('observedAt', 0) >= now - 10:
                monitoring_seen_at = now
            if telemetry:
                last_telemetry = telemetry
                origin = origin or telemetry.get('phase_started_seconds')
            if current is None and origin:
                stage_start = origin
                current = {'rate': decision.rate, 'started': stage_start, 'purpose': decision.action,
                           'selectionReason': decision.reason}
                phases[0]['rates'].append(decision.rate)
                phases[0]['stages'].append(current)
                write_state()
            with (run / 'monitor.jsonl').open('a', encoding='utf8') as f:
                f.write(json.dumps({'time': now, 'phase': 1, 'stage': state['stage'],
                    'target': state['target'], 'telemetry': telemetry,
                    'observedAt': sample.get('observedAt'), 'exporterMessage': sample.get('exporterMessage'),
                    'rollingOperations120': sample.get('rollingOperations120', {})}) + '\n')
            if result is None:
                if (run / 'stop-requested').exists():
                    result = 'user_stopped'
                elif now >= deadline - DRAIN:
                    result = 'budget_exhausted'
                elif not origin and now - started > 45:
                    result = 'inconclusive_monitoring'
                elif now - monitoring_seen_at > 25 and now - started > 45:
                    result = 'inconclusive_monitoring'
                elif current:
                    elapsed = now - stage_start
                    age = max(telemetry.get('member_queue_oldest_seconds', 0),
                              telemetry.get('poll_queue_oldest_seconds', 0))
                    queue_since = (queue_since or now) if age > 10 else None
                    hard = reasons_for(sample.get('rollingOperations120', {}), severe=True)
                    # After reducing load, allow old rooms to complete before judging recovery.
                    early_allowed = len(phases[0]['rates']) == 1 or decision.rate >= phases[0]['rates'][-2]
                    severe_since = (severe_since or now) if hard and elapsed >= (60 if early_allowed else WARMUP) else None
                    if baseline_failed is None and elapsed >= WARMUP:
                        baseline_failed = telemetry.get('failed_rooms', 0)
                        baseline_completed = telemetry.get('completed_rooms', 0)
                    early_failure = bool(severe_since and now - severe_since >= 90)
                    if queue_since and now - queue_since >= 30:
                        result = 'inconclusive_generator'
                    elif elapsed >= STEP or early_failure:
                        window = None
                        if early_failure:
                            outcome, reasons = 'failed', hard
                        else:
                            end = stage_start + STEP - SETTLE
                            params = urllib.parse.urlencode({'from': end - MEASURE, 'to': end})
                            try:
                                window = request('/window?' + params)
                                outcome, reasons = score(window, folder, decision.rate, end)
                            except Exception as exc:
                                outcome, reasons = 'inconclusive_monitoring', [repr(exc)]
                            if baseline_failed is not None:
                                failed = telemetry.get('failed_rooms', 0) - baseline_failed
                                done = telemetry.get('completed_rooms', 0) - baseline_completed + failed
                                if done >= 5 and failed / done > .01:
                                    outcome, reasons = 'failed', [f'Room scenarios failed: {failed}/{done}']
                        current.update(finished=now, durationSeconds=now-stage_start, outcome=outcome,
                                       **{'pass': outcome == 'passed'}, reason=reasons,
                                       measurementFrom=stage_start+WARMUP,
                                       measurementTo=stage_start+STEP-SETTLE)
                        if window:
                            atomic_json(folder / f'measurement-stage-{state["stage"]}.json', window)
                        search.observe(decision.rate, outcome, confirmation=decision.action == 'confirm')
                        event(f'Stage {state["stage"]}: {decision.rate} rooms/min -> {outcome}', reasons=reasons)
                        decision = search.next()
                        if decision.action == 'stop':
                            result = decision.reason
                        elif deadline - now < STEP + DRAIN:
                            result = 'budget_exhausted'
                        else:
                            # Direct nonzero-to-nonzero transition in the existing engine.
                            set_rate(decision.rate)
                            stage_start = time.time()
                            current = {'rate': decision.rate, 'started': stage_start,
                                       'purpose': decision.action, 'selectionReason': decision.reason}
                            phases[0]['rates'].append(decision.rate)
                            phases[0]['stages'].append(current)
                            severe_since = queue_since = None
                            baseline_failed = baseline_completed = None
                            write_state(status='running', target=decision.rate, stage=state['stage']+1)
                            event(f'Stage {state["stage"]}: {decision.rate} rooms/min; no pause')
                if result is not None:
                    drain_started = now
                    set_rate(0)
                    (folder / 'stop-arrivals').write_text(result, encoding='utf8')
                    if current and 'outcome' not in current:
                        current.update(finished=now, outcome=result, **{'pass': False}, reason=[result])
                    write_state(status='draining', target=0)
                    event('Final drain: ' + result, lastMonitoringAt=monitoring_seen_at,
                          observedAt=sample.get('observedAt'), exporterMessage=sample.get('exporterMessage'))
            else:
                if (now - drain_started >= 15 and telemetry and telemetry.get('active_rooms') == 0
                    and telemetry.get('member_queue', 0) == 0 and telemetry.get('poll_queue', 0) == 0):
                    stop_engine()
                    break
                if now - drain_started >= DRAIN or now >= deadline:
                    result = 'inconclusive_drain'
                    stop_engine()
                    break
            time.sleep(1)
        try:
            process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            stop_engine()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                result = 'inconclusive_engine'
        phases[0].update(exitCode=process.returncode, finished=time.time())
        if process.returncode != 0:
            result = 'inconclusive_engine'
        rows_file = folder / 'rooms.csv'
        rows = list(csv.DictReader(rows_file.open(encoding='utf-8-sig', newline=''))) if rows_file.exists() else []
        phases[0].update(roomCount=len(rows), failedRooms=sum(r['result'] != 'success' for r in rows))
        if result == 'bracketed_and_confirmed' and len(rows) != last_telemetry.get('started_rooms'):
            result = 'inconclusive_rooms'
        write_state(running=0, target=0, status=result or 'inconclusive_engine', ended=time.time())
        event('Run finished: ' + state['status'], low=search.low, high=search.high, confirmed=search.confirmed)
    except BaseException as exc:
        if process and process.poll() is None:
            stop_engine()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        write_state(running=0, target=0, status='failed', error=repr(exc), ended=time.time())
        event('Controller failed: ' + repr(exc))
        raise
    finally:
        if stdout:
            stdout.close()
        atomic_json(run / 'events.json', events)
        (STAND / 'latest-run.txt').write_text(str(run), encoding='utf8')
        print('ARTIFACTS', run, flush=True)


if __name__ == '__main__':
    main()

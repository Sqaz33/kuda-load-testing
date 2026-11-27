"""Run one candidate at a time: 180 s warm-up, then 60 s measured load.

The next rate is selected only after the current candidate has a final verdict.
JMeter business logic and Groovy scripts remain embedded in kuda.jmx.
"""
import base64
import csv
import datetime
import json
import math
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
JMETER = 'D:/apache-jmeter-5.6.3/bin/jmeter.bat'
STEP, WARMUP, MEASURE, DRAIN, SETTLE = 240, 180, 60, 210, 20
LIMITS = {'/v1/rooms': 1, '/v1/rooms/{id}/start': 1,
          '/v1/rooms/{id}': .5, '/v1/rooms/{id}/votes': .5}
RUN = pathlib.Path(os.environ['KUDA_LOCAL_RUN_DIR']) if os.environ.get('KUDA_LOCAL_RUN_DIR') else (
    ROOT / 'out' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '-local-capacity'))
RUN.mkdir(parents=True, exist_ok=bool(os.environ.get('KUDA_LOCAL_RUN_DIR')))
if (RUN / 'phases.json').exists():
    raise RuntimeError('Existing results must not be overwritten')
START = time.time()
DEADLINE = START + 3600
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SEARCH = CapacitySearch(start=16, ceiling=512, resolution=1)
STATE = {'started': START, 'deadline': DEADLINE, 'running': 1, 'status': 'starting',
         'directory': str(RUN), 'runDirectory': str(RUN), 'host': '127.0.0.1',
         'stepSeconds': STEP, 'measurementSeconds': MEASURE, 'target': 0, 'stage': 0,
         'topology': 'backend and generator share this PC'}
PHASES, EVENTS = [], []
PROCESS = None


def request(path):
    with OPENER.open('http://127.0.0.1:9199' + path, timeout=8) as response:
        return json.load(response)


def write_state(**values):
    STATE.update(values)
    STATE.update(updated=time.time(), lastPassingRoomsPerMinute=SEARCH.low,
                 firstFailingRoomsPerMinute=SEARCH.high, maximumConfirmed=SEARCH.confirmed)
    data = json.dumps(STATE, ensure_ascii=False, indent=2)
    temp = STAND / 'active.tmp'
    temp.write_text(data, encoding='utf8')
    os.replace(temp, STAND / 'active.json')
    (RUN / 'status.json').write_text(data, encoding='utf8')


def event(text, **details):
    item = {'time': time.time(), 'text': text, **details}
    EVENTS.append(item)
    with (RUN / 'events.jsonl').open('a', encoding='utf8') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(datetime.datetime.now().isoformat(timespec='seconds'), text, flush=True)
    try:
        data = json.dumps({'dashboardUID': 'kuda-load-test', 'time': int(item['time'] * 1000),
                           'tags': ['kuda', 'capacity'], 'text': text}, ensure_ascii=False).encode()
        annotation = urllib.request.Request('http://127.0.0.1:3001/api/annotations', data=data,
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Basic ' + base64.b64encode((os.environ.get('KUDA_GRAFANA_USER','admin')+':'+os.environ['KUDA_GRAFANA_PASSWORD']).encode()).decode()})
        OPENER.open(annotation, timeout=3).close()
    except Exception:
        pass


def stop_engine():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(b'StopTestNow', ('127.0.0.1', 4455))


def same_directory(value, folder):
    return str(value or '').replace('\\', '/').lower() == str(folder).replace('\\', '/').lower()


def reasons_for(operations, severe=False):
    count = sum(v['count'] for v in operations.values())
    errors = sum(v['errors'] for v in operations.values())
    reasons = []
    if count >= 100 and errors / count > (.05 if severe else .001):
        reasons.append(f'Ошибки HTTP/проверок: {errors}/{count}')
    for name, limit in LIMITS.items():
        v = operations.get(name)
        if v and v['count'] >= 5:
            threshold = max(2, 4 * limit) if severe else limit
            if v['p95'] > threshold:
                reasons.append(f'{name}: p95={v["p95"]:.3f}s > {threshold}s')
    return reasons


def score_window(window, folder, rate, origin):
    if not same_directory(window.get('directory'), folder):
        return 'inconclusive_monitoring', ['Exporter returned a different phase']
    if window.get('lastIngestAt', 0) < origin + STEP:
        return 'inconclusive_monitoring', ['CSV ingestion has not reached the measurement end']
    operations = window.get('operations', {})
    missing = [key for key in LIMITS if operations.get(key, {}).get('count', 0) < 5]
    if missing:
        return 'inconclusive_samples', ['Too few measured samples: ' + ', '.join(missing)]
    reasons = reasons_for(operations)
    if reasons:
        return 'failed', reasons
    creates = operations['/v1/rooms']['count'] - operations['/v1/rooms']['errors']
    expected = rate * MEASURE / 60
    # Open Model random arrivals fluctuate, especially at the initial low rates.
    # Allow three standard deviations before blaming the generator for underdelivery.
    if creates < max(0, expected - max(.1 * expected, 3 * math.sqrt(expected))):
        return 'inconclusive_delivery', [f'Created {creates} rooms; expected about {expected:g}']
    return 'passed', []


def phase(number, decision):
    global PROCESS
    rate = decision.rate
    folder = RUN / f'phase-{number}'
    folder.mkdir()
    shutil.copy2(ROOT / 'kuda.jmx', folder / 'kuda.jmx')
    members = min(1500, max(24, math.ceil(rate * 5.85)))
    polls = min(3800, max(32, math.ceil(rate * 14.95)))
    properties = folder / 'run.properties'
    properties.write_text(f'stageRates={rate}\nstepSeconds={STEP}\nroomViewSeconds={WARMUP}\n'
                          'responseTimeoutMs=10000\n', encoding='ascii')
    env = os.environ.copy()
    env['HEAP'] = '-Xms1g -Xmx6g -XX:MaxMetaspaceSize=512m'
    env['JVM_ARGS'] = '-Xss512k -Xloggc:' + str(folder / 'gc.log').replace('\\', '/') + (
        ' -XX:+PrintGCDetails -XX:+PrintGCTimeStamps')
    args = [JMETER, '-n', '-t', str(folder / 'kuda.jmx'), '-q', str(properties),
            '-Jhost=127.0.0.1', '-Jmode=load', f'-JparticipantThreads={members}',
            f'-JpollThreads={polls}', f'-JdrainSeconds={DRAIN}', f'-JoutDir={folder}',
            '-Jjmeterengine.nongui.port=4455', '-Jjmeterengine.nongui.maxport=4455',
            '-Jjmeterengine.force.system.exit=true', '-Jdynamic_tg.properties_caching_validity=1000',
            '-Jjmeter.save.saveservice.autoflush=true', '-j', str(folder / 'jmeter.log')]
    record = {'number': number, 'rates': [rate], 'stepSeconds': STEP, 'warmupSeconds': WARMUP,
              'measurementSeconds': MEASURE, 'members': members, 'polls': polls,
              'started': time.time(), 'directory': str(folder), 'purpose': decision.action,
              'selectionReason': decision.reason, 'stages': []}
    PHASES.append(record)
    write_state(directory=str(folder), phase=number, stage=number, status='running', target=rate)
    event(f'Проверка {rate} комнат/мин: 180 с прогрева + 60 с измерения',
          purpose=decision.action, low=SEARCH.low, high=SEARCH.high)
    outcome, reasons, stop_at, origin, severe_since, queue_since, window = None, [], None, None, None, None, None
    last_telemetry = {}
    stdout = (folder / 'console.log').open('w', encoding='utf8')
    try:
        PROCESS = subprocess.Popen([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c',
                                    subprocess.list2cmdline(args)], env=env,
                                   stdout=stdout, stderr=subprocess.STDOUT)
        while PROCESS.poll() is None:
            now, sample = time.time(), {}
            try:
                sample = request('/state')
                if not same_directory(sample.get('directory'), folder):
                    sample = {}
            except Exception:
                pass
            telemetry = sample.get('telemetry', {})
            if telemetry:
                last_telemetry = telemetry
                origin = origin or telemetry.get('phase_started_seconds')
            with (RUN / 'monitor.jsonl').open('a', encoding='utf8') as f:
                f.write(json.dumps({'time': now, 'phase': number, 'target': rate, 'telemetry': telemetry,
                    'rollingOperations120': sample.get('rollingOperations120', {})}, ensure_ascii=False) + '\n')
            if stop_at is None:
                if (RUN / 'stop-requested').exists():
                    outcome, reasons = 'user_stopped', ['User requested termination']
                elif now >= DEADLINE - DRAIN:
                    outcome, reasons = 'budget_exhausted', ['Reserve time to complete active rooms']
                elif not origin and now - record['started'] > 45:
                    outcome, reasons = 'inconclusive_monitoring', ['JMeter phase clock not received']
                elif origin:
                    hard = reasons_for(sample.get('rollingOperations120', {}), severe=True)
                    severe_since = (severe_since or now) if hard and now - origin >= 60 else None
                    age = max(telemetry.get('member_queue_oldest_seconds', 0),
                              telemetry.get('poll_queue_oldest_seconds', 0))
                    queue_since = (queue_since or now) if age > 10 else None
                    if queue_since and now - queue_since >= 30:
                        outcome, reasons = 'inconclusive_generator', [f'Worker jobs queued for {age:.1f}s']
                    elif severe_since and now - severe_since >= 90:
                        outcome, reasons = 'failed', hard
                    elif now >= origin + STEP:
                        reasons = ['All four minutes of new arrivals complete']
                if outcome or (origin and now >= origin + STEP):
                    stop_at = now
                    record.update(stopAt=now, stopDetails='; '.join(reasons))
                    (folder / 'stop-arrivals').write_text('; '.join(reasons), encoding='utf8')
                    event('Новые входы остановлены: ' + '; '.join(reasons))
            if stop_at is not None:
                if outcome is None and origin and now >= origin + STEP + SETTLE:
                    try:
                        params = urllib.parse.urlencode({'from': origin + WARMUP, 'to': origin + STEP})
                        window = request('/window?' + params)
                        outcome, reasons = score_window(window, folder, rate, origin)
                    except Exception as exc:
                        outcome, reasons = 'inconclusive_monitoring', [str(exc)]
                write_state(status='draining', target=0)
                if now - stop_at >= 15 and telemetry and telemetry.get('active_rooms') == 0 and (
                        telemetry.get('member_queue', 0) == 0 and telemetry.get('poll_queue', 0) == 0):
                    if outcome is not None:
                        stop_engine()
                        break
                if now - stop_at > DRAIN or now >= DEADLINE:
                    if outcome != 'failed':
                        outcome, reasons = 'inconclusive_drain', ['Rooms did not finish within the reserve']
                    stop_engine()
                    break
            time.sleep(2)
        try:
            PROCESS.wait(timeout=30)
        except subprocess.TimeoutExpired:
            stop_engine()
            try:
                PROCESS.wait(timeout=15)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(PROCESS.pid), '/T', '/F'], capture_output=True)
                outcome, reasons = 'inconclusive_engine', ['JMeter did not terminate']
        record['exitCode'] = PROCESS.returncode
    finally:
        stdout.close()
    console = (folder / 'console.log').read_text(encoding='utf8', errors='replace')
    if record.get('exitCode') != 0 or any(word in console for word in (
            'Uncaught Exception', 'OutOfMemoryError', 'StackOverflowError', 'Failed to create UDP port')):
        outcome, reasons = 'inconclusive_engine', ['See console.log and jmeter.log']
    room_file = folder / 'rooms.csv'
    rooms = list(csv.DictReader(room_file.open(encoding='utf-8-sig', newline=''))) if room_file.exists() else []
    failures = sum(r['result'] != 'success' for r in rooms)
    if outcome == 'passed':
        if not rooms or len(rooms) != last_telemetry.get('started_rooms'):
            outcome, reasons = 'inconclusive_rooms', ['Not every started room has a final record']
        elif failures / len(rooms) > .01:
            outcome, reasons = 'failed', [f'{failures}/{len(rooms)} complete room scenarios failed']
    if window is not None:
        (folder / 'measurement.json').write_text(json.dumps(window, ensure_ascii=False, indent=2), encoding='utf8')
    outcome = outcome or 'inconclusive_engine'
    record.update(finished=time.time(), outcome=outcome, roomCount=len(rooms), failedRooms=failures)
    record['stages'].append({'rate': rate, 'pass': outcome == 'passed', 'outcome': outcome,
                             'reason': reasons, 'measurementFrom': origin + WARMUP if origin else None,
                             'measurementTo': origin + STEP if origin else None})
    (RUN / 'phases.json').write_text(json.dumps(PHASES, ensure_ascii=False, indent=2), encoding='utf8')
    PROCESS = None
    event(f'Уровень {rate}: {outcome}', reasons=reasons)
    return outcome


try:
    write_state()
    shutil.copy2(ROOT / 'kuda.jmx', RUN / 'kuda.jmx')
    shutil.copy2(__file__, RUN / 'controller-used.py')
    shutil.copy2(STAND / 'capacity_policy.py', RUN / 'capacity-policy-used.py')
    criteria = {'durationLimitSeconds': 3600, 'stageSeconds': STEP, 'warmupSeconds': WARMUP,
                'measurementSeconds': MEASURE, 'settleSeconds': SETTLE, 'latencyLimitsSeconds': LIMITS,
                'errorRateMax': .001, 'roomFailureRateMax': .01, 'resolutionRoomsPerMinute': 1,
                'maximumProbeRate': SEARCH.ceiling, 'hardFailureSustainedSeconds': 90,
                'drainReserveSeconds': DRAIN, 'sharedHostCpuIsNotGeneratorOnly': True,
                'slaStatus': 'working assumptions'}
    (RUN / 'criteria.json').write_text(json.dumps(criteria, indent=2), encoding='utf8')
    event('Поиск: 16, удвоение до первого нарушения, уточнение до 1 комнаты/мин')
    while True:
        decision = SEARCH.next()
        if decision.action == 'stop':
            result = decision.reason
            break
        if (RUN / 'stop-requested').exists():
            result = 'user_stopped'
            break
        if DEADLINE - time.time() < STEP + DRAIN + 30:
            result = 'budget_exhausted'
            break
        outcome = phase(len(PHASES) + 1, decision)
        SEARCH.observe(decision.rate, outcome, confirmation=decision.action == 'confirm')
        write_state(target=0, status='selecting_next_level')
    write_state(running=0, target=0, status=result, ended=time.time())
    event('Нагрузка завершена: ' + result, low=SEARCH.low, high=SEARCH.high, confirmed=SEARCH.confirmed)
except BaseException as exc:
    if PROCESS is not None:
        stop_engine()
        try:
            PROCESS.wait(timeout=30)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(PROCESS.pid), '/T', '/F'], capture_output=True)
    write_state(running=0, target=0, status='failed', error=repr(exc), ended=time.time())
    event('Ошибка контроллера: ' + repr(exc))
finally:
    (RUN / 'events.json').write_text(json.dumps(EVENTS, ensure_ascii=False, indent=2), encoding='utf8')
    (RUN / 'search-history.json').write_text(json.dumps(SEARCH.history, indent=2), encoding='utf8')
    (STAND / 'latest-run.txt').write_text(str(RUN), encoding='utf8')
    print('ARTIFACTS', RUN, flush=True)

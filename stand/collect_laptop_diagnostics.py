"""Capture database waits and WAL/I/O counters with Linux container counters."""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SQL = """
SELECT json_build_object(
 'database_time',extract(epoch FROM clock_timestamp()),
 'room_queue',(SELECT json_build_object('pending',count(*),'oldest_seconds',COALESCE(extract(epoch FROM clock_timestamp()-min(occurred_at)),0)) FROM async_outbox WHERE kind='room'),
 'client_queue',(SELECT json_build_object('pending',count(*),'oldest_seconds',COALESCE(extract(epoch FROM clock_timestamp()-min(occurred_at)),0)) FROM async_outbox WHERE kind='analytics'),
 'async_queue',(SELECT json_build_object('pending',count(*),'oldest_seconds',COALESCE(extract(epoch FROM clock_timestamp()-min(occurred_at)),0)) FROM async_outbox),
 'server_queue',(SELECT json_build_object('pending',count(*),'oldest_seconds',COALESCE(extract(epoch FROM clock_timestamp()-min(occurred_at)),0)) FROM events_outbox WHERE delivered_at IS NULL),
 'wal',(SELECT row_to_json(w) FROM pg_stat_wal w),
 'io',(SELECT json_agg(i) FROM pg_stat_io i),
 'checkpoints',(SELECT row_to_json(b) FROM pg_stat_bgwriter b),
 'database',(SELECT row_to_json(d) FROM pg_stat_database d WHERE datname=current_database()),
 'waits',(SELECT json_agg(w) FROM (
   SELECT state,coalesce(wait_event_type,'CPU') AS type,coalesce(wait_event,'running') AS event,count(*) AS count
   FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()
   AND backend_type='client backend' GROUP BY 1,2,3) w),
 'waiting_queries',(SELECT json_agg(w) FROM (
   SELECT pid,query_id,state,wait_event_type,wait_event,
   extract(epoch FROM clock_timestamp()-query_start) AS query_age_seconds,
   CASE WHEN wait_event_type='Lock' THEN pg_blocking_pids(pid) ELSE ARRAY[]::integer[] END AS blockers
   FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()
   AND state='active' AND wait_event IS NOT NULL ORDER BY query_start LIMIT 30) w),
 'locks',(SELECT json_agg(l) FROM (
   SELECT locktype,mode,count(*) AS count FROM pg_locks WHERE NOT granted GROUP BY 1,2) l)
);
"""
FILES = ['/proc/diskstats', '/proc/pressure/io', '/proc/pressure/cpu', '/proc/pressure/memory',
         '/sys/fs/cgroup/io.stat', '/sys/fs/cgroup/cpu.stat',
         '/sys/fs/cgroup/memory.current', '/sys/fs/cgroup/memory.events']
SNAPSHOT = {}
LOCK = threading.Lock()
PROJECT = os.environ.get('KUDA_COMPOSE_PROJECT','kuda-nt')
DB_CONTAINER = PROJECT+'-postgres-1'


def collect():
    started = time.time()
    query = SQL.replace('FROM pg_stat_bgwriter b','FROM pg_stat_checkpointer b') if PROJECT == 'kuda-pgrust' else SQL
    result = subprocess.run(['docker', 'exec', '-e', 'PGAPPNAME=kuda_diagnostics',
        '-e', 'PGOPTIONS=-c statement_timeout=2000', DB_CONTAINER,
        'psql', '-XAt', '-U', 'kuda', '-d', 'kuda', '-c', query],
        capture_output=True, text=True, encoding='utf8', timeout=8, check=True)
    sample = json.loads(result.stdout)
    if PROJECT == 'kuda-pgrust':
        checkpoints = sample.get('checkpoints') or {}
        for destination, source in [('checkpoint_write_time','write_time'),('checkpoint_sync_time','sync_time')]:
            if source in checkpoints:
                checkpoints[destination] = checkpoints[source]
    if 'wal_sync' not in sample.get('wal',{}):
        # PostgreSQL 18 moved WAL write/fsync counts and timings to pg_stat_io.
        wal_io = [row for row in sample.get('io') or [] if row.get('object') == 'wal']
        if wal_io:
            for destination, source in [('wal_sync','fsyncs'),('wal_sync_time','fsync_time'),('wal_write','writes'),('wal_write_time','write_time')]:
                sample['wal'][destination] = sum(row.get(source) or 0 for row in wal_io)
            sample['wal_timing_source'] = 'pg_stat_io/object=wal'
    script = 'for f in ' + ' '.join(FILES) + '; do echo "FILE $f"; cat "$f"; done'
    result = subprocess.run(['docker', 'exec', DB_CONTAINER, 'sh', '-c', script],
        capture_output=True, text=True, timeout=8, check=True)
    sample['linux'] = {}
    current = None
    for line in result.stdout.splitlines():
        if line.startswith('FILE '):
            current = line[5:]
            sample['linux'][current] = []
        elif current:
            sample['linux'][current].append(line)
    sample.update(collected_at=time.time(), collection_seconds=time.time()-started)
    return sample


def metrics(sample):
    lines = []

    def emit(name, value, labels=None):
        if not isinstance(value, (int, float)):
            return
        suffix = '{' + ','.join(k+'='+json.dumps(str(v)) for k, v in labels.items()) + '}' if labels else ''
        lines.append(f'{name}{suffix} {value}')

    emit('kuda_pg_diagnostics_timestamp_seconds', sample.get('collected_at'))
    emit('kuda_pg_diagnostics_collection_seconds', sample.get('collection_seconds'))
    for queue in ('async_queue', 'server_queue', 'room_queue', 'client_queue'):
        for key, value in sample.get(queue, {}).items():
            emit('kuda_pg_'+queue+'_'+key, value)
    for key, value in sample.get('wal', {}).items():
        if key.endswith('_time'):
            emit('kuda_pg_'+key+'_seconds_total', value/1000)
        elif isinstance(value, (int, float)):
            emit('kuda_pg_'+key+'_total', value)
    for item in sample.get('io') or []:
        labels = {k: item[k] for k in ('backend_type', 'object', 'context')}
        for key in ('reads', 'writes', 'writebacks', 'extends', 'hits', 'evictions', 'fsyncs'):
            emit('kuda_pg_io_'+key+'_total', item[key], labels)
        for key in ('read_time', 'write_time', 'writeback_time', 'extend_time', 'fsync_time'):
            value = item[key]
            if value is not None:
                emit('kuda_pg_io_'+key+'_seconds_total', value/1000, labels)
    for item in sample.get('waits') or []:
        emit('kuda_pg_activity', item['count'], {k: item[k] for k in ('state', 'type', 'event')})
    for item in sample.get('locks') or []:
        emit('kuda_pg_waiting_locks', item['count'], {k: item[k] for k in ('locktype', 'mode')})
    for key in ('checkpoint_write_time', 'checkpoint_sync_time'):
        value = (sample.get('checkpoints') or {}).get(key)
        if isinstance(value, (int,float)):
            emit('kuda_pg_'+key+'_seconds_total', value/1000)
    for path, content in sample.get('linux', {}).items():
        if path.startswith('/proc/pressure/'):
            for line in content:
                parts = line.split()
                values = dict(part.split('=') for part in parts[1:])
                emit('kuda_linux_pressure_seconds_total', int(values['total'])/1e6,
                     {'resource': path.rsplit('/', 1)[-1], 'scope': parts[0]})
    return '\n'.join(lines)+'\n'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        with LOCK:
            snapshot = SNAPSHOT
        body = (json.dumps(snapshot) if self.path == '/state' else metrics(snapshot)).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json' if self.path == '/state' else 'text/plain; version=0.0.4')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def capture_logs(directory, stop):
    started_file = directory/'run-started.txt'
    start = float(started_file.read_text(encoding='utf-8-sig').strip()) if started_file.exists() else time.time()
    services = ('api','postgres','redis','geography') if PROJECT == 'kuda-pgrust' else ('api','postgres','redis')
    cursors = {service: start for service in services}
    while True:
        end = time.time()
        for service in cursors:
            try:
                result = subprocess.run(['docker', 'logs', '--timestamps', '--since',
                    datetime.datetime.fromtimestamp(cursors[service], datetime.timezone.utc).isoformat(),
                    '--until', datetime.datetime.fromtimestamp(end, datetime.timezone.utc).isoformat(),
                    PROJECT+'-'+service+'-1'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, timeout=8, check=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                with (directory/(service+'-live.log')).open('ab') as output:
                    output.write(result.stdout)
                cursors[service] = end
            except Exception as exc:
                with (directory/'log-capture-errors.jsonl').open('a',encoding='utf8') as output:
                    output.write(json.dumps({'time':time.time(),'service':service,'error':repr(exc)})+'\n')
        if stop.is_set():
            return
        stop.wait(30)


def main():
    global SNAPSHOT, PROJECT, DB_CONTAINER
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=pathlib.Path)
    parser.add_argument('--project', choices=['kuda-nt','kuda-pgrust','kuda-backend'], default=PROJECT)
    args = parser.parse_args()
    PROJECT = args.project
    DB_CONTAINER = PROJECT+'-postgres-1'
    threading.Thread(target=ThreadingHTTPServer(('0.0.0.0', 9200), Handler).serve_forever, daemon=True).start()
    log_stop = threading.Event()
    log_thread = threading.Thread(target=capture_logs, args=(args.run,log_stop), daemon=True)
    log_thread.start()
    try:
        with (args.run/'db-diagnostics.jsonl').open('a', encoding='utf8') as output:
            while not (args.run/'stop-diagnostics').exists():
                started = time.monotonic()
                try:
                    sample = collect()
                    with LOCK:
                        SNAPSHOT = sample
                except Exception as exc:
                    sample = {'collected_at': time.time(), 'error': repr(exc)}
                output.write(json.dumps(sample)+'\n')
                output.flush()
                time.sleep(max(.05, 5-(time.monotonic()-started)))
    finally:
        log_stop.set()
        log_thread.join(timeout=28)


if __name__ == '__main__':
    main()

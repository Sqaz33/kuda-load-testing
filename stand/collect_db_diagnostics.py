"""Capture database waits and WAL/I/O counters with Linux container counters."""
import argparse
import json
import pathlib
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SQL = """
SELECT json_build_object(
 'database_time',extract(epoch FROM clock_timestamp()),
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


def collect():
    started = time.time()
    result = subprocess.run(['docker', 'exec', '-e', 'PGAPPNAME=kuda_diagnostics',
        '-e', 'PGOPTIONS=-c statement_timeout=2000', 'kuda-backend-postgres-1',
        'psql', '-XAt', '-U', 'kuda', '-d', 'kuda', '-c', SQL],
        capture_output=True, text=True, encoding='utf8', timeout=8, check=True)
    sample = json.loads(result.stdout)
    script = 'for f in ' + ' '.join(FILES) + '; do echo "FILE $f"; cat "$f"; done'
    result = subprocess.run(['docker', 'exec', 'kuda-backend-postgres-1', 'sh', '-c', script],
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
        emit('kuda_pg_'+key+'_seconds_total', sample.get('checkpoints', {}).get(key, 0)/1000)
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


def main():
    global SNAPSHOT
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=pathlib.Path)
    args = parser.parse_args()
    threading.Thread(target=ThreadingHTTPServer(('0.0.0.0', 9200), Handler).serve_forever, daemon=True).start()
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
            time.sleep(max(.05, 1-(time.monotonic()-started)))


if __name__ == '__main__':
    main()

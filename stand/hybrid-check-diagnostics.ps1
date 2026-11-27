$env:KUDA_COMPOSE_PROJECT='kuda-pgrust'
$env:PYTHONIOENCODING='utf-8'
Set-Location 'C:/Users/mset6/kuda-pgrust'
C:/Python313/python.exe -c "import collect_diagnostics as c; s=c.collect(); print('diagnostics',s.get('collection_seconds'),'wal_source',s.get('wal_timing_source')); print('wal',s.get('wal')); print('metrics_lines',len(c.metrics(s).splitlines()))"
docker logs --tail 3 kuda-pgrust-api-1

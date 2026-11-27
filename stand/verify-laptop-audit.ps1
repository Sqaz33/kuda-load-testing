[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Set-Location C:/Users/mset6/kuda-nt
docker compose exec -T postgres psql -X -U kuda -d kuda -c "SELECT count(*) AS statements, sum(calls) AS calls FROM pg_stat_statements; SHOW track_io_timing; SHOW track_wal_io_timing; SHOW log_min_duration_statement; SHOW log_lock_waits;"
docker inspect kuda-nt-api-1 --format '{{json .HostConfig.LogConfig}}'
Get-Item C:/Users/mset6/kuda-nt/artifacts/20261127-130302-capacity/db-diagnostics.jsonl | Select Length

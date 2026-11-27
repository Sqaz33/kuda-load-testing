[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c "SELECT deadlocks,conflicts FROM pg_stat_database WHERE datname='kuda';"
docker logs --since 5m kuda-nt-postgres-1 2>&1 | Select-String -Pattern 'deadlock detected|Process .* waits|Process .*UPDATE|Process .*INSERT' -Context 0,2 | Select-Object -First 16 | ForEach-Object {$_.ToString()}

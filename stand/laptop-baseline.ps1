[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Set-Location C:/Users/mset6/kuda-nt
docker compose exec -T postgres psql -X -U kuda -d kuda -c "SELECT count(*) AS venues FROM venues;"
docker compose exec -T postgres psql -X -U kuda -d kuda -c "SHOW max_connections; SHOW track_wal_io_timing; SELECT pg_stat_statements_reset();"
docker inspect kuda-nt-api-1 --format 'RAM={{.HostConfig.Memory}} CPUquota={{.HostConfig.NanoCpus}}'
Get-NetAdapter | ForEach-Object {"$($_.Name) $($_.Status) $($_.LinkSpeed)"}

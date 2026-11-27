[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c "SELECT deadlocks FROM pg_stat_database WHERE datname='kuda'; SELECT calls, rows, left(query,160) AS query FROM pg_stat_statements WHERE query LIKE 'UPDATE sessions SET revision%';"
Get-ScheduledTask -TaskName 'Kuda-PG-Diagnostics*' | Select-Object TaskName,State

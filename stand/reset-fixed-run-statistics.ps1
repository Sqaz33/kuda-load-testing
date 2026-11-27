[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c 'SELECT pg_stat_statements_reset(); SELECT pg_stat_reset();'

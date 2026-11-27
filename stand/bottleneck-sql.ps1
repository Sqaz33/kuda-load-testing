[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
docker exec kuda-nt-postgres-1 psql -X -A -F "|" -U kuda -d kuda -c "SELECT queryid,calls,round(total_exec_time::numeric,0) AS total_ms,round(mean_exec_time::numeric,2) AS mean_ms,rows,shared_blks_read,temp_blks_written,left(regexp_replace(query,E'[\n\r]+',' ','g'),900) AS query FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname='kuda') ORDER BY total_exec_time DESC LIMIT 10;"

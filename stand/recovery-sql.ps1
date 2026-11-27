[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
docker exec kuda-nt-postgres-1 psql -X -A -F "|" -U kuda -d kuda -c "SELECT calls,round(total_exec_time::numeric,0) AS total_ms,round(mean_exec_time::numeric,2) AS mean_ms,rows,left(regexp_replace(query,E'[\n\r]+',' ','g'),160) AS query FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname='kuda') ORDER BY total_exec_time DESC LIMIT 7;"
Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes,PagesInputPersec,PagesOutputPersec,PageReadsPersec,PercentCommittedBytesInUse | ConvertTo-Json -Compress
Get-CimInstance Win32_PerfFormattedData_Counters_ProcessorInformation | Where-Object Name -eq '_Total' | Select PercentProcessorPerformance,ProcessorFrequency,PercentProcessorUtility | ConvertTo-Json -Compress

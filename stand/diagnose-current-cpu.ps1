[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$cores=(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
$a=@{}
Get-Process | ForEach-Object {try{$a[$_.Id]=$_.CPU}catch{}}
$sw=[Diagnostics.Stopwatch]::StartNew()
Start-Sleep -Seconds 5
$b=Get-Process | Select Id,Name,CPU
$secs=$sw.Elapsed.TotalSeconds
$b | ForEach-Object {if($a.ContainsKey($_.Id)){[pscustomobject]@{name=$_.Name;pid=$_.Id;cpuPct=[math]::Round(100*($_.CPU-$a[$_.Id])/$secs/$cores,1)}}} | Sort-Object cpuPct -Descending | Select -First 8 | ConvertTo-Json -Compress
docker stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} RAM={{.MemUsage}}'
docker exec kuda-nt-postgres-1 psql -X -A -F "|" -U kuda -d kuda -c "SELECT queryid,calls,round(total_exec_time::numeric,0) AS total_ms,round(mean_exec_time::numeric,2) AS mean_ms,left(regexp_replace(query,E'[\n\r]+',' ','g'),180) AS query FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname='kuda') ORDER BY total_exec_time DESC LIMIT 6;"

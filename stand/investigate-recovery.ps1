[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-CimInstance Win32_OperatingSystem | Select FreePhysicalMemory,TotalVisibleMemorySize | ConvertTo-Json -Compress
Get-CimInstance Win32_Battery | Select BatteryStatus,EstimatedChargeRemaining | ConvertTo-Json -Compress
docker stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} MEM={{.MemUsage}} NET={{.NetIO}} DISK={{.BlockIO}}'
$a=Get-Process | Select Id,Name,CPU,WorkingSet64
Start-Sleep -Seconds 3
$b=Get-Process
$b | ForEach-Object {$v=$_; $old=$a | Where-Object Id -eq $v.Id; if($old){[pscustomobject]@{Name=$v.Name;CpuSeconds=$v.CPU-$old.CPU;RAM=$v.WorkingSet64}}} | Sort-Object CpuSeconds -Descending | Select -First 10 | ConvertTo-Json -Compress
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c "SELECT state,wait_event_type,wait_event,count(*) FROM pg_stat_activity WHERE backend_type='client backend' GROUP BY 1,2,3; SELECT locktype,mode,count(*) FROM pg_locks WHERE NOT granted GROUP BY 1,2;"

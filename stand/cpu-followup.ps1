[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$cores=(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
$before=@{}
Get-Process | ForEach-Object {try{$before[$_.Id]=$_.CPU}catch{}}
$start=[Diagnostics.Stopwatch]::StartNew()
Start-Sleep -Seconds 10
$after=Get-Process | Select Id,Name,CPU,WorkingSet64
$seconds=$start.Elapsed.TotalSeconds
$after | ForEach-Object {if($before.ContainsKey($_.Id)){[pscustomobject]@{pid=$_.Id;name=$_.Name;cpuPercent=[math]::Round(100*($_.CPU-$before[$_.Id])/$seconds/$cores,1)}}} | Sort-Object cpuPercent -Descending | Select -First 10 | ConvertTo-Json -Compress
Get-CimInstance Win32_Process -Filter "ProcessId=19692" | Select ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress
wsl -d docker-desktop -- sh -c "top -b -n 1 | head -22"

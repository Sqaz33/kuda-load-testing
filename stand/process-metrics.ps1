[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$before=@{}
Get-Process | ForEach-Object {$before[$_.Id]=$_.CPU}
$clock=[Diagnostics.Stopwatch]::StartNew()
Start-Sleep -Seconds 2
Get-Process | Where-Object {$before.ContainsKey($_.Id)} | ForEach-Object {[pscustomobject]@{name=$_.Name;pid=$_.Id;cpuCores=($_.CPU-$before[$_.Id])/$clock.Elapsed.TotalSeconds;memory=$_.WorkingSet64}} | Sort-Object cpuCores -Descending | Select-Object -First 10 | ConvertTo-Json
$path='"C:\Users\mset6\kuda-nt\windows_exporter.exe" --collectors.enabled=cpu,memory,logical_disk,physical_disk,net,os,system,process --collector.process.include=(?i)^(com.docker.backend|vmmemWSL|MsMpEng|Memory.Compression|System|telegraf|windows_exporter)$ --web.listen-address=192.168.0.213:9182'
Set-ItemProperty -LiteralPath HKLM:\SYSTEM\CurrentControlSet\Services\KudaWindowsExporter -Name ImagePath -Value $path
Restart-Service KudaWindowsExporter

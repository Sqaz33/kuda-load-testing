$ErrorActionPreference='Stop'
$exporterPath='D:\kuda-load-testing\stand\windows_exporter.exe'
$existing=Get-CimInstance Win32_Process -Filter "Name='windows_exporter.exe'" | Where-Object ExecutablePath -eq $exporterPath
foreach($process in $existing){Stop-Process -Id $process.ProcessId -Force}
$exporterArgs=@(
 '--collectors.enabled=cpu,memory,logical_disk,physical_disk,net,os,system,process'
 '--collector.process.include=(?i)^(java|javaw|com.docker.backend|vmmemWSL|MsMpEng|System|python|telegraf)$'
 '--web.listen-address=192.168.0.242:9183'
)
Start-Process -FilePath $exporterPath -ArgumentList $exporterArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\windows-exporter-stdout.log" -RedirectStandardError "$PSScriptRoot\windows-exporter-stderr.log"

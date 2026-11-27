[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
quser
Start-Service com.docker.service
$action=New-ScheduledTaskAction -Execute 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -Argument '--background'
$principal=New-ScheduledTaskPrincipal -UserId 'mset6' -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskName 'Kuda-NT-Docker' -Action $action -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName 'Kuda-NT-Docker'
Get-ScheduledTaskInfo 'Kuda-NT-Docker' | ConvertTo-Json

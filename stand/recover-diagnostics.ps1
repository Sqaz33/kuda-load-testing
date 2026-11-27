[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-Content C:/Users/mset6/kuda-nt/artifacts/20261127-130302-capacity/diagnostic-stderr.log -Tail 8
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId,CommandLine
$action=New-ScheduledTaskAction -Execute 'C:/Python313/python.exe' -Argument '-u C:/Users/mset6/kuda-nt/collect_diagnostics.py C:/Users/mset6/kuda-nt/artifacts/20261127-130302-capacity' -WorkingDirectory 'C:/Users/mset6/kuda-nt'
$principal=New-ScheduledTaskPrincipal -UserId mset6 -LogonType Interactive -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName Kuda-PG-Diagnostics -Action $action -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask Kuda-PG-Diagnostics

$ErrorActionPreference='Stop'
New-Item -ItemType File -Force C:/Users/mset6/kuda-nt/artifacts/20261127-140443-capacity/stop-diagnostics | Out-Null
Start-Sleep -Seconds 7
Stop-ScheduledTask -TaskName Kuda-PG-Diagnostics-20261127-141012-capacity
Start-Sleep -Seconds 1
Start-ScheduledTask -TaskName Kuda-PG-Diagnostics-20261127-141012-capacity
Start-Sleep -Seconds 3
Get-ScheduledTaskInfo Kuda-PG-Diagnostics-20261127-141012-capacity | Select LastRunTime,LastTaskResult | ConvertTo-Json -Compress

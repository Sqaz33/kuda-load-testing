[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$state=@{time=(Get-Date).ToString('o');services=@();defragTask=$null}
$task=Get-ScheduledTask -TaskPath '\Microsoft\Windows\Defrag\' -TaskName ScheduledDefrag
$state.defragTask=@{enabled=$task.Settings.Enabled;state=$task.State.ToString()}
if($task.Settings.Enabled){Disable-ScheduledTask -InputObject $task | Out-Null}
if($task.State -eq 'Running'){Stop-ScheduledTask -InputObject $task}
Get-Service 'clr_optimization*' -ErrorAction SilentlyContinue | ForEach-Object {
 $state.services+=@{name=$_.Name;status=$_.Status.ToString()}
 if($_.Status -eq 'Running' -and $_.CanStop){Stop-Service -Name $_.Name}
}
$state | ConvertTo-Json -Depth 5 | Set-Content C:\Users\mset6\kuda-nt\maintenance-state.json -Encoding utf8
Get-Service defragsvc,'clr_optimization*' -ErrorAction SilentlyContinue | Select Name,Status | ConvertTo-Json

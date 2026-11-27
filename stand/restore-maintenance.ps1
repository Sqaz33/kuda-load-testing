[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$state=Get-Content C:\Users\mset6\kuda-nt\maintenance-state.json -Raw|ConvertFrom-Json
if($state.defragTask.enabled){Enable-ScheduledTask -TaskPath '\Microsoft\Windows\Defrag\' -TaskName ScheduledDefrag | Out-Null}
foreach($task in $state.ngenTasks){
 if($task.enabled){Enable-ScheduledTask -TaskPath '\Microsoft\Windows\.NET Framework\' -TaskName $task.name | Out-Null}
 if($task.state -eq 'Running'){Start-ScheduledTask -TaskPath '\Microsoft\Windows\.NET Framework\' -TaskName $task.name}
}
foreach($service in $state.services){if($service.status -eq 'Running'){Start-Service $service.name}}
if($state.defragTask.state -eq 'Running' -or $state.defragServiceRunning){Start-ScheduledTask -TaskPath '\Microsoft\Windows\Defrag\' -TaskName ScheduledDefrag}
@{restored=(Get-Date).ToString('o');tasks=@(Get-ScheduledTask -TaskPath '\Microsoft\Windows\.NET Framework\','\Microsoft\Windows\Defrag\'|Select TaskPath,TaskName,State,@{n='Enabled';e={$_.Settings.Enabled}})} | ConvertTo-Json -Depth 5 | Set-Content C:\Users\mset6\kuda-nt\maintenance-restored.json -Encoding utf8
Write-Output 'Windows automatic maintenance settings restored.'
if(Get-ScheduledTask -TaskName 'Kuda-NT-RestoreMaintenance' -ErrorAction SilentlyContinue){Unregister-ScheduledTask -TaskName 'Kuda-NT-RestoreMaintenance' -Confirm:$false}

[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$state=Get-Content C:\Users\mset6\kuda-nt\maintenance-state.json -Raw|ConvertFrom-Json
$tasks=@(Get-ScheduledTask -TaskPath '\Microsoft\Windows\.NET Framework\' -ErrorAction SilentlyContinue)
$state|Add-Member -NotePropertyName ngenTasks -NotePropertyValue @($tasks|ForEach-Object {@{name=$_.TaskName;enabled=$_.Settings.Enabled;state=$_.State.ToString()}}) -Force
$state|Add-Member -NotePropertyName defragServiceRunning -NotePropertyValue ((Get-Service defragsvc).Status -eq 'Running') -Force
$state|ConvertTo-Json -Depth 6|Set-Content C:\Users\mset6\kuda-nt\maintenance-state.json -Encoding utf8
foreach($task in $tasks){
 if($task.Settings.Enabled){Disable-ScheduledTask -InputObject $task|Out-Null}
 if($task.State -eq 'Running'){Stop-ScheduledTask -InputObject $task}
}
Stop-Service defragsvc
$tasks|Select TaskPath,TaskName,State|ConvertTo-Json
Get-CimInstance Win32_Process -Filter "Name='mscorsvw.exe'"|Select ProcessId,ParentProcessId,CommandLine|ConvertTo-Json

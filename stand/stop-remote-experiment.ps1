$ErrorActionPreference='Stop'
$task=Get-ScheduledTask -TaskName 'Kuda-Pgrust-Recovery' -ErrorAction SilentlyContinue
if($task){Stop-ScheduledTask -TaskName 'Kuda-Pgrust-Recovery'; Disable-ScheduledTask -TaskName 'Kuda-Pgrust-Recovery' | Out-Null}
docker ps -q --filter label=com.docker.compose.project=kuda-pgrust | ForEach-Object {docker stop --time 5 $_}

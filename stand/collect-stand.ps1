param([Parameter(Mandatory=$true)][string]$RunDirectory)
$ErrorActionPreference='Stop'
$run=Get-Item -LiteralPath $RunDirectory
$state=Get-Content -LiteralPath (Join-Path $run.FullName 'status.json') -Raw | ConvertFrom-Json
$runName=$run.Name
if($runName -notmatch '^[0-9-]+-(capacity|controller-check)$'){throw 'Unexpected run directory name'}
$since=[DateTimeOffset]::FromUnixTimeMilliseconds([long]($state.started*1000)).UtcDateTime.ToString('o')
$remoteRoot=if($state.remoteRoot){$state.remoteRoot}else{'C:/Users/mset6/kuda-nt'}
if($remoteRoot -notin @('C:/Users/mset6/kuda-nt','C:/Users/mset6/kuda-pgrust')){throw 'Unexpected stand directory'}
$services=if($state.composeProject -eq 'kuda-pgrust'){"'api','postgres','redis','postgres-exporter','geography','geography-exporter'"}else{"'api','postgres','redis','postgres-exporter','cadvisor'"}
$script=@'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$OutputEncoding=[Text.UTF8Encoding]::new($false)
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location 'REMOTE_ROOT'
$directory='REMOTE_ROOT/artifacts/RUN_NAME'
New-Item -ItemType Directory -Force $directory|Out-Null
foreach($service in @(SERVICE_LIST)) {
 docker compose logs --no-color --timestamps --since 'SINCE_TIME' $service 2>&1 | Set-Content -LiteralPath (Join-Path $directory ($service+'.log')) -Encoding utf8
}
docker compose ps --format json | Set-Content (Join-Path $directory 'containers.json') -Encoding utf8
docker stats --no-stream --format '{{json .}}' | Set-Content (Join-Path $directory 'docker-stats.jsonl') -Encoding utf8
foreach($service in @('api','postgres','redis')) {
 $id=docker compose ps -q $service
 docker inspect --format '{{json .State}}' $id | Set-Content (Join-Path $directory ($service+'-state.json')) -Encoding utf8
 docker inspect --format '{{json .HostConfig}}' $id | Set-Content (Join-Path $directory ($service+'-resources.json')) -Encoding utf8
}
$sql=@"
COPY (SELECT queryid,calls,total_exec_time,mean_exec_time,max_exec_time,rows,shared_blks_hit,shared_blks_read,temp_blks_written,query FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) ORDER BY total_exec_time DESC LIMIT 200) TO STDOUT WITH CSV HEADER
"@
docker compose exec -T postgres psql -X -U kuda -d kuda -c $sql | Set-Content (Join-Path $directory 'pg-stat-statements.csv') -Encoding utf8
$sql=@"
SELECT jsonb_build_object('time',now(),'database',(SELECT to_jsonb(s) FROM pg_stat_database s WHERE datname='kuda'),'activity',(SELECT jsonb_agg(to_jsonb(a)) FROM pg_stat_activity a WHERE datname='kuda'),'locks',(SELECT jsonb_agg(to_jsonb(l)) FROM pg_locks l),'size_bytes',pg_database_size('kuda'));
"@
docker compose exec -T postgres psql -X -A -t -U kuda -d kuda -c $sql | Set-Content (Join-Path $directory 'postgres-snapshot.json') -Encoding utf8
@{cpu=@(Get-CimInstance Win32_Processor|Select Name,NumberOfCores,NumberOfLogicalProcessors);os=Get-CimInstance Win32_OperatingSystem|Select Caption,TotalVisibleMemorySize,FreePhysicalMemory,LocalDateTime;network=@(Get-NetAdapter|Select Name,Status,LinkSpeed);disks=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'|Select DeviceID,Size,FreeSpace)}|ConvertTo-Json -Depth 5 | Set-Content (Join-Path $directory 'hardware.json') -Encoding utf8
Get-WinEvent -FilterHashtable @{LogName='System';StartTime=[DateTime]'SINCE_TIME';Level=1,2,3} -ErrorAction SilentlyContinue | Select TimeCreated,Id,ProviderName,LevelDisplayName,Message | Export-Csv (Join-Path $directory 'windows-system-events.csv') -Encoding UTF8 -NoTypeInformation
Copy-Item compose.yaml,telegraf.conf -Destination $directory
if(Test-Path 'pgrust-recovery.jsonl'){Copy-Item 'pgrust-recovery.jsonl' -Destination $directory}
$zip=$directory+'.zip'
Compress-Archive -Path ($directory+'\*') -DestinationPath $zip -Force
Write-Output ('ZIP_SHA256='+(Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash)
Write-Output ('ZIP_BYTES='+(Get-Item -LiteralPath $zip).Length)
'@
$script=$script.Replace('RUN_NAME',$runName).Replace('SINCE_TIME',$since).Replace('REMOTE_ROOT',$remoteRoot).Replace('SERVICE_LIST',$services)
$scriptPath=Join-Path $run.FullName 'collect-remote.ps1'
Set-Content -LiteralPath $scriptPath -Value $script -Encoding utf8
$output=& "$PSScriptRoot\remote.ps1" ps $scriptPath
$output | Set-Content -LiteralPath (Join-Path $run.FullName 'collect-remote.log') -Encoding utf8
if($LASTEXITCODE){throw 'Remote artifact collection failed'}
$zip=Join-Path $run.FullName 'stand-logs.zip'
& "$PSScriptRoot\remote.ps1" get "$remoteRoot/artifacts/$runName.zip" $zip
if($LASTEXITCODE){throw 'Remote artifact download failed'}
$match=[regex]::Match(($output -join "`n"),'ZIP_SHA256=([A-F0-9]{64})')
if(!$match.Success -or (Get-FileHash -LiteralPath $zip).Hash -ne $match.Groups[1].Value){throw 'Downloaded archive checksum mismatch'}
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $run.FullName 'stand-logs') -Force
Write-Host "Логи стенда сохранены: $zip"

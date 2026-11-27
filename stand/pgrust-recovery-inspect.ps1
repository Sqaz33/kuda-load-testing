$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
docker inspect kuda-pgrust-postgres-1 --format '{{json .State}}'
docker inspect kuda-pgrust-postgres-1 --format '{{json .Config.Entrypoint}} {{json .Config.Cmd}} {{json .HostConfig.RestartPolicy}}'
docker exec kuda-pgrust-postgres-1 psql -XAt -U kuda -d kuda -c 'SHOW restart_after_crash; SELECT pg_postmaster_start_time();'
Get-ScheduledTask -TaskName 'Kuda*' | Select-Object TaskName,State | ConvertTo-Json

$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$dir='C:/Users/mset6/kuda-pgrust'
$sql=@"
SELECT jsonb_build_object('time',now(),'activity',(SELECT jsonb_agg(x) FROM (SELECT state,backend_type,count(*) FROM pg_stat_activity WHERE datname='kuda' GROUP BY 1,2)x),'settings',(SELECT jsonb_object_agg(name,setting) FROM pg_settings WHERE name IN ('max_connections','shared_buffers','work_mem','track_io_timing','track_wal_io_timing') OR name LIKE 'pgrust.%'),'memory_contexts',(SELECT jsonb_agg(x) FROM (SELECT name,total_bytes,used_bytes FROM pg_backend_memory_contexts ORDER BY total_bytes DESC LIMIT 15)x));
"@
docker exec kuda-pgrust-postgres-1 psql -XAt -U kuda -d kuda -c $sql | Set-Content "$dir/memory-diagnosis.json" -Encoding utf8
if($LASTEXITCODE){throw 'Memory diagnosis query failed'}
$diag=Get-Content "$dir/memory-diagnosis.json" -Raw | ConvertFrom-Json
$diag.activity | ConvertTo-Json
$diag.settings.psobject.Properties | Where-Object {$_.Name -match 'memory|cache|grant|pool|work_mem|connections'} | ForEach-Object {Write-Output ($_.Name+'='+$_.Value)}
$diag.memory_contexts | ConvertTo-Json
 docker exec kuda-pgrust-postgres-1 sh -c 'cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.events /proc/pressure/memory'

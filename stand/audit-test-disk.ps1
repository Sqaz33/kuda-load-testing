[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select DeviceID,Size,FreeSpace | ConvertTo-Json -Compress
docker system df
docker ps -a --format '{{.Names}} {{.Status}}'
Set-Location C:/Users/mset6/kuda-nt
Get-ChildItem -File | Select Name,Length | ConvertTo-Json -Compress
Get-ChildItem artifacts -Directory | ForEach-Object {$m=Get-ChildItem $_.FullName -File -Recurse | Measure-Object Length -Sum; "$($_.Name): $($m.Sum) bytes"}
docker inspect kuda-nt-api-1 kuda-nt-postgres-1 --format '{{.Name}} LOG={{.LogPath}}'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c "SELECT pg_size_pretty(pg_database_size('kuda')); SELECT relname,pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 12;"

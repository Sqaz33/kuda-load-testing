$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$path='C:/Users/mset6/kuda-pgrust'
New-Item -ItemType Directory -Force $path | Out-Null
Copy-Item 'C:/Users/mset6/kuda-nt/telegraf.conf' "$path/telegraf.conf"
docker exec kuda-nt-postgres-1 psql -XAt -U kuda -d kuda -c 'SELECT count(*) FROM venues;'
docker exec kuda-nt-postgres-1 sh -c 'pg_dump -U kuda -d kuda --data-only --no-owner --no-privileges -t cities -t districts -t categories -t diets -t venues -t venue_categories -t venue_tags -t venue_photos -t venue_sources -t geocoded_addresses > /tmp/hybrid-geography-catalog.sql'
if($LASTEXITCODE){throw 'Catalog export failed'}
docker cp kuda-nt-postgres-1:/tmp/hybrid-geography-catalog.sql "$path/geography-catalog.sql"
if($LASTEXITCODE){throw 'Catalog copy failed'}
Get-Item "$path/geography-catalog.sql" | Select-Object Name,Length | ConvertTo-Json
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,FreeSpace | ConvertTo-Json

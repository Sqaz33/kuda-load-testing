[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
docker info --format 'CPU={{.NCPU}} MEM={{.MemTotal}} SERVER={{.ServerVersion}}'
docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}'
Get-Process '*docker*' -ErrorAction SilentlyContinue | Select Name,Id,SessionId | ConvertTo-Json

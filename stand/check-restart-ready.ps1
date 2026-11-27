[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Set-Location C:/Users/mset6/kuda-nt
docker ps -a --format '{{.Names}} {{.Status}}'
docker volume ls --format '{{.Name}}'
docker images venue-backend --format '{{.Repository}}:{{.Tag}} {{.ID}}'
Get-ChildItem -File | Select Name,Length | ConvertTo-Json -Compress

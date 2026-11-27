[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location C:/Users/mset6/kuda-nt
docker load -i backend-updated.tar
if ($LASTEXITCODE) {throw 'Image load failed'}
docker compose up -d
if ($LASTEXITCODE) {throw 'API deployment failed'}
docker compose ps --format '{{.Name}} {{.State}}'
docker inspect kuda-nt-api-1 --format '{{.Image}}'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c 'SELECT pg_stat_statements_reset(); SELECT pg_stat_reset();'
if ($LASTEXITCODE) {throw 'Statistics reset failed'}

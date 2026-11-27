[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location C:/Users/mset6/kuda-nt
docker compose up -d
if ($LASTEXITCODE) {throw 'Stand start failed'}
docker cp seed.sql kuda-nt-postgres-1:/tmp/seed.sql
docker compose exec -T postgres psql -X -U kuda -d kuda -v ON_ERROR_STOP=1 -f /tmp/seed.sql | Select-Object -Last 3
if ($LASTEXITCODE) {throw 'Catalog restore failed'}
docker compose exec -T postgres psql -X -U kuda -d kuda -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements; SELECT count(*) AS venues FROM venues; SELECT count(*) AS rooms FROM sessions;'
if ($LASTEXITCODE) {throw 'Database check failed'}
Start-Service KudaWindowsExporter
Start-Service kuda-telegraf
docker compose ps --format '{{.Name}} {{.State}}'

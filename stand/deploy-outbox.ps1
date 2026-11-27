[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location C:/Users/mset6/kuda-nt
docker load -i backend-updated.tar
if($LASTEXITCODE){throw 'Image load failed'}
docker compose run --rm migrate up
if($LASTEXITCODE){throw 'Migration failed'}
docker compose up -d
if($LASTEXITCODE){throw 'Deployment failed'}
docker exec kuda-nt-api-1 /app/api -healthcheck
if($LASTEXITCODE){throw 'Readiness failed'}
docker inspect kuda-nt-api-1 --format '{{.Image}}'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c "SELECT kind,count(*) FROM async_outbox GROUP BY kind; SELECT count(*) AS server_pending FROM events_outbox WHERE delivered_at IS NULL;"

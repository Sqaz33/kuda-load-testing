$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
Set-Location 'C:/Users/mset6/kuda-pgrust'
docker load -i backend-hybrid.tar
if($LASTEXITCODE){throw 'Image load failed'}
$publicConfig=Join-Path (Get-Location) 'docker-public-config'
New-Item -ItemType Directory -Force $publicConfig | Out-Null
[IO.File]::WriteAllText((Join-Path $publicConfig 'config.json'),'{"auths":{}}')
$endpoint=(docker context inspect desktop-linux --format '{{.Endpoints.docker.Host}}').Trim()
docker --config $publicConfig --host $endpoint pull malisper/pgrust:v0.4-beta@sha256:62e3ab08273d85716b17cf594265077774ea017bf7ed1a541634be243bced6a0
if($LASTEXITCODE){throw 'pgrust pull failed'}
docker compose config --quiet
if($LASTEXITCODE){throw 'Invalid compose'}
docker stop kuda-nt-api-1 kuda-nt-postgres-exporter-1 kuda-nt-redis-1 kuda-nt-postgres-1
if($LASTEXITCODE){throw 'Old stand stop failed'}
docker compose up -d postgres geography redis
if($LASTEXITCODE){throw 'Hybrid databases failed'}
docker compose run --rm -e DB_ENGINE=postgres -e 'DATABASE_URL=postgres://kuda:kuda_local_dev@geography:5432/kuda?sslmode=disable' migrate up
if($LASTEXITCODE){throw 'Geography migration failed'}
docker compose exec -T geography psql -X -U kuda -d kuda -v ON_ERROR_STOP=1 -c 'TRUNCATE cities,categories,diets CASCADE;'
if($LASTEXITCODE){throw 'Fresh geography reset failed'}
docker cp geography-catalog.sql kuda-pgrust-geography-1:/tmp/geography-catalog.sql
docker compose exec -T geography psql -X -U kuda -d kuda -v ON_ERROR_STOP=1 -f /tmp/geography-catalog.sql
if($LASTEXITCODE){throw 'Catalog import failed'}
docker compose run --rm migrate up
if($LASTEXITCODE){throw 'pgrust migrations failed'}
docker compose run --rm catalog-sync
if($LASTEXITCODE){throw 'Catalog synchronization failed'}
foreach($service in 'postgres','geography') {
 docker compose exec -T $service psql -X -U kuda -d kuda -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements; SELECT version(); SELECT count(*) FROM venues;'
 if($LASTEXITCODE){throw 'Database metadata failed'}
}
docker compose up -d api postgres-exporter geography-exporter
if($LASTEXITCODE){throw 'Hybrid API start failed'}
Start-Sleep -Seconds 5
docker exec kuda-pgrust-api-1 /app/api -healthcheck
if($LASTEXITCODE){throw 'Hybrid API health failed'}
Invoke-RestMethod 'http://192.168.0.213:8787/ready' | ConvertTo-Json -Depth 5
docker compose ps

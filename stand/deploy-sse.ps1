[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location C:/Users/mset6/kuda-nt
docker load -i backend-updated.tar
if($LASTEXITCODE){throw 'Image load failed'}
$config=Get-Content compose.yaml -Raw
Copy-Item compose.yaml compose-before-sse.yaml -Force
$config=[regex]::Replace($config,'(?ms)(  redis:.*?)(?=  migrate:)',{param($match) $match.Value.Replace('--maxmemory, 64mb','--maxmemory, 128mb').Replace('mem_limit: 128m','mem_limit: 256m')})
Set-Content compose.yaml -Value $config -Encoding utf8
docker compose run --rm migrate up
if($LASTEXITCODE){throw 'Migration failed'}
docker compose up -d
if($LASTEXITCODE){throw 'Deployment failed'}
docker compose ps --format '{{.Name}} {{.State}}'
docker inspect kuda-nt-api-1 --format '{{.Image}}'
docker exec kuda-nt-api-1 /app/api -healthcheck
if($LASTEXITCODE){throw 'Readiness check failed'}
docker inspect kuda-nt-api-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | Select-String '^DB_MAX_CONNS='


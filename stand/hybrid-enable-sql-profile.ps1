$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
Set-Location C:/Users/mset6/kuda-pgrust
docker compose up -d postgres
if($LASTEXITCODE){throw 'pgrust restart failed'}
Start-Sleep -Seconds 3
docker compose up -d api
if($LASTEXITCODE){throw 'API reconnect failed'}
docker exec kuda-pgrust-postgres-1 psql -XAt -U kuda -d kuda -v ON_ERROR_STOP=1 -c 'SELECT pg_stat_statements_reset(); SELECT count(*) FROM pg_stat_statements;'
if($LASTEXITCODE){throw 'SQL profiling not available'}

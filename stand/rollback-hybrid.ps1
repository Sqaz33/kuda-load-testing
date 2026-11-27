$ErrorActionPreference='Stop'
Set-Location 'C:/Users/mset6/kuda-pgrust'
docker compose stop api postgres-exporter geography-exporter postgres geography redis
if($LASTEXITCODE){throw 'Hybrid stop failed'}
Set-Location 'C:/Users/mset6/kuda-nt'
docker compose up -d
if($LASTEXITCODE){throw 'Original stand restart failed'}

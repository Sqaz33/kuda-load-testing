$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
Set-Location 'C:/Users/mset6/kuda-nt'
if (!(Test-Path 'compose-before-profiling.yaml')) {Copy-Item 'compose.yaml' 'compose-before-profiling.yaml'}
$compose=Get-Content 'compose.yaml' -Raw
if ($compose -notmatch 'PPROF_ADDR') {$compose=$compose.Replace('      DB_MAX_CONNS: 150',"      DB_MAX_CONNS: 150`n      PPROF_ADDR: :6060")}
$compose=$compose.Replace("ports: ['192.168.0.213:8787:8787']","ports: ['192.168.0.213:8787:8787', '127.0.0.1:6060:6060']")
if ($compose -notmatch '127.0.0.1:6060:6060' -or $compose -notmatch 'PPROF_ADDR') {throw 'Private profiler configuration missing'}
[IO.File]::WriteAllText((Join-Path (Get-Location) 'compose.yaml'),$compose,[Text.UTF8Encoding]::new($false))
docker load -i 'backend-updated.tar'
if($LASTEXITCODE){throw 'Image load failed'}
docker compose run --rm migrate up
if($LASTEXITCODE){throw 'Migration failed'}
docker compose up -d
if($LASTEXITCODE){throw 'Deployment failed'}
Start-Sleep -Seconds 4
docker exec kuda-nt-api-1 /app/api -healthcheck
if($LASTEXITCODE){throw 'API health failed'}
$snapshot=Invoke-RestMethod 'http://127.0.0.1:6060/debug/runtime'
$snapshot | Select-Object goVersion,goroutines,gomaxprocs,profileSettings | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri 'http://127.0.0.1:6060/debug/profile-control' -Method Put -ContentType 'application/json' -Body '{"blockRate":0,"mutexFraction":0}' | ConvertTo-Json
docker inspect kuda-nt-api-1 --format '{{.Image}}'
try {Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8787/debug/pprof/' | Out-Null; throw 'Profiler exposed through API'} catch {if ($_.Exception.Response.StatusCode.value__ -ne 404 -and $_.Exception.Message -notmatch 'Unable to connect') {throw}}

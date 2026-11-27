[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
New-Item -ItemType Directory -Force 'C:\Users\mset6\kuda-nt' | Out-Null
Set-Location 'C:\Users\mset6\kuda-nt'
docker info --format 'CPU={{.NCPU}} MEM={{.MemTotal}}'
docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}'
docker pull postgis/postgis:16-3.5
docker pull redis:8.2-alpine
docker pull quay.io/prometheuscommunity/postgres-exporter:v0.18.1
docker pull gcr.io/cadvisor/cadvisor:v0.51.0

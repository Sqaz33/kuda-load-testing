[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location C:/Users/mset6/kuda-nt
Copy-Item compose.yaml compose-before-20261127.yaml -Force
Copy-Item compose-updated.yaml compose.yaml -Force
docker load -i backend-updated.tar
if ($LASTEXITCODE) {throw 'Image load failed'}
docker compose up -d
if ($LASTEXITCODE) {throw 'Compose failed'}
Start-Service KudaWindowsExporter
Start-Service kuda-telegraf
docker compose ps --format '{{.Name}} {{.State}}'
docker inspect kuda-nt-api-1 --format '{{.Image}}'
Get-CimInstance Win32_Battery | Select BatteryStatus,EstimatedChargeRemaining

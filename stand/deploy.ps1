[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
Set-Location C:\Users\mset6\kuda-nt
docker load -i backend.tar
docker compose up -d
if($LASTEXITCODE){throw 'Compose failed'}
docker cp seed.sql kuda-nt-postgres-1:/tmp/seed.sql
docker compose exec -T postgres psql -U kuda -d kuda -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS pg_stat_statements;'
docker compose exec -T postgres psql -U kuda -d kuda -v ON_ERROR_STOP=1 -f /tmp/seed.sql | Select-Object -Last 2
if(!(Get-Service KudaWindowsExporter -ErrorAction SilentlyContinue)) {
 New-Service -Name KudaWindowsExporter -BinaryPathName '"C:\Users\mset6\kuda-nt\windows_exporter.exe" --collectors.enabled=cpu,memory,logical_disk,physical_disk,net,os,system --web.listen-address=192.168.0.213:9182' -StartupType Automatic | Out-Null
}
Start-Service KudaWindowsExporter
New-NetFirewallRule -DisplayName 'Kuda NT API and metrics from generator' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8787,9182,9187,8088 -RemoteAddress 192.168.0.242 -Profile Any | Out-Null
docker compose ps
Get-Service KudaWindowsExporter | Select Name,Status | ConvertTo-Json

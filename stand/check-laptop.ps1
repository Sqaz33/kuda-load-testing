[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-CimInstance Win32_Processor | ForEach-Object { "$($_.Name) cores=$($_.NumberOfCores) logical=$($_.NumberOfLogicalProcessors)" }
docker info --format 'Docker={{.ServerVersion}} CPUs={{.NCPU}} RAM={{.MemTotal}}'
Set-Location C:/Users/mset6/kuda-nt
Get-ChildItem | Select Name,Length | Format-Table | Out-String -Width 160
docker images venue-backend --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedAt}}'
docker compose ps -a --format '{{.Name}} {{.State}}'

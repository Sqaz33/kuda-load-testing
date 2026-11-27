[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-ChildItem -LiteralPath C:/Users/mset6/Desktop -Force | Select Name,Length | ConvertTo-Json -Compress
Test-Path -LiteralPath C:/Users/mset6/Desktop/cleanup-kuda.ps1
try {Get-Content -LiteralPath C:/Users/mset6/Desktop/cleanup-kuda.ps1 -TotalCount 1 -ErrorAction Stop} catch {$_.Exception.Message}

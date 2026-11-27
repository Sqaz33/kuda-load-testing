param([string]$RunDirectory)
$ErrorActionPreference='Stop'
while ($true) {
  $state=Get-Content "$RunDirectory/status.json" -Raw | ConvertFrom-Json
  if (!$state.running) {break}
  Start-Sleep -Seconds 30
}
New-Item -ItemType File -Force "$RunDirectory/stop-diagnostics" | Out-Null
Start-Sleep -Seconds 30
$env:PYTHONIOENCODING='utf-8'
python -u -X utf8 D:/kuda-load-testing/stand/finalize_local.py $RunDirectory
if ($LASTEXITCODE) {throw 'Artifact finalization failed'}

param([string]$RunDirectory)
$ErrorActionPreference='Stop'
while ($true) {
 $state=Get-Content "$RunDirectory/status.json" -Raw | ConvertFrom-Json
 if (!$state.running) {break}
 Start-Sleep -Seconds 30
}
$stopScript=Join-Path $RunDirectory 'stop-diagnostics.ps1'
$remoteRoot=if($state.remoteRoot){$state.remoteRoot}else{'C:/Users/mset6/kuda-nt'}
if($remoteRoot -notin @('C:/Users/mset6/kuda-nt','C:/Users/mset6/kuda-pgrust')){throw 'Unexpected stand directory'}
"New-Item -ItemType File -Force '$remoteRoot/artifacts/$((Get-Item $RunDirectory).Name)/stop-diagnostics' | Out-Null" | Set-Content $stopScript -Encoding utf8
& D:/kuda-load-testing/stand/remote.ps1 ps $stopScript
Start-Sleep -Seconds 30
$env:PYTHONIOENCODING='utf-8'
python -u -X utf8 D:/kuda-load-testing/stand/finalize_laptop.py $RunDirectory
if ($LASTEXITCODE) {throw 'Artifact finalization failed'}


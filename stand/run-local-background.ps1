$ErrorActionPreference='Stop'
$run=Join-Path 'D:\kuda-load-testing\out' ((Get-Date -Format 'yyyyMMdd-HHmmss')+'-local-capacity')
New-Item -ItemType Directory -Path $run|Out-Null
$env:KUDA_LOCAL_RUN_DIR=$run
Remove-Item Env:KUDA_RESUME,Env:KUDA_VERIFY -ErrorAction SilentlyContinue
try {
 docker compose -f "$PSScriptRoot\compose.monitoring.yaml" -f "$PSScriptRoot\compose.monitoring.local.yaml" restart results-exporter *> (Join-Path $run 'exporter-start.log')
 if($LASTEXITCODE){throw 'Results exporter could not be restarted'}
 python -u -X utf8 "$PSScriptRoot\run_continuous_capacity.py" *> (Join-Path $run 'controller-console.log')
 if($LASTEXITCODE){throw 'Local load controller failed'}
 python -u -X utf8 "$PSScriptRoot\finalize_local.py" $run *> (Join-Path $run 'finalization-console.log')
 if($LASTEXITCODE){throw 'Local artifact collection failed'}
} catch {
 $_|Out-String|Set-Content -LiteralPath (Join-Path $run 'BACKGROUND_ERROR.txt') -Encoding utf8
} finally {
 Remove-Item Env:KUDA_LOCAL_RUN_DIR -ErrorAction SilentlyContinue
}

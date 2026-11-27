$ErrorActionPreference='Stop'
$run=Join-Path 'D:\kuda-load-testing\out' ((Get-Date -Format 'yyyyMMdd-HHmmss')+'-local-io-diagnostic')
New-Item -ItemType Directory -Path $run|Out-Null
$env:KUDA_LOCAL_RUN_DIR=$run
try {
 $hardware=[ordered]@{
  cpu=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
  disks=(Get-Disk | Select-Object Number,FriendlyName,BusType,Size)
  partitions=(Get-Partition | Where-Object DriveLetter -in @('C','D') | Select-Object DriveLetter,DiskNumber)
  docker=(docker info --format '{{json .}}' | ConvertFrom-Json | Select-Object NCPU,MemTotal,Driver,OperatingSystem)
 }
 $hardware | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $run 'hardware.json') -Encoding utf8
 docker compose -f "$PSScriptRoot\compose.monitoring.yaml" -f "$PSScriptRoot\compose.monitoring.local.yaml" restart results-exporter *> (Join-Path $run 'exporter-start.log')
 if($LASTEXITCODE){throw 'Results exporter could not be restarted'}
 python -u -X utf8 "$PSScriptRoot\run_fixed_diagnostic.py" *> (Join-Path $run 'controller-console.log')
 if($LASTEXITCODE){throw 'Diagnostic controller failed'}
 python -u -X utf8 "$PSScriptRoot\finalize_local.py" $run *> (Join-Path $run 'finalization-console.log')
 if($LASTEXITCODE){throw 'Artifact collection failed'}
} catch {
 $_|Out-String|Set-Content -LiteralPath (Join-Path $run 'BACKGROUND_ERROR.txt') -Encoding utf8
} finally {
 Remove-Item Env:KUDA_LOCAL_RUN_DIR -ErrorAction SilentlyContinue
}

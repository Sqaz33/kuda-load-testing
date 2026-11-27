param([int]$ControllerProcessId,[string]$RunDirectory)
$ErrorActionPreference='Stop'
Wait-Process -Id $ControllerProcessId -ErrorAction SilentlyContinue
try {
 $state=Get-Content -LiteralPath (Join-Path $RunDirectory 'status.json') -Raw|ConvertFrom-Json
 if($state.running){throw 'Контроллер завершился до записи итогового состояния'}
 python -u -X utf8 "$PSScriptRoot\finalize.py" $RunDirectory
 if($LASTEXITCODE){throw 'Ошибка сохранения артефактов; см. журнал завершения'}
} catch {
 $_|Out-String|Set-Content (Join-Path $RunDirectory 'FINALIZATION_ERROR.txt') -Encoding utf8
 & "$PSScriptRoot\remote.ps1" ps "$PSScriptRoot\restore-maintenance.ps1"
}

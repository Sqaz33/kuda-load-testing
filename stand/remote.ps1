param([Parameter(ValueFromRemainingArguments=$true)][string[]]$RemoteArgs)
$secret=Get-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'kuda-ssh-secret.txt') | ConvertTo-SecureString
$env:KUDA_SSH_PASSWORD=[Net.NetworkCredential]::new('', $secret).Password
try {uv run --no-project --with paramiko python -X utf8 "$PSScriptRoot\remote.py" @RemoteArgs}
finally {Remove-Item Env:KUDA_SSH_PASSWORD}
exit $LASTEXITCODE

[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$file='C:Usersmset6Desktopcleanup-kuda.ps1'
$t=$null
$e=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$t,[ref]$e)
$e | ForEach-Object {$_.Message}
Get-FileHash -LiteralPath $file | Select Hash | ConvertTo-Json -Compress

[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$file='C:/Users/mset6/Desktop/cleanup-kuda.ps1'
$tokens=$null
$errors=$null
[void][Management.Automation.Language.Parser]::ParseFile($file,[ref]$tokens,[ref]$errors)
if ($errors.Count) {throw ($errors | ForEach-Object Message | Out-String)}
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut('C:/Users/mset6/Desktop/Очистить стенд Kuda.lnk')
$link.TargetPath='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
$link.Arguments='-NoProfile -ExecutionPolicy Bypass -File "C:/Users/mset6/Desktop/cleanup-kuda.ps1"'
$link.WorkingDirectory='C:/Users/mset6/kuda-nt'
$link.Description='Удалить тестовую базу Kuda и старые артефакты'
$link.Save()
Get-Item -LiteralPath $file,'C:/Users/mset6/Desktop/Очистить стенд Kuda.lnk' | Select FullName,Length | ConvertTo-Json -Compress
Get-FileHash -LiteralPath $file | Select Hash | ConvertTo-Json -Compress

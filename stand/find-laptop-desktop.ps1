[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
[pscustomobject]@{Desktop=[Environment]::GetFolderPath('DesktopDirectory');UserProfile=$env:USERPROFILE} | ConvertTo-Json -Compress

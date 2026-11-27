[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select DeviceID,Size,FreeSpace | ConvertTo-Json -Compress
Get-ChildItem -LiteralPath C:/ -Force -File -ErrorAction SilentlyContinue | Select Name,Length | ConvertTo-Json -Compress
Get-ChildItem -LiteralPath C:/Users/mset6/AppData/Local/Docker,C:/Users/mset6/AppData/Local/Packages,C:/Users/mset6/AppData/Local/wsl -Filter *.vhdx -File -Recurse -Force -ErrorAction SilentlyContinue | Select FullName,Length | ConvertTo-Json -Compress
docker system df

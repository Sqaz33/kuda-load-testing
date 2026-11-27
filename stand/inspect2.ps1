[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
@{cpu=@(Get-CimInstance Win32_Processor|Select Name,NumberOfCores,NumberOfLogicalProcessors);disks=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'|Select DeviceID,Size,FreeSpace);network=@(Get-NetAdapter|Select Name,Status,LinkSpeed);processes=@(Get-Process -Name '*docker*','*wsl*' -ErrorAction SilentlyContinue|Select Name,Id,SessionId);user=$env:USERPROFILE} | ConvertTo-Json -Depth 5
wsl --list --verbose
Get-Service '*docker*','sshd' | Format-List Name,Status,StartType
Get-ChildItem 'C:\Program Files\Docker\Docker' | Select Name
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe' -WindowStyle Hidden

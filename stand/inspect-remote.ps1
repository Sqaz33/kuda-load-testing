[Console]::OutputEncoding=[Text.Encoding]::UTF8
Get-CimInstance Win32_OperatingSystem | Select Caption,TotalVisibleMemorySize,FreePhysicalMemory,LocalDateTime
Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select DeviceID,Size,FreeSpace
Get-NetAdapter | Select Name,Status,LinkSpeed
Get-Command docker,python,git -ErrorAction SilentlyContinue | Select Name,Source
docker info --format '{{json .}}'
docker ps -a --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

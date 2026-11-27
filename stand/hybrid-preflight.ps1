$ProgressPreference='SilentlyContinue'
Get-Item 'C:/Users/mset6/kuda-nt/compose.yaml' | Select-Object FullName
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace
Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory
 docker ps --format '{{.Names}} {{.Status}}'

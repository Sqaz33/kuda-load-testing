[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
@{os=Get-CimInstance Win32_OperatingSystem|Select Caption,TotalVisibleMemorySize,FreePhysicalMemory,LocalDateTime;cpu=Get-CimInstance Win32_Processor|Select Name,NumberOfCores,NumberOfLogicalProcessors;network=@(Get-NetAdapter|Select Name,Status,LinkSpeed);battery=@(Get-CimInstance Win32_Battery|Select BatteryStatus,EstimatedChargeRemaining);processes=@(Get-Process|Sort WorkingSet64 -Descending|Select -First 12 Name,CPU,WorkingSet64)}|ConvertTo-Json -Depth 5
docker stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} MEM={{.MemUsage}}'

[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-CimInstance Win32_Service | Where-Object ProcessId -eq 15512 | Select Name,DisplayName,State,StartMode | ConvertTo-Json
$p=(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Services\KudaWindowsExporter).ImagePath
$p=$p.Replace('com.docker.backend|vmmemWSL','mscorsvw|svchost|com.docker.backend|vmmemWSL')
Set-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Services\KudaWindowsExporter -Name ImagePath -Value $p
Restart-Service KudaWindowsExporter

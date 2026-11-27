[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
$ErrorActionPreference='Stop'
$measurements=@()
for($i=0;$i -lt 3;$i++){
 $before=@{}
 Get-Process | ForEach-Object {try{$before[$_.Id]=$_.CPU}catch{}}
 $start=Get-Date
 Start-Sleep -Seconds 5
 $elapsed=((Get-Date)-$start).TotalSeconds
 $cores=(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
 $rows=Get-Process | ForEach-Object {
  $p=$_
  if($before.ContainsKey($p.Id)){
   try {
    $delta=$p.CPU-$before[$p.Id]
    if($delta -ge 0){[pscustomobject]@{pid=$p.Id;name=$p.Name;cpuPercent=[math]::Round(100*$delta/$elapsed/$cores,1);workingSetMB=[math]::Round($p.WorkingSet64/1MB);path=$p.Path}}
   }catch{}
  }
 } | Sort-Object cpuPercent -Descending | Select-Object -First 12
 $measurements+=@{time=(Get-Date).ToString('o');seconds=$elapsed;cores=$cores;processes=@($rows)}
}
$measurements | ConvertTo-Json -Depth 5
docker stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} MEM={{.MemUsage}}'
Get-CimInstance Win32_OperatingSystem | Select FreePhysicalMemory,TotalVisibleMemorySize | ConvertTo-Json -Compress
Get-CimInstance Win32_Processor | Select Name,CurrentClockSpeed,MaxClockSpeed,LoadPercentage | ConvertTo-Json -Compress

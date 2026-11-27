param(
    [ValidateSet('Smoke','Load')]
    [string]$Mode = 'Smoke',
    [string]$HostAddress = '192.168.0.242',
    [string]$JMeter = 'D:\apache-jmeter-5.6.3\bin\jmeter.bat'
)
$ErrorActionPreference = 'Stop'
$runDirectory = Join-Path $PSScriptRoot ('out\' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $Mode.ToLower())
New-Item -ItemType Directory -Path $runDirectory | Out-Null
$arguments = @('-n','-t',(Join-Path $PSScriptRoot 'kuda.jmx'),
    "-Jhost=$HostAddress","-Jmode=$($Mode.ToLower())","-JoutDir=$runDirectory",
    '-Jjmeterengine.force.system.exit=true','-Jdynamic_tg.properties_caching_validity=1000',
    '-j',(Join-Path $runDirectory 'jmeter.log'))
if ($Mode -eq 'Smoke') {
    $arguments += @('-JparticipantThreads=3','-JpollThreads=4','-JroomViewSeconds=25',
        '-JpollDelayMs=500','-JvotePauseMs=100','-JvoteSpreadMs=100','-JdrainSeconds=40')
}
& $JMeter @arguments
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$rooms = @(Import-Csv -LiteralPath (Join-Path $runDirectory 'rooms.csv'))
$failedRooms = @($rooms | Where-Object result -ne success)
if (!$rooms.Count -or $failedRooms.Count) {
    Write-Host "Есть ошибки сценария. Результаты: $runDirectory"
    exit 1
}
Write-Host "Все компании завершились. Результаты: $runDirectory"

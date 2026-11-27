[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ErrorActionPreference='Stop'
$exe='C:\Users\mset6\kuda-nt\telegraf.exe'
& $exe --config C:\Users\mset6\kuda-nt\telegraf.conf --test
& $exe --service install --service-name kuda-telegraf --config C:\Users\mset6\kuda-nt\telegraf.conf
Start-Service kuda-telegraf
New-NetFirewallRule -DisplayName 'Kuda NT Docker metrics from generator' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9273 -RemoteAddress 192.168.0.242 -Profile Any | Out-Null

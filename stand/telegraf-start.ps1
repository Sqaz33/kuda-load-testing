[Console]::OutputEncoding=[Text.Encoding]::UTF8
& C:\Users\mset6\kuda-nt\telegraf.exe --config C:\Users\mset6\kuda-nt\telegraf.conf --test
Start-Service kuda-telegraf
New-NetFirewallRule -DisplayName 'Kuda NT Docker metrics from generator' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9273 -RemoteAddress 192.168.0.242 -Profile Any | Out-Null

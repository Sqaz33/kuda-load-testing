$ErrorActionPreference='Stop'
$dir='C:/Users/mset6/kuda-nt/artifacts/20261127-130302-capacity'
New-Item -ItemType Directory -Force $dir | Out-Null
Start-Process C:/Python313/python.exe -ArgumentList '-u','C:/Users/mset6/kuda-nt/collect_diagnostics.py',$dir -WindowStyle Hidden -RedirectStandardOutput "$dir/diagnostic-stdout.log" -RedirectStandardError "$dir/diagnostic-stderr.log"
New-NetFirewallRule -DisplayName 'Kuda NT PG diagnostics' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9200 -RemoteAddress 192.168.0.242 -Profile Any | Out-Null

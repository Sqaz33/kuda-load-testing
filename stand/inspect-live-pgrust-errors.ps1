$ProgressPreference='SilentlyContinue'
Set-Location C:/Users/mset6/kuda-pgrust
docker logs --since 3m kuda-pgrust-postgres-1 2>&1 | Select-String -Pattern 'ERROR:|PANIC|panicked|Failed process was running|STATEMENT:|FATAL:|terminated by signal' -Context 0,2 | Select-Object -Last 45
docker logs --since 3m kuda-pgrust-api-1 2>&1 | Select-String -Pattern 'background worker failed|request failed|SSE|status.:500' | Select-Object -Last 8
Get-Content C:/Users/mset6/kuda-pgrust/pgrust-recovery.jsonl -Tail 5

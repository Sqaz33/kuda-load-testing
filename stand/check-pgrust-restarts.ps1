$ProgressPreference='SilentlyContinue'
docker logs --since 2026-11-27T18:40:00Z kuda-pgrust-postgres-1 2>&1 | Select-String -Pattern 'terminated by signal|PANIC|Failed process was running' -Context 0,1

$ProgressPreference='SilentlyContinue'
Get-Item C:/Users/mset6/kuda-pgrust/backend-hybrid.tar | Select-Object Length,LastWriteTime | ConvertTo-Json
Get-FileHash C:/Users/mset6/kuda-pgrust/backend-hybrid.tar | Select-Object Hash | ConvertTo-Json
docker logs --tail 5 kuda-pgrust-postgres-1
docker ps --format '{{.Names}} {{.Status}}'

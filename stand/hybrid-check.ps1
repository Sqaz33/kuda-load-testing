$ProgressPreference='SilentlyContinue'
docker ps --format '{{.Names}} {{.Status}}'

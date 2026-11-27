[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ProgressPreference='SilentlyContinue'
Get-Content C:/Users/mset6/kuda-nt/seed.sql -TotalCount 4
docker volume ls --format '{{.Name}}'
docker images --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}'
docker exec kuda-nt-postgres-1 psql -X -U kuda -d kuda -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"

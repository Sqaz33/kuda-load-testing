[Console]::OutputEncoding=[Text.Encoding]::UTF8
Set-Location C:\Users\mset6\kuda-nt
docker compose exec -T postgres psql -X -U kuda -d kuda -c 'SELECT pg_stat_statements_reset(); SELECT pg_stat_reset();'
docker compose restart api

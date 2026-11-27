$ProgressPreference='SilentlyContinue'
docker exec kuda-pgrust-postgres-1 psql -XAt -U kuda -d kuda -v ON_ERROR_STOP=1 -c 'SELECT row_to_json(b) FROM pg_stat_checkpointer b;'

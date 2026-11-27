import os
import base64
import json
import pathlib
import urllib.request

stand=pathlib.Path(__file__).parent
run=pathlib.Path((stand/'local-next-run.txt').read_text().strip())
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
headers={'Authorization':'Basic '+base64.b64encode((os.environ.get('KUDA_GRAFANA_USER','admin')+':'+os.environ['KUDA_GRAFANA_PASSWORD']).encode()).decode(), 'Content-Type':'application/json'}
request=urllib.request.Request('http://127.0.0.1:3001/api/dashboards/uid/kuda-load-test',headers=headers)
original=json.load(opener.open(request,timeout=10))
(run/'grafana-before.json').write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf8')
dashboard=original['dashboard']
dashboard['panels']=[panel for panel in dashboard['panels'] if panel['id'] not in (63,64,65,66,67)]
for panel in dashboard['panels']:
    panel['title']=panel['title'].replace('pgrust','PostgreSQL')
    if panel['id']==4:
        panel['title']='До аварийного лимита прогона'
    if panel['id']==33:
        panel['title']='Проверка HTTP — этот ПК'
    if panel['id']==61:
        panel['targets']=panel['targets'][:1]
        panel['targets'][0]['expr']='rate(docker_container_cpu_usage_total{container_name="kuda-backend-postgres-1",cpu="cpu-total"}[1m])/1e9'
        panel['targets'][0]['legendFormat']='PostgreSQL'
    if panel['id']==62:
        panel['targets']=panel['targets'][:1]
        panel['targets'][0]['expr']='docker_container_mem_usage{container_name="kuda-backend-postgres-1"}'
        panel['targets'][0]['legendFormat']='PostgreSQL'
dashboard['time']={'from':'now-15m','to':'now'}
dashboard['refresh']='5s'
body=json.dumps({'dashboard':dashboard,'overwrite':True,'message':'Local PostgreSQL capacity run'}).encode()
result=json.load(opener.open(urllib.request.Request('http://127.0.0.1:3001/api/dashboards/db',data=body,headers=headers),timeout=15))
(stand/'dashboard.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2),encoding='utf8')
print(result)

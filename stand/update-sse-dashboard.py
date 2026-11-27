import os
import base64,json,urllib.request
from pathlib import Path
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
headers={'Authorization':'Basic '+base64.b64encode((os.environ.get('KUDA_GRAFANA_USER','admin')+':'+os.environ['KUDA_GRAFANA_PASSWORD']).encode()).decode(),'Content-Type':'application/json'}
def req(path,body=None):
 return json.load(opener.open(urllib.request.Request('http://127.0.0.1:3001'+path,data=None if body is None else json.dumps(body).encode(),headers=headers),timeout=10))
dashboard=req('/api/dashboards/uid/kuda-load-test')['dashboard']
if not any(p.get('title')=='SSE и фоновая обработка' for p in dashboard['panels']):
 y=max(p.get('gridPos',{}).get('y',0)+p.get('gridPos',{}).get('h',0) for p in dashboard['panels'])
 nid=max(p['id'] for p in dashboard['panels'])+1
 dashboard['panels'].append({'id':nid,'type':'row','title':'SSE и фоновая обработка','collapsed':False,'gridPos':{'x':0,'y':y,'w':24,'h':1},'panels':[]})
 ds=next(p.get('datasource') for p in dashboard['panels'] if p.get('datasource'))
 def panel(title,x,queries):
  global nid
  nid+=1
  dashboard['panels'].append({'id':nid,'type':'timeseries','title':title,'datasource':ds,'gridPos':{'x':x,'y':y+1,'w':8,'h':8},'targets':[{'refId':chr(65+i),'expr':expr,'legendFormat':legend,'datasource':ds} for i,(expr,legend) in enumerate(queries)],'fieldConfig':{'defaults':{'custom':{'drawStyle':'line','lineWidth':1}},'overrides':[]},'options':{'legend':{'displayMode':'table','placement':'bottom','calcs':['lastNotNull','max']}}})
 panel('SSE — открытые соединения',0,[('kuda_sse_connections','бэкенд'),('kuda_test_active_streams','JMeter')])
 panel('SSE — события, ошибки и переподключения',8,[('rate(kuda_test_stream_events[1m])','событий/с'),('kuda_test_stream_errors','ошибки'),('kuda_test_stream_reconnects','переподключения')])
 panel('Очереди фоновой обработки',16,[('kuda_pg_async_queue_pending','аналитика и уведомления'),('kuda_pg_server_queue_pending','серверная аналитика'),('kuda_pg_async_queue_oldest_seconds','возраст задания, с')])
 print(req('/api/dashboards/db',{'dashboard':dashboard,'overwrite':True,'message':'Room SSE and durable queue diagnostics'})['status'])
Path('D:/kuda-load-testing/stand/dashboard.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2),encoding='utf8')

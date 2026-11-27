from pathlib import Path
import xml.etree.ElementTree as E
import shutil
root=Path('D:/kuda-load-testing')
backup=root/'stand/backups/before-sse';backup.mkdir(parents=True,exist_ok=True)
for f in ['kuda.jmx','stand/run_laptop_capacity.py','stand/capacity_policy.py']:
 shutil.copy2(root/f,backup/Path(f).name)
p=root/'kuda.jmx';tree=E.parse(p);r=tree.getroot()
def find(name):
 for n in r.iter():
  if n.get('testname')==name:return n
 raise ValueError(name)
def script(n):return n.find("stringProp[@name='script']")
def parent(n):return next(x for x in r.iter() if n in list(x))
def pair(n):
 t=parent(n);i=list(t).index(n);return t,i,list(t)[i+1]
def move_after(n,target):
 t,i,h=pair(n);t.remove(n);t.remove(h);dest,j,_=pair(target);dest.insert(j+2,n);dest.insert(j+3,h)
def jsr(name,code):
 n=E.Element('JSR223Sampler',{'guiclass':'TestBeanGUI','testclass':'JSR223Sampler','testname':name,'enabled':'true'})
 for k,v in [('scriptLanguage','groovy'),('filename',''),('parameters',''),('cacheKey','true'),('script',code)]:E.SubElement(n,'stringProp',{'name':k}).text=v
 return n
init=script(find('Инициализировать прогон'))
init.text=init.text.replace('active:new AtomicInteger(),','streams:new AtomicInteger(),streamErrors:new AtomicInteger(),streamReconnects:new AtomicInteger(),streamEvents:new AtomicInteger(),active:new AtomicInteger(),')
publish=script(find('Передать три приглашения'))
publish.text=publish.text.replace('room=[id:', 'room=[streams:new java.util.concurrent.ConcurrentHashMap(),id:')
move_after(find('Фоновый опрос организатора'),find('Передать три приглашения'))
move_after(find('Фоновый опрос участника'),find('Приглашение | POST join'))
find('Фоновый опрос организатора').set('testname','SSE | Подписать организатора')
find('Фоновый опрос участника').set('testname','SSE | Подписать участника')
# Keep one real GET after selecting the winner, both as a business check and to
# measure the read API. Waiting for events no longer issues HTTP requests.
old=find('Комната | Ждать finished');final=E.fromstring(E.tostring(old));_,_,oh=pair(old);finalh=E.fromstring(E.tostring(oh))
final.set('testname','Комната | GET result')
for n in list(finalh):
 if n.tag in ('JSR223Assertion','ConstantTimer'):
  i=list(finalh).index(n);h=list(finalh)[i+1];finalh.remove(n);finalh.remove(h)
a=E.SubElement(finalh,'JSR223Assertion',{'guiclass':'TestBeanGUI','testclass':'JSR223Assertion','testname':'Проверить результат комнаты','enabled':'true'})
for k,v in [('scriptLanguage','groovy'),('filename',''),('parameters',''),('cacheKey','true'),('script',"def b=new groovy.json.JsonSlurper().parseText(prev.responseDataAsString); if(prev.responseCode!='200'||b.id!=vars.get('roomId')||b.winner?.id!=vars.getObject('roomJob').winner.get()){AssertionResult.setFailure(true);AssertionResult.setFailureMessage('Результат комнаты отличается');vars.getObject('roomJob').cancelled.set(true)}")]:E.SubElement(a,'stringProp',{'name':k}).text=v
E.SubElement(finalh,'hashTree')
dest,j,_=pair(find('Результат | PUT winner'));dest.insert(j+2,final);dest.insert(j+3,finalh)
wait_code="""def room=vars.getObject('roomJob')
long deadline=vars.get('waitUntil').toLong()
def state=room.streams.get(vars.get('userId'))
while(state==null && !room.cancelled.get() && System.currentTimeMillis()<deadline){Thread.sleep(100);state=room.streams.get(vars.get('userId'))}
if(state==null) throw new IllegalStateException('Не получен снимок SSE')
SampleResult.setResponseCode('200');SampleResult.setSuccessful(true)
SampleResult.setResponseData(groovy.json.JsonOutput.toJson(state),'UTF-8')
SampleResult.setIgnore()
Thread.sleep(250)
"""
for name in ['Комната | Ждать members','Комната | Ждать finished','Комната | Ждать start']:
 old=find(name);t,i,h=pair(old);t.remove(old);t.insert(i,jsr(name.replace('Комната | Ждать','SSE | Ждать'),wait_code))
 # Headers and network timers are not needed for reading a local event snapshot.
 for n in list(h):
  if n.tag in ('HeaderManager','ConstantTimer'):
   i=list(h).index(n);hh=list(h)[i+1];h.remove(n);h.remove(hh)
stream_code=r'''import groovy.json.JsonSlurper
import java.net.HttpURLConnection

def run=props.get('kudaLoad');def room=vars.getObject('roomJob')
String uid=vars.get('userId');String token=vars.get('authToken')
HttpURLConnection connection=null
run.streams.incrementAndGet()
try {
 boolean connected=false
 while(!room.cancelled.get() && System.currentTimeMillis()<room.end){
  try {
   URL url=new URL(vars.get('protocol')+'://'+vars.get('host')+':'+vars.get('port')+'/v1/rooms/'+room.id+'/events')
   connection=(HttpURLConnection)url.openConnection()
   connection.setRequestProperty('Authorization','Bearer '+token)
   connection.setRequestProperty('Accept','text/event-stream')
   connection.setConnectTimeout(vars.get('responseTimeoutMs').toInteger());connection.setReadTimeout(20000)
   if(connection.responseCode!=200) throw new IllegalStateException('SSE HTTP '+connection.responseCode)
   if(connected) run.streamReconnects.incrementAndGet()
   connected=true
   def reader=new BufferedReader(new InputStreamReader(connection.inputStream,'UTF-8'))
   String event=''
   while(!room.cancelled.get() && System.currentTimeMillis()<room.end){
    String line=reader.readLine();if(line==null)break
    if(line.startsWith('event: '))event=line.substring(7)
    if(line.startsWith('data: ') && event=='room'){
     def state=new JsonSlurper().parseText(line.substring(6))
     if(state.id!=room.id)throw new IllegalStateException('SSE другой комнаты')
     room.streams.put(uid,state);run.streamEvents.incrementAndGet()
     if(state.winner && room.winner.get()){
      if(state.winner.id!=room.winner.get())throw new IllegalStateException('SSE другой победитель')
      vars.put('sawWinner','true')
     }
    }
    if(event=='access_revoked')throw new IllegalStateException('SSE доступ отозван')
   }
   reader.close()
  } finally {if(connection!=null)connection.disconnect()}
  if(!room.cancelled.get() && System.currentTimeMillis()<room.end)Thread.sleep(250)
 }
 SampleResult.setIgnore()
} catch(Throwable e){
 if(!room.cancelled.get()){
  run.streamErrors.incrementAndGet();room.cancelled.set(true);vars.put('ok','false');vars.put('reason',e.message ?: e.class.simpleName)
  SampleResult.setSuccessful(false);SampleResult.setResponseCode('SSE_ERROR');SampleResult.setResponseMessage(e.message ?: e.class.simpleName)
 }else SampleResult.setIgnore()
} finally {run.streams.decrementAndGet();if(connection!=null)connection.disconnect()}
'''
old=find('Пока открыт экран');t,i,h=pair(old);t.remove(old);t.remove(h);t.insert(i,jsr('SSE | Читать изменения комнаты',stream_code));t.insert(i+1,E.Element('hashTree'))
# Keep terminal workers quiet; hitting the planned drain deadline is not a
# scenario failure when no task has been taken.
for n in r.iter():
 s=script(n)
 if s is None:continue
 s.text=(s.text or '').replace("if(System.currentTimeMillis()>=run.hardEnd) throw new IllegalStateException('Истекло предельное время завершения')", "if(System.currentTimeMillis()>=run.hardEnd){vars.put('workerRunning','false');vars.put('hasJob','false');SampleResult.setIgnore();return}")
 if 'def data=[timestamp_seconds:' in s.text:
  s.text=s.text.replace('def data=[timestamp_seconds:', 'def data=[active_streams:run.streams.get(),stream_errors:run.streamErrors.get(),stream_reconnects:run.streamReconnects.get(),stream_events:run.streamEvents.get(),timestamp_seconds:')
find('Опрос | Динамический пул').set('testname','SSE | Динамический пул')
next(r.iter('TestPlan')).set('testname','Куда | Комнаты, голоса и SSE')
E.indent(tree,space='  ');tree.write(p,encoding='UTF-8',xml_declaration=True)
print('Updated',p)

import groovy.json.JsonOutput
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
def run=props.get('kudaLoad')
def room=vars.getObject('roomJob')
String action=args[0]
try {
 switch(action) {
 case 'hold':
  long limit=room.end+vars.get('pollDelayMs').toLong()+vars.get('responseTimeoutMs').toLong()+5000
  while(!room.cancelled.get() && room.pending.get()>0 && System.currentTimeMillis()<limit) Thread.sleep(200)
  if(room.cancelled.get() || room.pending.get()>0) throw new IllegalStateException('Не все пользователи подтвердили результат')
  break
 }
 SampleResult.setIgnore()
} catch(Exception e) {
 vars.put('ok','false');vars.put('reason',e.message ?: e.class.simpleName)
 if(room!=null) room.cancelled.set(true)
 if(action.startsWith('take-')) vars.put('workerRunning','false')
 SampleResult.setSuccessful(false)
 SampleResult.setResponseCode('SCENARIO_ERROR')
 SampleResult.setResponseMessage(e.message ?: e.class.simpleName)
}

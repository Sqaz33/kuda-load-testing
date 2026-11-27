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
 case 'host-finalize':
  boolean success=vars.get('ok')=='true' && room!=null && !room.cancelled.get() && room.winner.get()
  if(success) run.completed.incrementAndGet()
  else {
   run.failed.incrementAndGet()
   if(room!=null) room.cancelled.set(true)
  }
  def row=[vars.get('roomId') ?: '',success?'success':'failed',room?.winner?.get() ?: '',
    System.currentTimeMillis()-vars.get('startedAt').toLong(),vars.get('reason') ?: (success ? '' : 'Ошибка связанного участника или фонового опроса')]
    .collect { '"'+it.toString().replace('"','""').replaceAll('[\\r\\n]',' ')+'"' }.join(',')
  synchronized(run.lock) { run.summary.append(row+'\n','UTF-8') }
  run.active.decrementAndGet()
  run.telemetryNext.set(0L)
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

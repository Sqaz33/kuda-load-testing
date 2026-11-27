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
 case 'wait-start':
  vars.put('waitMore','true')
  vars.put('waitKind',action)
  long seconds=action=='wait-members' ? vars.get('joinTimeoutSeconds').toLong() : vars.get('votingTimeoutSeconds').toLong()
  vars.put('waitUntil',(System.currentTimeMillis()+seconds*1000L).toString())
  if(action=='wait-finished') room.hostPaused.set(true)
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

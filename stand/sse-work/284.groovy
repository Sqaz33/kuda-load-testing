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
 case 'publish':
  room=[id:vars.get('roomId'),invite:vars.get('inviteToken'),
   end:System.currentTimeMillis()+vars.get('roomViewSeconds').toLong()*1000L,
   cancelled:new AtomicBoolean(),winner:new AtomicReference(''),
   pending:new AtomicInteger(),hostPaused:new AtomicBoolean()]
  vars.putObject('roomJob',room)
  for(int i=1;i<=3;i++) {
   if(!run.members.offer([room:room,number:i,queuedAt:System.currentTimeMillis()],2,TimeUnit.SECONDS)) throw new IllegalStateException('Очередь участников переполнена')
  }
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

import groovy.json.JsonOutput
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
def run=props.get('kudaLoad')
def room=vars.getObject('roomJob')
String action=args[0]
try {

if(run.stopFile.exists() && !run.stopApplied.getAndSet(true)) {
 run.end=System.currentTimeMillis(); run.hardEnd=run.end+vars.get('drainSeconds').toLong()*1000L
}
// Snapshot every ten seconds; this does not add HTTP traffic.
def telemetryNow=System.currentTimeMillis()
def telemetryNext=run.telemetryNext.get()
if(telemetryNow>=telemetryNext && run.telemetryNext.compareAndSet(telemetryNext,telemetryNow+10000L)) {
 def memberHead=run.members.peek();def pollHead=run.polls.peek()
 def data=[timestamp_seconds:telemetryNow/1000d,phase_started_seconds:run.phaseStart/1000d,active_rooms:run.active.get(),started_rooms:run.started.get(),completed_rooms:run.completed.get(),failed_rooms:run.failed.get(),member_queue:run.members.size(),poll_queue:run.polls.size(),member_queue_oldest_seconds:memberHead==null?0:Math.max(0L,telemetryNow-memberHead.queuedAt)/1000d,poll_queue_oldest_seconds:pollHead==null?0:Math.max(0L,telemetryNow-pollHead.queuedAt)/1000d]
 synchronized(run.lock) { run.telemetry.setText(JsonOutput.toJson(data),'UTF-8') }
}

 switch(action) {
 case 'take-poll':
  def queue=action=='take-member' ? run.members : run.polls
  if(System.currentTimeMillis()>=run.hardEnd) throw new IllegalStateException('Истекло предельное время завершения')
  if(System.currentTimeMillis()>run.end && run.active.get()==0 && queue.isEmpty()) {
   vars.put('workerRunning','false'); vars.put('hasJob','false'); break
  }
  def job=queue.poll(5,TimeUnit.SECONDS)
  vars.put('hasJob','false')
  if(job==null) break
  room=job.room
  vars.putObject('roomJob',room)
  if(room.cancelled.get()) {
   if(action=='take-poll') room.pending.decrementAndGet()
   break
  }
  vars.put('hasJob','true');vars.put('ok','true')
  vars.put('roomId',room.id);vars.put('inviteToken',room.invite)
  if(action=='take-member') {
   vars.put('actorRole','member')
   vars.put('authToken','')
   vars.put('guestName','НТ участник '+job.number+' '+UUID.randomUUID().toString().take(8))
  } else {
   vars.put('authToken',job.token);vars.put('userId',job.userId)
   vars.put('hostPoll',job.host.toString());vars.put('sawWinner','false')
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

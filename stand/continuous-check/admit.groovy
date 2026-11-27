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
 case 'host-begin':
  if(run.stopFile.exists()) { run.stopArrivals.set(true); SampleResult.setIgnore(); ctx.getThread().stop(); return }
  if(run.continuous) {
   boolean admitted=false
   synchronized(run.arrivalLock) {
    long now=System.currentTimeMillis()
    if(now>=run.controlNext) {
     run.controlNext=now+250L
     if(run.controlFile.exists()) {
      def control=new groovy.json.JsonSlurper().parse(run.controlFile,'UTF-8')
      int rate=control.rate as int
      if(rate<0 || rate>run.arrivalCeiling) throw new IllegalArgumentException('Invalid arrival rate: '+rate)
      run.targetRate.set(rate)
      run.workerRate.set(Math.max(run.workerRate.get(),rate))
     }
    }
    // Evenly admit only the requested fraction of potential Open Model starts.
    // Rejected starts perform no HTTP and create no business scenario or sample.
    run.arrivalCredit+=run.targetRate.get()
    if(run.targetRate.get()>0 && run.arrivalCredit>=run.arrivalCeiling) {
     run.arrivalCredit-=run.arrivalCeiling; admitted=true
    }
   }
   if(!admitted) { SampleResult.setIgnore(); ctx.getThread().stop(); return }
  }
  vars.put('actorRole','host')
  run.active.incrementAndGet()
  run.started.incrementAndGet()
  vars.putObject('roomJob',null)
  room=null
  vars.put('ok','true')
  vars.put('reason','')
  vars.put('authToken','')
  vars.put('roomId','')
  vars.put('startedAt',System.currentTimeMillis().toString())
  vars.put('guestName','НТ организатор '+UUID.randomUUID().toString().take(8))
  vars.put('createKey',UUID.randomUUID().toString())
  def c=[city:'Волгоград',timeZone:'Europe/Volgograd',date:props.get('kudaMeetingDate'),
   time:'19:30',area:[type:'district',district:'Центральный'],categories:['bar','cafe','restaurant'],
   budgetMax:2000,partySize:4,deadlineMinutes:30,exclusions:[]]
  vars.put('constraintsJson',JsonOutput.toJson(c))
  vars.put('createJson',JsonOutput.toJson([constraints:c]))
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

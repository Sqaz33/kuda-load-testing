import groovy.json.JsonOutput
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.atomic.AtomicInteger
import org.apache.jmeter.services.FileServer
def mode = vars.get('mode')
def rates=vars.get('stageRates').split('\\|').collect { it.toInteger() }
assert rates.every { it>0 } && vars.get('stepSeconds').toInteger()>0
int duration = mode == 'smoke' ? vars.get('smokeRooms').toInteger() : vars.get('stepSeconds').toInteger()*rates.size()
boolean continuous=mode!='smoke' && props.getProperty('continuous','false').toBoolean()
int arrivalCeiling=props.getProperty('arrivalCeiling','512').toInteger()
if(continuous) duration=props.getProperty('loadSeconds','3390').toInteger()
def schedule = mode == 'smoke' ? 'rate(1/sec) even_arrivals('+duration+' sec) rate(1/sec)' :
    rates.collect { 'rate('+it+'/min) even_arrivals('+vars.get('stepSeconds')+' sec) rate('+it+'/min)' }.join(' ')
if(continuous) schedule='rate('+arrivalCeiling+'/min) even_arrivals('+duration+' sec) rate('+arrivalCeiling+'/min)'
schedule += ' pause('+vars.get('drainSeconds')+' sec)'
new org.apache.jmeter.threads.openmodel.ScheduleParser(schedule).parse()
File base=new File(FileServer.getFileServer().getBaseDir())
String path=vars.get('outDir')
File output=path.startsWith('~/') ? new File(base,path.substring(2)) : new File(path)
if(!output.isAbsolute()) output=new File(base,path)
output.mkdirs()
def summary=new File(output,'rooms.csv')
if(!summary.exists() || summary.length()==0) summary.setText('roomId,result,winnerId,elapsedMs,reason\n','UTF-8')
props.put('kudaLoad',[members:new LinkedBlockingQueue(20000),polls:new LinkedBlockingQueue(20000),
 active:new AtomicInteger(),started:new AtomicInteger(),completed:new AtomicInteger(),failed:new AtomicInteger(),
 end:System.currentTimeMillis()+duration*1000L,
 hardEnd:System.currentTimeMillis()+(duration+vars.get('drainSeconds').toInteger())*1000L,
 continuous:continuous,arrivalCeiling:arrivalCeiling,targetRate:new AtomicInteger(rates[0]),workerRate:new AtomicInteger(rates[0]),arrivalCredit:arrivalCeiling-rates[0],arrivalLock:new Object(),controlNext:0L,controlFile:new File(output,'load-control.json'),schedule:schedule,summary:summary,lock:new Object(),rates:rates,stepSeconds:vars.get('stepSeconds').toInteger(),phaseStart:System.currentTimeMillis(),durationSeconds:duration+vars.get('drainSeconds').toInteger(),telemetry:new File(output,'telemetry.json'),telemetryNext:new java.util.concurrent.atomic.AtomicLong(),stopArrivals:new java.util.concurrent.atomic.AtomicBoolean(),stopApplied:new java.util.concurrent.atomic.AtomicBoolean(),stopFile:new File(output,'stop-arrivals')])
props.put('kudaMeetingDate',java.time.LocalDate.now(java.time.ZoneId.of('Europe/Volgograd')).plusDays(2).toString())
log.info('Куда: '+mode+'; '+schedule)
SampleResult.setIgnore()

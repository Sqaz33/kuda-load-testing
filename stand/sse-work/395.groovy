import groovy.json.JsonSlurper
def room=vars.getObject('roomJob')
try {
 if(!(prev.responseCode in ['200','201'])) throw new IllegalStateException('HTTP '+prev.responseCode+' на шаге '+args[0])
 def body=new JsonSlurper().parseText(prev.getResponseDataAsString())
 switch(args[0]) {
 case 'start':
  assert body.id==vars.get('roomId') : 'Ответ другой комнаты'
  if(args[0]=='started') {
   vars.put('waitMore',(body.status=='waiting').toString())
   if(body.status=='waiting') break
  }
  assert body.status=='swiping' && body.roundCandidateIds.size()==12 : 'Нет раунда из 12 карточек'
  break
 }
} catch(Throwable e) {
 AssertionResult.setFailure(true)
 AssertionResult.setFailureMessage(e.message ?: e.class.simpleName)
 vars.put('ok','false');vars.put('reason',e.message ?: e.class.simpleName)
 if(room!=null) room.cancelled.set(true)
}

import groovy.json.JsonSlurper
def room=vars.getObject('roomJob')
try {
 if(!(prev.responseCode in ['200','201'])) throw new IllegalStateException('HTTP '+prev.responseCode+' на шаге '+args[0])
 def body=new JsonSlurper().parseText(prev.getResponseDataAsString())
 switch(args[0]) {
 case 'poll':
  assert body.id==vars.get('roomId') : 'Ответ другой комнаты'
  if(body.winner && room.winner.get()) {
   assert body.winner.id==room.winner.get() : 'Победитель отличается'
   vars.put('sawWinner','true')
  }
  break
 }
} catch(Throwable e) {
 AssertionResult.setFailure(true)
 AssertionResult.setFailureMessage(e.message ?: e.class.simpleName)
 vars.put('ok','false');vars.put('reason',e.message ?: e.class.simpleName)
 if(room!=null) room.cancelled.set(true)
}

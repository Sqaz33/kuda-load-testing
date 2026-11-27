def run=props.get('kudaLoad')
log.info('Куда: создано '+run.started.get()+', успешно '+run.completed.get()+', ошибок '+run.failed.get())
if(run.started.get()==0 || run.failed.get()>0 || run.started.get()!=run.completed.get() || !run.members.isEmpty() || !run.polls.isEmpty()) {
 SampleResult.setSuccessful(false);SampleResult.setResponseCode('ROOMS_INCOMPLETE')
 SampleResult.setResponseMessage('Есть незавершённые компании; см. rooms.csv')
} else SampleResult.setIgnore()
props.remove('kudaLoad');props.remove('kudaMeetingDate')

import com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroupGui
import org.apache.jmeter.util.JMeterUtils
import org.apache.jmeter.save.SaveService
JMeterUtils.setJMeterHome('D:/apache-jmeter-5.6.3')
JMeterUtils.loadJMeterProperties('D:/apache-jmeter-5.6.3/bin/jmeter.properties')
println(new ConcurrencyThreadGroupGui().createTestElement().propertyIterator().collect { it.name+' = '+it.stringValue }.join('\n'))


def g=new ConcurrencyThreadGroupGui().createTestElement()
g.setName('worker')
g.setProperty('TargetLevel','10');g.setProperty('Unit','S');g.setProperty('Hold','60')
def h=new org.apache.jorphan.collections.HashTree();h.add(g)
SaveService.saveTree(h,new FileOutputStream('D:/kuda-load-testing/stand/concurrency-template.jmx'))

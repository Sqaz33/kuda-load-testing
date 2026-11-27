from capacity_policy import CapacitySearch
from run_laptop_capacity import sustained_verdict

def window(fail=False):
    return {'outcome': 'failed' if fail else 'passed', 'reasons': ['/v1/rooms: p95 too high'] if fail else []}
assert sustained_verdict([window(True), window(), window(), window()])[0] == 'passed'
assert sustained_verdict([window(), window(True), window(True), window(True)])[0] == 'failed'
assert sustained_verdict([window(True), window(), window(True), window()])[0] == 'passed'
assert sustained_verdict([window(), window(), window(True), window(True)])[0] == 'passed'
assert sustained_verdict([window(True), window(True), window(True), window()])[0] == 'passed'
assert sustained_verdict([window(True), window(True), window(True)])[0] == 'failed'
assert sustained_verdict([window(), window(True), window(True)])[0] == 'passed'
different=window(True)
different['reasons']=['/v1/rooms/{id}/votes: p95 too high']
assert sustained_verdict([window(True),different,window(True)])[0] == 'passed'
assert sustained_verdict([{'outcome':'inconclusive_monitoring','reasons':[]}]+[window()]*3)[0] == 'inconclusive_monitoring'
profile=CapacitySearch(start=224,ceiling=1024,increment=64)
assert profile.next().rate==224
profile.observe(224,'passed')
assert profile.next().rate==288
p=CapacitySearch(start=32, ceiling=256, increment=32)
for rate in range(32,257,32):
    assert p.next().rate == rate
    p.observe(rate, 'passed')
assert p.next().action == 'stop' and p.next().reason == 'lower_bound_only'
p=CapacitySearch(start=32, ceiling=256, increment=32)
for rate in (32,64,96): p.observe(rate, 'passed')
p.observe(128, 'failed')
assert p.next().rate == 112
print('SLA windows and stepped search: OK')

p=CapacitySearch(start=32, ceiling=256, increment=32)
p.observe(32,'failed')
assert p.next().rate == 16
p.observe(16,'failed')
assert p.next().rate == 8
p.observe(8,'passed')
assert p.next().rate == 12
print('Failed first stage halves rate instead of falling directly to one: OK')

import run_laptop_capacity as controller
old_mode=controller.SLA_MODE
controller.SLA_MODE='latency_only'
ops={name:{'count':64,'errors':64,'p95':.05} for name in controller.LIMITS}
assert controller.reasons_for(ops)==[]
assert controller.score({'directory':'test','lastIngestAt':100,'operations':ops},'test',64,100)[0]=='passed'
ops['/v1/rooms/{id}/votes']['p95']=.6
assert controller.score({'directory':'test','lastIngestAt':100,'operations':ops},'test',64,100)[0]=='failed'
controller.SLA_MODE=old_mode
print('Latency-only SLA retains latency failures but excludes error thresholds: OK')

from run_laptop_capacity import ramp_rate
assert [ramp_rate(t) for t in (0,30,60,90,120,180)] == [0,40,80,120,160,160]
p=CapacitySearch(start=160, ceiling=256, increment=16)
for rate in range(160,257,16):
    assert p.next().rate == rate
    p.observe(rate,'passed')
assert p.next().action == 'stop'
p=CapacitySearch(start=160, ceiling=256, increment=16)
p.observe(160,'failed')
assert p.next().rate == 144
print('Two-minute ramp and 160/+16 profile: OK')

credit=0;arrivals=0
for i in range(512):
    credit+=ramp_rate(i*120/512)
    if credit>=256:
        credit-=256;arrivals+=1
assert abs(arrivals-160)<=2,arrivals
print('Ramp admission integrates to approximately 160 rooms: OK')

import pathlib
import xml.etree.ElementTree as ET
plan=ET.parse(pathlib.Path(__file__).parents[1]/'kuda.jmx')
targets=[node.text for node in plan.iter('stringProp') if node.get('name')=='TargetLevel']
assert len(targets)==2
assert all("?:'0'" in target and 'cap>0 && n>cap?cap:n' in target for target in targets)
assert all(',' not in target for target in targets), 'Unescaped commas split JMeter function arguments'
print('Both helper groups have no fixed default cap; JMX XML is valid')

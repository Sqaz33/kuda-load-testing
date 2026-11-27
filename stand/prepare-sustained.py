from pathlib import Path
p=Path('D:/kuda-load-testing/stand/run_laptop_capacity.py')
s=p.read_text(encoding='utf8').replace('from capacity_policy import CapacitySearch','from capacity_policy import CapacitySearch, Decision')
i=s.index('\ndef main():')
helper="""
def sustained_verdict(evaluations):
    outcomes = [item['outcome'] for item in evaluations]
    if all(value == 'passed' for value in outcomes):
        return 'passed', []
    unknown = [value for value in outcomes if value not in ('passed', 'failed')]
    if unknown:
        return unknown[0], ['Insufficient or invalid minute windows']
    violations = [{reason.split(':')[0] for reason in item['reasons']}
                  for item in evaluations]
    common = set.intersection(*violations)
    if common:
        return 'failed', ['Sustained across all measured minutes: ' + ', '.join(sorted(common))]
    return 'unstable_results', ['Minute windows disagree; repeat this rate once']

"""
s=s[:i]+helper+s[i:]
s=s.replace("        baseline_failed = baseline_completed = None", "        repeated_rates = set()\n        room_samples = []",1)
s=s.replace("            telemetry = sample.get('telemetry', {})","""            telemetry = sample.get('telemetry', {})
            if telemetry:
                point = (telemetry.get('timestamp_seconds', now),
                         telemetry.get('failed_rooms', 0), telemetry.get('completed_rooms', 0))
                if not room_samples or point[0] != room_samples[-1][0]:
                    room_samples.append(point)
                room_samples = [point for point in room_samples if point[0] >= now - 600]
""",1)
a=s.index('                    if baseline_failed is None')
b=s.index('                        current.update(',a)
s=s[:a]+"""                    stage_seconds = 180 if state['stage'] == 1 else STEP
                    minute_count = 2 if state['stage'] == 1 else 3
                    if elapsed >= stage_seconds:
                        end = stage_start + stage_seconds
                        evaluations = []
                        window = {'minutes': evaluations}
                        for index in range(minute_count):
                            minute_end = end - (minute_count - index - 1) * MEASURE
                            minute_start = minute_end - MEASURE
                            params = urllib.parse.urlencode({'from': minute_start, 'to': minute_end})
                            measured = None
                            try:
                                for attempt in range(15):
                                    measured = request('/window?' + params)
                                    if measured.get('lastIngestAt', 0) >= minute_end:
                                        break
                                    time.sleep(1)
                                outcome, reasons = score(measured, folder, decision.rate, minute_end)
                                before = [v for v in room_samples if v[0] <= minute_start]
                                after = [v for v in room_samples if v[0] <= minute_end]
                                if before and after:
                                    failed = after[-1][1] - before[-1][1]
                                    done = after[-1][2] - before[-1][2] + failed
                                    if done >= 5 and failed / done > .01:
                                        outcome = 'failed'
                                        reasons.append(f'Room scenarios failed: {failed}/{done}')
                            except Exception as exc:
                                outcome, reasons = 'inconclusive_monitoring', [repr(exc)]
                            evaluations.append({'from': minute_start, 'to': minute_end,
                                                'outcome': outcome, 'reasons': reasons, 'data': measured})
                        outcome, reasons = sustained_verdict(evaluations)
                        if outcome == 'passed' and queue_since and now - queue_since >= 30:
                            outcome, reasons = 'inconclusive_generator', ['Persistent generator queue at stage end']
"""+s[b:]
s=s.replace('measurementFrom=stage_start+WARMUP,','measurementFrom=end-minute_count*MEASURE,')
s=s.replace('measurementTo=stage_start+STEP-SETTLE)', 'measurementTo=end)')
s=s.replace("""                        search.observe(decision.rate, outcome, confirmation=decision.action == 'confirm')
                        event""","""                        retry_mixed = outcome == 'unstable_results' and decision.rate not in repeated_rates
                        if not retry_mixed:
                            search.observe(decision.rate, outcome, confirmation=decision.action == 'confirm')
                        event""")
s=s.replace('                        decision = search.next()',"""                        if retry_mixed:
                            repeated_rates.add(decision.rate)
                            decision = Decision('probe', decision.rate, 'repeat mixed minute windows')
                        else:
                            decision = search.next()""")
s=s.replace('                            baseline_failed = baseline_completed = None\n','')
s=s.replace("'stageSeconds': STEP, 'warmupSeconds': WARMUP,","'stageSeconds': STEP, 'initialStageSeconds': 180, 'evaluationMinutes': 3, 'initialEvaluationMinutes': 2, 'warmupSeconds': WARMUP,")
s=s.replace("'slaEvaluation': 'Only the last minute of each 600-second stage'","'slaEvaluation': 'All final three separate minute windows must breach the same criterion; first stage uses two. Mixed results repeat once.'")
s=s.replace("event('Continuous run: 64 rooms/min; 10-minute stages; score only the last minute; no intermediate drain')","event('Continuous run: 64 rooms/min for 3 minutes; later stages 10 minutes; sustained minute-window SLA; no intermediate drain')")
compile(s,str(p),'exec')
assert 'baseline_failed' not in s
p.write_text(s,encoding='utf8')
e=Path('D:/kuda-load-testing/stand/results_exporter.py')
x=e.read_text(encoding='utf8')
x=x.replace('fresh=[r for r in RECENT if r[0]>=time.time()-120]','fresh=[r for r in RECENT if r[0]>=time.time()-600]')
x=x.replace("        for t,label,elapsed,ok,op in RECENT:\n            by[label]", "        for t,label,elapsed,ok,op in RECENT:\n            if t < time.time()-120:continue\n            by[label]")
x=x.replace('if start<time.time()-120:', 'if start<time.time()-600:')
compile(x,str(e),'exec')
e.write_text(x,encoding='utf8')
print('Controller and exporter compile')

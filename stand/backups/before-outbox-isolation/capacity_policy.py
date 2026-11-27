"""Integer room/min search policy; importing this module never starts a test."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    action: str
    rate: int | None
    reason: str


class CapacitySearch:
    def __init__(self, start=16, ceiling=512, resolution=1, increment=None):
        if not 1 <= start <= ceiling or resolution < 1:
            raise ValueError('Invalid search limits')
        self.start, self.ceiling, self.resolution = start, ceiling, resolution
        self.increment = increment
        self.low = self.high = None
        self.confirmed = False
        self.stop_reason = None
        self.history = []

    def next(self):
        if self.stop_reason:
            return Decision('stop', None, self.stop_reason)
        if not self.history:
            return Decision('probe', self.start, 'initial level')
        if self.low is None:
            if self.high <= 1:
                return Decision('stop', None, 'no_passing_level')
            return Decision('probe', max(1, self.high // 2), 'find a passing lower bound')
        if self.high is None:
            if self.low >= self.ceiling:
                return Decision('stop', None, 'lower_bound_only')
            return Decision('probe', min(self.ceiling, self.low + self.increment if self.increment else self.low * 2), 'find a failing upper bound')
        if self.high - self.low > self.resolution:
            return Decision('probe', self.low + (self.high - self.low) // 2, 'bisect proven bounds')
        if not self.confirmed:
            return Decision('confirm', self.low, 'confirm highest passing level once')
        return Decision('stop', None, 'bracketed_and_confirmed')

    def observe(self, rate, outcome, confirmation=False):
        self.history.append({'rate': rate, 'outcome': outcome, 'confirmation': confirmation})
        if outcome not in ('passed', 'failed'):
            self.stop_reason = outcome
        elif outcome == 'passed':
            if self.high is not None and rate >= self.high:
                self.stop_reason = 'unstable_results'
                return
            self.low = max(self.low or rate, rate)
            if confirmation:
                self.confirmed = True
        else:
            self.high = min(self.high or rate, rate)
            if self.low is not None and rate <= self.low:
                smaller = [r['rate'] for r in self.history
                           if r['outcome'] == 'passed' and r['rate'] < rate]
                self.low = max(smaller) if smaller else None
                self.stop_reason = 'unstable_results'

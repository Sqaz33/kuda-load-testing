import os
import json
import heapq
from collections import defaultdict

totals = defaultdict(int)
largest = []
errors = 0
stack = ['C:/']
while stack:
    directory = stack.pop()
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink() or os.path.isjunction(entry.path):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        size = entry.stat(follow_symlinks=False).st_size
                        parts = os.path.relpath(entry.path, 'C:/').split(os.sep)
                        for depth in range(1, min(4, len(parts))):
                            totals['C:/' + '/'.join(parts[:depth])] += size
                        item = (size, entry.path)
                        if len(largest) < 25:
                            heapq.heappush(largest, item)
                        elif size > largest[0][0]:
                            heapq.heapreplace(largest, item)
                except OSError:
                    errors += 1
    except OSError:
        errors += 1

print(json.dumps({
    'directories': sorted(totals.items(), key=lambda row: row[1], reverse=True)[:65],
    'largestFiles': sorted(largest, reverse=True),
    'inaccessibleEntries': errors
}, ensure_ascii=False, indent=2))

"""Pure, host-side scheduling and evidence validation for parallel_compare."""
import hashlib
import json
import os
from pathlib import Path
import stat

FORMAT = 'isolated-episode-compare-v1'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(path)


def digest(value):
    if not isinstance(value, bytes):
        value = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8', 'backslashreplace')
    return hashlib.sha256(value).hexdigest()


def fingerprints(directory):
    """Hash an evidence tree without following links outside the evidence mount."""
    out = {}
    def failed(exc):
        raise exc
    paths = []
    for base, dirs, files in os.walk(directory, followlinks=False, onerror=failed):
        paths.extend(Path(base)/name for name in dirs+files)
    for path in sorted(paths):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('non-regular evidence entry: '+str(path))
        out[str(path.relative_to(directory))] = digest(path.read_bytes())
    return out


def partition(episodes, parallelism, durations):
    """Deterministic longest-first packing; each lane executes its list serially."""
    lanes = [[] for _ in range(min(parallelism, len(episodes)))]
    loads = [0.] * len(lanes)
    for wf in sorted(episodes, key=lambda w: (-durations.get(w, 1), w)):
        slot = min(range(len(lanes)), key=lambda i: (loads[i], i))
        lanes[slot].append(wf)
        loads[slot] += max(0., durations.get(wf, 1))
    return lanes


def validate_rows(rows, episode):
    """Completeness plus immutable episode/point associations before any reuse."""
    expected = {a['id']: (cp, a) for cp in episode['checkpoints'] for a in cp['assertions']}
    if len(rows) != len(expected) or {r['id'] for r in rows} != set(expected):
        raise ValueError('missing or duplicate assertion rows')
    for r in rows:
        cp, a = expected[r['id']]
        if (r['episode'] != episode['id'] or r['checkpoint'] != cp['id']
                or r['channel'] != a['channel'] or r['method'] != a['method']
                or r['feature'] != episode['feature']):
            raise ValueError('assertion belongs to another episode/specification')
        if r['status'] not in ('pass', 'fail', 'unresolved', 'blocked'):
            raise ValueError('unknown assertion status')
        if type(r['passed']) is not bool or r['passed'] != (r['status']=='pass') or r['score'] != int(r['passed']):
            raise ValueError('inconsistent assertion verdict')
        if r.get('failure_kind') == 'infrastructure':
            raise ValueError('infrastructure failure cannot be reused')


def completed(directory, episode):
    """Valid failures count as completed. Missing/infra/torn outputs do not."""
    directory = Path(directory)
    try:
        status = read(directory/'status.json')
        if status['source_episode'] != episode['id'] or status['infrastructure_error']:
            return False
        if any((directory/n).exists() for n in ('infrastructure-error.json', 'worker-error.json')):
            return False
        rows = [json.loads(s) for s in (directory/'results.jsonl').read_text().splitlines()]
        validate_rows(rows, episode)
        usage = read(directory/'usage.json')
        if not isinstance(usage, dict) or usage.get('elapsed_seconds', -1) < 0:
            return False
        fingerprints(directory)
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def check_lane_identity(actual, parent, assigned):
    for key in ('sources', 'candidate', 'manifest_sha256', 'evaluator', 'mode'):
        if actual.get(key) != parent[key]:
            raise ValueError('lane identity mismatch: '+key)
    if actual.get('episodes') != sorted(assigned) or actual.get('diagnostic') is not True:
        raise ValueError('lane selection mismatch')


def check_resume(previous, current):
    if previous != current:
        keys = sorted(k for k in previous.keys() | current.keys() if previous.get(k) != current.get(k))
        raise ValueError('resume identity differs: '+', '.join(keys))


def parent_finished(output, episode):
    """Worker status alone is insufficient after an external stop/host crash.

    The serial parent emits an episode receipt only after waiting, cleanup and
    fault classification. Final summary/results also cover missing-start rows.
    """
    output = Path(output)
    if (output/'summary.json').exists() and (output/'results.jsonl').exists():
        return True
    log = output.parent/'container.log'
    if not log.exists():
        return False
    for line in log.read_text(errors='replace').splitlines():
        try:
            receipt = json.loads(line)
        except ValueError:
            continue
        if (isinstance(receipt, dict) and receipt.get('episode') == episode
                and receipt.get('infrastructure_error') is False and 'timed_out' in receipt):
            return True
    return False

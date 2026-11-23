"""Calculate task rewards from complete episode results.

Each episode has equal weight and passes only when every assertion passes.
Channel statistics are reported separately for inspection.
"""
from collections import Counter

STATUSES = ('pass', 'fail', 'unresolved', 'blocked')


def aggregate(manifest, rows, *, mode='compare', diagnostic=False, invalid=False):
    if mode not in ('record', 'compare'):
        raise ValueError('unsupported assessment mode')
    episodes = manifest['episodes']
    if not episodes or len({w['id'] for w in episodes}) != len(episodes):
        raise ValueError('expected nonempty unique episodes')
    expected, groups = {}, {}
    for wf in episodes:
        groups[wf['id']] = []
        for cp in wf['checkpoints']:
            for a in cp['assertions']:
                if a['id'] in expected or a['channel'] not in ('backend', 'frontend'):
                    raise ValueError('duplicate or invalid assertion')
                expected[a['id']] = (wf['id'], cp['id'], wf['feature'], a['channel'], a['method'])
                groups[wf['id']].append(a['id'])
        if not groups[wf['id']]:
            raise ValueError('episode has no assertions')
    if len(rows) != len(expected) or {r['id'] for r in rows} != set(expected):
        raise ValueError('results must cover every selected assertion exactly once')
    for row in rows:
        if tuple(row[k] for k in ('episode', 'checkpoint', 'feature', 'channel', 'method')) != expected[row['id']]:
            raise ValueError('result identity differs from manifest: '+row['id'])
        if (row['status'] not in STATUSES or type(row['passed']) is not bool
                or row['passed'] != (row['status'] == 'pass') or row['score'] != int(row['passed'])):
            raise ValueError('inconsistent result verdict: '+row['id'])
        invalid |= row.get('failure_kind') == 'infrastructure'
    by_id = {r['id']: r for r in rows}
    passed = sum(all(by_id[point]['passed'] for point in ids) for ids in groups.values())
    ratio = passed/len(episodes)

    def channel(name):
        points = [r for r in rows if r['channel'] == name]
        count = sum(r['passed'] for r in points)
        statuses = Counter(r['status'] for r in points)
        return {'assertions': len(points), 'passed': count,
                'ratio': count/len(points) if points else 0.,
                'statuses': {status: statuses[status] for status in STATUSES}}

    backend, frontend = channel('backend'), channel('frontend')
    return {'episode_passed': passed, 'episode_total': len(episodes),
            'episode_rate': ratio, 'backend': backend, 'frontend': frontend,
            'all_passed': all(r['passed'] for r in rows), 'infrastructure_error': bool(invalid),
            'reward': None if invalid or diagnostic or mode == 'record' else round(ratio, 6)}

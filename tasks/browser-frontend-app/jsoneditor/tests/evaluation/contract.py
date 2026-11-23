"""Episode/assertion protocol v2, frozen bundles and evidence identities.

Shared verbatim by every program-bench task; task identity and runtime
configuration live in task.py.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from .task import TASK, VERSION, REFERENCE, SURFACE, RUNTIME

PROTOCOL = 'episode-evaluation-v2'
KIT_VERSION = '1.0.0'
FRONTEND_LIMIT = 1000
HERE = Path(__file__).resolve().parents[1]
STATE_ROOT = Path('/app/candidate-state')
WORKSPACE_NAME = 'session'
STATUSES = ('pass', 'fail', 'unresolved', 'blocked')
# Why a point did not pass. Only these kinds exist; SCHEMA.md explains each.
FAILURE_KINDS = {
    'fail': {'result_mismatch', 'program_exception', 'agent_verdict', 'companion', 'candidate_timeout'},
    'unresolved': {'agent_verdict', 'budget', 'observation', 'report_protocol'},
    'blocked': {'dependency', 'setup_failure', 'candidate_start', 'candidate_missing_start', 'candidate_timeout',
                'infrastructure'},
}
SETUP_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')


def files_path(area, name='', *, instance=True, state_root=STATE_ROOT):
    """Absolute exchange path for specifications and hooks, independent of episode IDs.

    The default layout is session/instance/files/<area>/<name>. Brokers whose
    exchange directory is beside the instance directory use instance=False,
    giving session/files/<area>/<name>. area and name are relative paths without
    parent components; name may be empty. state_root supports explicit custom
    installations and defaults to the runner's state root.
    """
    root = Path(state_root)
    if not root.is_absolute():
        raise ValueError('state_root must be absolute')
    parts = [Path(area), Path(name)]
    if not str(area) or any(path.is_absolute() or '..' in path.parts for path in parts):
        raise ValueError('exchange paths must be relative without parent components')
    workspace = root / WORKSPACE_NAME
    return str((workspace / 'instance' if instance else workspace) / 'files' / parts[0] / parts[1])


class InfrastructureError(RuntimeError):
    """The verifier itself failed (runtime, decoder, evidence storage); the run is invalid instead of scored."""


class ObservationUnavailable(RuntimeError):
    """The candidate's interface could not be observed or stopped answering; that checkpoint's frontend points
    stay unresolved."""


class CandidateTimeout(BaseException):
    """The episode reached its wall-clock limit (raised from the SIGTERM handler); never caught by task code."""


def encoded(value):
    # A lone surrogate (a file name that is not UTF-8) becomes a JSON \\u escape; all other text encodes as UTF-8.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8', 'backslashreplace')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encoded(value)).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix+'.pending')
    pending.write_bytes(encoded(value))
    pending.replace(path)


def tree(root, prefix, skip=None):
    root = Path(root)
    return {prefix+str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob('*'))
            if p.is_file() and not (skip and p.is_relative_to(skip))
            and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def source_identity():
    """Source identity for run outputs and resume checks; it is not part of frozen bundles."""
    files = tree(HERE, 'tests/', HERE/'data')
    runtime = Path(RUNTIME)
    if runtime.is_dir():
        files.update(tree(runtime, 'runtime/'))
    else:
        files['runtime/'] = 'missing'
    return files


def candidate_identity(path):
    """Content digests of the submitted files. Links are recorded by their target and never followed, special files
    are skipped, and a file that cannot be read is recorded as such, so nothing a candidate leaves in its directory
    can stop a run."""
    root = Path(path)
    if not root.is_dir():
        return {}
    skip = {'.git', '.tmp', '__pycache__'}
    files = {}
    for top, dirs, names in os.walk(root):
        base = Path(top)
        for name in list(dirs):
            if name in skip or (base / name).is_symlink():
                dirs.remove(name)
                if name not in skip:
                    names.append(name)
        for name in names:
            if name in skip:
                continue
            p = base / name
            key = str(p.relative_to(root))
            try:
                if stat.S_ISLNK(p.lstat().st_mode):
                    files[key] = 'link:' + os.readlink(p)
                    continue
                fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as f:
                    if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                        continue
                    h = hashlib.sha256()
                    for block in iter(lambda: f.read(1 << 20), b''):
                        h.update(block)
                files[key] = h.hexdigest()
            except OSError as exc:
                files[key] = f'unreadable:{exc.errno}'
    return dict(sorted(files.items()))


def assertions(episode):
    return [a for checkpoint in episode['checkpoints'] for a in checkpoint['assertions']]


def manifest(episodes):
    """Common manifest envelope; episode content is task-specific. The evaluator model is runtime
    configuration of the host bridge and is not part of the manifest."""
    points = [a for w in episodes for a in assertions(w)]
    value = {'task':TASK,'version':VERSION,'kit':KIT_VERSION,'protocol':PROTOCOL,'reference_version':REFERENCE,
             'surface':SURFACE,'execution_unit':'episode','scoring_unit':'episode',
             'episodes':episodes,
             'counts':{'episodes':len(episodes),'features':len({w['feature'] for w in episodes}),
                       'checkpoints':sum(len(w['checkpoints']) for w in episodes),'assertions':len(points),
                       'frontend':0,'backend':0,**dict(Counter(a['channel'] for a in points)),
                       'gui_episodes':sum(w['execution']!='program' for w in episodes),
                       'program_episodes':sum(w['execution']=='program' for w in episodes)}}
    validate_manifest(value)
    return value


def validate_manifest(manifest):
    assert manifest['task']==TASK and manifest['protocol']==PROTOCOL and manifest['version']==VERSION
    assert manifest.get('kit')==KIT_VERSION and 'model' not in manifest
    episodes=manifest['episodes'];assert episodes
    assert len({w['id'] for w in episodes})==len(episodes)
    all_ids=[]
    for episode in episodes:
        assert episode['execution'] in {'program','gui','mixed'}
        assert episode['initial_state'] and episode['feature']
        setup=episode.get('setup',[])
        assert isinstance(setup,list) and all(isinstance(s,dict) for s in setup)
        setup_ids=[s.get('id') for s in setup]
        assert all(isinstance(i,str) and SETUP_ID.fullmatch(i) for i in setup_ids),'setup items need ids'
        assert len(set(setup_ids))==len(setup_ids),'setup ids must be unique'
        checkpoint_ids={cp['id'] for cp in episode['checkpoints']}
        position={cp['id']:i for i,cp in enumerate(episode['checkpoints'])}
        # A setup item runs at episode start, or right before the checkpoint named by 'before'.
        ready_at={}
        for item in setup:
            if item.get('before'):
                assert item['before'] in position,'setup before an unknown checkpoint: '+str(item['before'])
                ready_at[item['id']]=position[item['before']]
            else:
                ready_at[item['id']]=-1
        assertion_ids={a['id'] for a in assertions(episode)}
        assert not checkpoint_ids & assertion_ids and not any(i.startswith('setup:') for i in checkpoint_ids)
        seen,seen_points=set(),set()
        for cp in episode['checkpoints']:
            assert cp['id'] not in seen and cp['goal']
            for dep in cp.get('depends_on',[]):
                if dep.startswith('setup:'):
                    assert dep[6:] in setup_ids,'unknown setup dependency '+dep
                    assert ready_at[dep[6:]]<=position[cp['id']],'a checkpoint depends on setup that runs after it: '+dep
                elif dep in checkpoint_ids:
                    assert dep in seen,'a checkpoint may only depend on earlier checkpoints: '+dep
                else:
                    assert dep in seen_points,'an assertion dependency must name an earlier assertion: '+dep
            seen.add(cp['id'])
            assert cp['assertions'],'a checkpoint must declare at least one assertion'
            for a in cp['assertions']:
                assert a['channel'] in {'frontend','backend'}
                assert a['method']==('agent' if a['channel']=='frontend' else 'program')
                assert a['requirement'];all_ids.append(a['id'])
            seen_points.update(a['id'] for a in cp['assertions'])
        companions={a['id']:list(a.get('requires',[])) for a in assertions(episode)}
        for point,required in companions.items():
            assert all(r in assertion_ids and r!=point for r in required),'companions must be other points of the episode'
        state={}
        def acyclic(point):
            if state.get(point)=='done':return
            assert state.get(point)!='open','companion bindings must not form a cycle'
            state[point]='open'
            for r in companions[point]:acyclic(r)
            state[point]='done'
        for point in companions:acyclic(point)
        frontend=any(a['channel']=='frontend' for a in assertions(episode))
        assert frontend==(episode['execution']!='program'),'only GUI/mixed episodes carry frontend points'
        if frontend:
            assert episode['budget']['calls']>0 and episode['budget']['tokens']>0 and episode['budget']['seconds']>0
            assert isinstance(episode.get('session'),str) and episode['session']
    assert len(set(all_ids))==len(all_ids)
    assert sum(a['channel']=='frontend' for w in episodes for a in assertions(w))<=FRONTEND_LIMIT


def result(assertion, episode, checkpoint, status, reason='', evidence=(), failure_kind=None):
    assert status in STATUSES
    kind=None if status=='pass' else failure_kind or status
    assert kind is None or kind in FAILURE_KINDS[status],(status,kind)
    return {'id':assertion['id'],'episode':episode['id'],'checkpoint':checkpoint['id'],
            'feature':episode['feature'],'channel':assertion['channel'],'method':assertion['method'],
            'status':status,'passed':status=='pass','score':int(status=='pass'),
            'reason':str(reason)[:2000],'evidence':list(evidence),'failure_kind':kind}


def validate_rows(rows, episodes):
    expected={a['id']:a for w in episodes for a in assertions(w)}
    assert len(rows)==len(expected) and {r['id'] for r in rows}==set(expected)
    for row in rows:
        assert row['status'] in STATUSES
        assert row['score']==int(row['status']=='pass') and row['passed']==(row['status']=='pass')
        assert row['channel']==expected[row['id']]['channel']
        assert isinstance(row['evidence'],list)
        assert (row['failure_kind'] is None) if row['status']=='pass' else row['failure_kind'] in FAILURE_KINDS[row['status']]


def gate(dependency, episode, rows, setup_ok):
    """Whether one declared prerequisite passed. A checkpoint passes when its backend points pass, or
    its frontend points when it has no backend points; an assertion passes when its row passes; a setup item
    passes when it succeeded. Gating only decides whether dependents run."""
    if dependency.startswith('setup:'):
        return setup_ok.get(dependency[6:]) is True
    for cp in episode['checkpoints']:
        if cp['id']==dependency:
            backend=[a['id'] for a in cp['assertions'] if a['channel']=='backend']
            return all(rows.get(i,{}).get('status')=='pass' for i in backend or [a['id'] for a in cp['assertions']])
    return rows.get(dependency,{}).get('status')=='pass'


def apply_companions(episode, rows):
    """A point bound to companion points ('requires') passes only if every companion passes; points whose
    companions have no row yet are left for a later call."""
    changed=True
    while changed:
        changed=False
        for a in assertions(episode):
            row,required=rows.get(a['id']),a.get('requires') or []
            if not row or row['status']!='pass' or not required or any(r not in rows for r in required):
                continue
            missing=[r for r in required if rows[r]['status']!='pass']
            if missing:
                row.update(status='fail',passed=False,score=0,failure_kind='companion',
                           reason=('Bound to '+', '.join(missing)+', which did not pass; this point only counts '
                                   'together with it. Own check passed: '+row['reason'])[:2000])
                changed=True


class Evidence:
    def __init__(self, directory, episode):
        self.directory=Path(directory);self.episode=episode;self.items={}
        self.directory.mkdir(parents=True,exist_ok=True)

    def add(self, checkpoint, role, observation, png=None):
        stem=f'e{len(self.items)+1:05d}'
        identity=f'{self.episode}/{checkpoint}/{role}/{stem}'
        write(self.directory/(stem+'.json'),observation)
        item={'id':identity,'episode':self.episode,'checkpoint':checkpoint,'role':role,
              'observation':stem+'.json','observation_sha256':digest((self.directory/(stem+'.json')).read_bytes())}
        if png is not None:
            (self.directory/(stem+'.png')).write_bytes(png)
            item.update(image=stem+'.png',image_sha256=digest(png))
        self.items[identity]=item;write(self.directory/'index.json',self.items)
        return identity

    def text(self, checkpoint, role, text, suffix='.txt'):
        """Plain-text evidence such as a program exception's traceback."""
        stem=f'e{len(self.items)+1:05d}'
        identity=f'{self.episode}/{checkpoint}/{role}/{stem}'
        (self.directory/(stem+suffix)).write_text(text)
        self.items[identity]={'id':identity,'episode':self.episode,'checkpoint':checkpoint,'role':role,
                              'file':stem+suffix,'sha256':digest((self.directory/(stem+suffix)).read_bytes())}
        write(self.directory/'index.json',self.items)
        return identity

    def read(self, identity):
        item=self.items[identity]
        obs=json.loads((self.directory/item['observation']).read_text())
        png=(self.directory/item['image']).read_bytes() if item.get('image') else None
        return obs,png


def parse_verdict(message, checkpoint, available, required_actual):
    """Validate one report_checkpoint call.

    available maps each citable token (an evidence ID or a short label such as
    'reference-after') to its evidence item; cited tokens are returned as IDs.
    """
    calls=message.get('tool_calls') or []
    if not isinstance(calls,list) or len(calls)!=1 or not isinstance(calls[0],dict) or not isinstance(calls[0].get('function'),dict) or calls[0]['function'].get('name')!='report_checkpoint':
        raise ValueError('expected one report_checkpoint call')
    try:body=json.loads(calls[0]['function']['arguments'])
    except (KeyError,TypeError,json.JSONDecodeError):raise ValueError('invalid checkpoint JSON') from None
    if not isinstance(body,dict) or set(body)!={'assertions'} or not isinstance(body['assertions'],list):
        raise ValueError('invalid checkpoint report')
    expected={a['id'] for a in checkpoint['assertions'] if a['channel']=='frontend'}
    reports=body['assertions']
    if any(not isinstance(r,dict) or not isinstance(r.get('id'),str) for r in reports):
        raise ValueError('invalid assertion identity')
    if len(reports)!=len(expected) or {r.get('id') for r in reports}!=expected:
        raise ValueError('every declared frontend assertion must be reported exactly once')
    actual=next((i for i in available.values() if i['id']==required_actual),None)
    if actual is None:raise ValueError('current candidate evidence is not citable')
    for report in reports:
        if set(report)!={'id','status','reason','evidence'} or report['status'] not in ('pass','fail','unresolved'):
            raise ValueError('invalid assertion report')
        if not isinstance(report['reason'],str) or not report['reason'].strip():raise ValueError('missing evidence explanation')
        cited=report['evidence']
        if not isinstance(cited,list) or not all(isinstance(x,str) for x in cited) or not set(cited)<=set(available):
            raise ValueError('unknown or foreign evidence citation')
        items=[available[x] for x in cited]
        if required_actual not in {i['id'] for i in items}:raise ValueError('report must cite the current candidate checkpoint evidence')
        if any(i['checkpoint']!=checkpoint['id'] or i['episode']!=actual['episode'] for i in items):
            raise ValueError('evidence belongs to another episode/checkpoint')
        if not any(i['role']=='reference-after' for i in items):
            raise ValueError('report must cite the reference checkpoint evidence')
        report['evidence']=list(dict.fromkeys(i['id'] for i in items))
    return reports


def read_frozen_evidence(directory, item):
    """Read a reference observation and optional image, including shared image paths.

    Paths are relative to the bundle, so an image may live at an earlier
    checkpoint or episode. Older bundles with per-item digests also work;
    those metadata fields are not required or consulted.
    """
    root = Path(directory).resolve()

    def path(field):
        value = Path(item[field])
        target = (root / value).resolve()
        if value.is_absolute() or not target.is_relative_to(root) or not target.is_file():
            raise ValueError('missing or invalid reference evidence path: ' + str(value))
        return target

    observation = json.loads(path('observation').read_text())
    image = path('image').read_bytes() if item.get('image') else None
    return observation, image


def load_frozen(directory, built):
    """Validate the functional manifest and completeness of a frozen bundle.

    Source integrity is checked within each run, independently of this bundle.
    Returns (manifest, oracle, meta).
    """
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text());oracle=json.loads((directory/'oracle.json').read_text())
    meta=json.loads((directory/'oracle-meta.json').read_text())
    validate_manifest(manifest)
    assert manifest==built,'frozen functional specification differs from executable specification'
    assert meta['record']['all_passed'] and meta['record']['model_calls']==0
    assert set(meta['record'].get('durations',{}))=={w['id'] for w in manifest['episodes']},'recorded durations missing'
    expected={a['id'] for w in manifest['episodes'] for a in assertions(w) if a['channel']=='backend'}
    assert set(oracle['program'])==expected,'incomplete program observations'
    front={w['id']+'/'+cp['id'] for w in manifest['episodes'] for cp in w['checkpoints'] if any(a['channel']=='frontend' for a in cp['assertions'])}
    assert set(oracle['frontend'])==front,'incomplete reference frontend checkpoints'
    for pair in oracle['frontend'].values():
        assert set(pair)=={'before','after'}
        for e in pair.values():
            read_frozen_evidence(directory,e)
    return manifest,oracle,meta

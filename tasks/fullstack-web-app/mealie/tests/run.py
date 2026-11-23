#!/usr/bin/env python3
"""Serial episode runner: deterministic record and single-agent compare.

Shared verbatim by every task. suite.py builds the manifest; worker.py (the
shared driver plus task hooks) runs one episode in its own runtime instance.
Episodes run one at a time; each has a wall-clock limit derived from its
frozen budget and recorded reference duration.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time
import traceback
from evaluation.task import TASK, RUNTIME
from evaluation.contract import (VERSION, KIT_VERSION, PROTOCOL, HERE, STATE_ROOT, WORKSPACE_NAME,
                                 assertions, candidate_identity, digest, result,
                                 source_identity, validate_rows, write)
from evaluation.model_client import PROTOCOLS
from evaluation.scoring import aggregate
from evaluation.driver import CANDIDATE_USER, kill_candidate
import suite

GRACE = 30


def clear_workspace(state):
    """Atomically detach a previous session, then remove it without following links.

    The state root is managed by the runner. Any failure to remove a detached
    entry invalidates the run; a new worker must never inherit old state.
    """
    state = Path(state)
    fd = os.open(state.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        detached = '.cleanup-' + secrets.token_hex(16)
        try:
            os.rename(state.name, detached, src_dir_fd=fd, dst_dir_fd=fd)
        except FileNotFoundError:
            return
        info = os.stat(detached, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            # The renamed entry lives under a trusted directory and no worker
            # is running. /proc/self/fd anchors the parent on Python versions
            # whose symlink-safe rmtree does not yet accept dir_fd.
            if not shutil.rmtree.avoids_symlink_attacks:
                raise ValueError('descriptor-based workspace cleanup is unavailable')
            shutil.rmtree(f'/proc/self/fd/{fd}/{detached}')
        else:
            os.unlink(detached, dir_fd=fd)
    finally:
        os.close(fd)


def verify_state_root(path):
    """Require a root-owned real state directory that the application cannot replace.

    The application must not be able to write the directory. Its ancestors
    must also be unwritable to that user, unless the directory is a mount point.
    Bind mounts are recognized from mountinfo as well as ordinary mount points.
    This check never changes ownership or repairs an untrusted path.
    """
    path = Path(os.path.abspath(path))
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0:
        raise ValueError('state root must be a real directory owned by root')
    for parent in path.parents:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('state root ancestors must be real directories')

    def unwritable(directory):
        probe = subprocess.run(['runuser', '-u', CANDIDATE_USER, '--', 'test', '-w', str(directory)],
                               capture_output=True)
        if probe.returncode != 1:
            raise ValueError('application can write a state directory or its parent: ' + str(directory))

    unwritable(path)
    mounts = {re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), line.split()[4])
              for line in Path('/proc/self/mountinfo').read_text().splitlines()}
    if str(path) not in mounts and not path.is_mount():
        for parent in path.parents:
            unwritable(parent)


def tree_integrity(root):
    """Snapshot content, entry types, owners and modes, including empty directories.

    The snapshot is held by this process only. Links are described without
    traversing them; regular files are read through no-follow descriptors.
    """
    root = Path(root)
    entries = {}

    def visit(path):
        info = path.lstat()
        kind = stat.S_IFMT(info.st_mode)
        content = None
        if stat.S_ISREG(info.st_mode):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ValueError('protected file changed while reading: ' + str(path))
                content = digest(stream.read())
        elif stat.S_ISLNK(info.st_mode):
            content = os.readlink(path)
        elif not stat.S_ISDIR(info.st_mode):
            raise ValueError('unsupported entry in protected directory: ' + str(path))
        entries[str(path.relative_to(root))] = (kind, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), content)
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)

    visit(root)
    return entries


def verify_integrity(baseline, private):
    """Fail the entire run if protected files or private-directory access changed."""
    for path, expected in baseline.items():
        if tree_integrity(path) != expected:
            raise ValueError('protected directory integrity changed: ' + str(path))
    for path in dict.fromkeys(private):
        if not path.is_dir():
            raise ValueError('private directory is missing: ' + str(path))
        for access in ('-r', '-x'):
            probe = subprocess.run(['runuser', '-u', CANDIDATE_USER, '--', 'test', access, str(path)],
                                   capture_output=True)
            if probe.returncode != 1:
                raise ValueError('private-directory access check failed: ' + str(path))


def summarize(manifest, rows, usages, *, mode, diagnostic, elapsed, invalid=False, evaluator=None, resumed=()):
    validate_rows(rows, manifest['episodes'])
    scoring=aggregate(manifest,rows,mode=mode,diagnostic=diagnostic,invalid=invalid)
    keys=('setup_calls','program_calls','setup_seconds','model_calls','tokens','gui_actions','model_seconds',
          'model_wait_seconds','reference_gui_events','candidate_restarts')
    usage={key:sum(x.get(key,0) for x in usages) for key in keys}
    return {'task':TASK,'version':VERSION,'kit':KIT_VERSION,'protocol':PROTOCOL,'mode':mode,
            'full_suite':not diagnostic,'diagnostic':diagnostic,'counts':manifest['counts'],
            **scoring,
            'failure_kinds':dict(sorted(Counter(r['failure_kind'] for r in rows if r['failure_kind']).items())),
            'evaluator':evaluator,'resumed_episodes':list(resumed),
            'usage':usage,'seconds':round(elapsed,3)}


def failure_rows(episode, reason, kind, status='blocked', keep=()):
    kept={r['id']:r for r in keep}
    return [kept.get(a['id']) or result(a,episode,cp,status,reason,failure_kind=kind)
            for cp in episode['checkpoints'] for a in cp['assertions']]


def freeze(directory, manifest, output, identity, summary, durations):
    """Publish only a complete successful zero-model reference run."""
    assert summary['all_passed'] and not summary['infrastructure_error'] and not summary['diagnostic']
    assert summary['usage']['model_calls']==0
    directory=Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('record requires a fresh frozen-bundle directory')
    directory.mkdir(parents=True,exist_ok=True)
    oracle={'program':{},'frontend':{}}
    images={}
    for wf in manifest['episodes']:
        root=output/'episodes'/wf['id']
        data=json.loads((root/'record.json').read_text())
        oracle['program'].update(data['program'])
        for checkpoint in wf['checkpoints']:
            cp=checkpoint['id']
            if cp not in data['frontend']:continue
            refs=data['frontend'][cp]
            pair={}
            for role in ('before','after'):
                item=refs[role]
                item={key:value for key,value in item.items() if not key.endswith('_sha256')}
                for field in ('observation','image'):
                    if field not in item:continue
                    source=root/'evidence'/item[field]
                    relative=Path('reference')/wf['id']/source.name
                    if field=='image':
                        fingerprint=digest(source.read_bytes())
                        if fingerprint in images:
                            item[field]=images[fingerprint]
                            continue
                        images[fingerprint]=str(relative)
                    target=directory/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,target);item[field]=str(relative)
                pair[role]=item
            oracle['frontend'][wf['id']+'/'+cp]=pair
    expected={a['id'] for w in manifest['episodes'] for a in assertions(w) if a['channel']=='backend'}
    assert set(oracle['program'])==expected
    write(directory/'manifest.json',manifest);write(directory/'oracle.json',oracle)
    shutil.copyfile(HERE/'data/schema.json',directory/'schema.json')
    write(directory/'coverage.json',{'version':VERSION,'kit':KIT_VERSION,'protocol':PROTOCOL,'counts':manifest['counts'],
        'features':{feature:{'episodes':[w['id'] for w in manifest['episodes'] if w['feature']==feature],
                    'assertions':sum(len(assertions(w)) for w in manifest['episodes'] if w['feature']==feature)}
                    for feature in sorted({w['feature'] for w in manifest['episodes']})}})
    write(directory/'oracle-meta.json',{'version':VERSION,'kit':KIT_VERSION,'protocol':PROTOCOL,
        'record':{'all_passed':True,'model_calls':0,'counts':manifest['counts'],'durations':durations}})


def model_config(directory, manifest):
    """The evaluator is runtime configuration of the host bridge: recorded, never frozen."""
    path=directory/'config.json'
    if not path.is_file():raise ValueError('compare needs an externally started model bridge at --model-rpc')
    config=json.loads(path.read_text())
    for key in ('model','effort','base_url','protocol'):
        if not isinstance(config.get(key),str) or not config[key]:raise ValueError('model bridge config lacks '+key)
    if config['protocol'] not in PROTOCOLS:raise ValueError('model bridge speaks an unsupported protocol')
    for wf in manifest['episodes']:
        if wf['execution']=='program':continue
        if config.get('max_calls',0)<wf['budget']['calls'] or config.get('max_tokens',0)<wf['budget']['tokens']:
            raise ValueError('model bridge ceiling must cover each frozen episode budget')
    return {k:config[k] for k in ('model','effort','base_url','protocol','max_calls','max_tokens')}


def wall_limit(episode, durations):
    """Seconds of candidate and verifier time an episode may take (model waiting excluded)."""
    recorded=durations.get(episode['id'])
    if episode['execution']=='program':
        return max(900,5*recorded) if recorded else 3600
    return episode['budget']['seconds']+(max(600,5*recorded) if recorded else 1800)


def model_wait(directory):
    try:
        state=json.loads((directory/'model-wait.json').read_text())
    except (OSError,ValueError):
        return 0.
    return state.get('total',0)+(max(0.,time.time()-state['since']) if state.get('since') else 0.)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode',choices=['record','compare'],default='compare')
    ap.add_argument('--start',default='/app/solution/start.sh',type=Path)
    ap.add_argument('--state-root',default=STATE_ROOT,type=Path)
    ap.add_argument('--out',default='/logs/verifier',type=Path)
    ap.add_argument('--truth',default=HERE/'data',type=Path,help='frozen bundle directory; record requires a fresh destination')
    ap.add_argument('--model-rpc',default='/model',type=Path)
    ap.add_argument('--episode',action='append',help='author diagnostic only; never emits a formal reward or full frozen bundle')
    ap.add_argument('--manifest-only',action='store_true')
    ap.add_argument('--resume-from',type=Path,help='reuse completed episodes of an identical interrupted (non-diagnostic) run')
    args=ap.parse_args(argv)
    os.umask(0o027)
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    # Root keeps the collector's group even with CAP_FSETID dropped. Files are
    # readable to Harbor/host collection but not to the candidate's distinct GID.
    if os.geteuid()==0:os.setgid(out.stat().st_gid)
    out.chmod(0o2750)
    if any((out/name).exists() for name in ('episodes','identity.json','results.jsonl','summary.json','reward.txt','reward.json')):
        ap.error('use a fresh output directory; previous evidence is preserved')
    started=time.monotonic();manifest=None;identity=None;rows=[];usages=[];resumed=[]
    diagnostic=bool(args.episode)
    try:
        baseline={} if args.manifest_only else {path:tree_integrity(path) for path in (HERE,Path(RUNTIME))}
        if not args.manifest_only:verify_state_root(args.state_root)
        manifest=suite.build()
        meta=None
        if args.mode=='compare' and not args.manifest_only:manifest,_,meta=suite.load(args.truth)
        evaluator=model_config(args.model_rpc,manifest) if args.mode=='compare' and not args.manifest_only else None
        selected=manifest['episodes']
        if args.episode:
            unknown=set(args.episode)-{w['id'] for w in manifest['episodes']}
            if unknown:raise ValueError('unknown episodes: '+str(sorted(unknown)))
            selected=[w for w in manifest['episodes'] if w['id'] in args.episode]
        identity={'version':VERSION,'kit':KIT_VERSION,'protocol':PROTOCOL,'manifest_sha256':digest(manifest),
                  'sources':source_identity(),'candidate':candidate_identity(args.start.parent),
                  'evaluator':evaluator,'mode':args.mode,'episodes':sorted(w['id'] for w in selected),
                  'diagnostic':diagnostic}
        present=args.start.is_file()
        if os.geteuid()!=0 and not args.manifest_only:raise ValueError('isolated verifier must run as root and launch candidate as agent')
        write(out/'identity.json',identity);write(out/'manifest.json',manifest)
        if args.manifest_only:
            print(json.dumps(manifest['counts'],indent=2));return 0
        manifest=dict(manifest,episodes=selected)
        durations=(meta or {}).get('record',{}).get('durations',{})
        if args.mode=='record' and not diagnostic and args.truth.exists() and any(args.truth.iterdir()):
            raise ValueError('record requires a fresh --truth directory')
        private=(HERE,out)+((args.truth,) if args.truth.exists() else ()) \
            +((args.model_rpc,) if args.mode=='compare' else ())
        verify_integrity(baseline,private)
        (out/'episodes').mkdir(mode=0o2750)
        resume=args.resume_from.resolve() if args.resume_from else None
        if resume:
            previous=json.loads((resume/'identity.json').read_text())
            if previous.get('diagnostic'):raise ValueError('--resume-from refuses diagnostic runs')
            if previous!=identity:raise ValueError('resume requires identical sources, candidate, evaluator, mode and episodes')
        invalid=False;unavailable=False
        for wf in selected:
            directory=out/'episodes'/wf['id']
            if not present:
                points=failure_rows(wf,'The submission has no start.sh: nothing can be started.','candidate_missing_start')
                rows.extend(points);usages.append({});continue
            if unavailable:
                rows.extend(failure_rows(wf,'Run stopped: the model provider was unavailable.','infrastructure'));usages.append({});continue
            if resume:
                previous=resume/'episodes'/wf['id']
                if (previous/'status.json').is_file():
                    status=json.loads((previous/'status.json').read_text())
                    if not status.get('infrastructure_error') and not (previous/'worker-error.json').exists():
                        saved=[json.loads(x) for x in (previous/'results.jsonl').read_text().splitlines()]
                        validate_rows(saved,[wf]);shutil.copytree(previous,directory)
                        rows.extend(saved);usages.append(json.loads((directory/'usage.json').read_text()));resumed.append(wf['id'])
                        continue
            verify_integrity(baseline,private)
            state=args.state_root/WORKSPACE_NAME
            clear_workspace(state)
            request=['--episode',wf['id'],'--mode',args.mode,
                     '--start',str(args.start),'--state',str(state),
                     '--out',str(directory),'--truth',str(args.truth),'--spool',str(args.model_rpc)]
            command=[sys.executable,str(HERE/'worker.py'),'--request-stdin']
            limit=wall_limit(wf,durations);timed_out=stopped=False
            with (out/'episodes'/(wf['id']+'.log')).open('w') as stream:
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=stream,stderr=subprocess.STDOUT,
                                         start_new_session=True)
                process.stdin.write(json.dumps(request).encode());process.stdin.close()
                began=time.monotonic()
                while process.poll() is None:
                    if args.mode=='compare' and (args.model_rpc/'unavailable.json').exists():
                        unavailable=stopped=True
                    elif time.monotonic()-began-model_wait(directory)<=limit:
                        time.sleep(.25);continue
                    else:
                        timed_out=True
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=GRACE)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                    break
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            kill_candidate()
            runtime_logs=state/'runtime'/'logs'
            if runtime_logs.is_dir():
                shutil.copytree(runtime_logs,directory/'runtime',dirs_exist_ok=True)
            clear_workspace(state)
            verify_integrity(baseline,private)
            kept=json.loads((directory/'rows-progress.json').read_text()) if (directory/'rows-progress.json').exists() else []
            if stopped:
                points=failure_rows(wf,'Run stopped: the model provider was unavailable.','infrastructure',keep=kept)
            elif (directory/'results.jsonl').exists():
                points=[json.loads(x) for x in (directory/'results.jsonl').read_text().splitlines()]
            elif timed_out:
                points=failure_rows(wf,'The episode reached its wall-clock limit.','candidate_timeout',keep=kept)
            else:
                points=failure_rows(wf,'Worker stopped before results were written.','infrastructure',keep=kept)
            validate_rows(points,[wf])
            fault=stopped or (directory/'infrastructure-error.json').exists() or (directory/'worker-error.json').exists() \
                or (not (directory/'results.jsonl').exists() and not timed_out)
            invalid|=fault or unavailable
            usage=json.loads((directory/'usage.json').read_text()) if (directory/'usage.json').exists() else {}
            rows.extend(points);usages.append(usage)
            print(json.dumps({'episode':wf['id'],'passed':sum(r['passed'] for r in points),'assertions':len(points),
                              'seconds':round(time.monotonic()-began,3),'limit':limit,'timed_out':timed_out,
                              'infrastructure_error':fault}),flush=True)
        order={a['id']:i for i,a in enumerate(a for w in manifest['episodes'] for a in assertions(w))}
        rows.sort(key=lambda row:order[row['id']])
        summary=summarize(manifest,rows,usages,mode=args.mode,diagnostic=diagnostic,elapsed=time.monotonic()-started,
                          invalid=invalid,evaluator=evaluator,resumed=resumed)
        for row in rows:row['identity_sha256']=digest(identity)
        (out/'results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        if args.mode=='record' and summary['all_passed'] and not invalid and not diagnostic:
            durations={wf['id']:round(u.get('elapsed_seconds',0),3) for wf,u in zip(selected,usages)}
            freeze(args.truth,manifest,out,identity,summary,durations);summary['recorded']=True
        if summary['reward'] is not None:
            write(out/'reward.json',{'reward':summary['reward']});(out/'reward.txt').write_text(str(summary['reward'])+'\n')
        summary.update(identity_sha256=digest(identity),results_sha256=digest((out/'results.jsonl').read_bytes()))
        write(out/'summary.json',summary)
        write(out/'evidence.json',{'identity':identity,'resumed_episodes':resumed,
                                   'resume_source':str(resume) if resume else None,
                                   'files':{name:digest((out/name).read_bytes()) for name in ('summary.json','results.jsonl','reward.json','reward.txt') if (out/name).exists()}})
        print(json.dumps(summary,indent=2),flush=True)
        return 2 if invalid else 0 if summary['all_passed'] else 1
    except Exception as exc:
        write(out/'infrastructure-error.json',{'type':type(exc).__name__,'reason':str(exc),'traceback':traceback.format_exc()})
        print('INFRASTRUCTURE: '+str(exc),file=sys.stderr);return 2
    finally:
        if args.mode=='compare' and args.model_rpc.is_dir():write(args.model_rpc/'finished.json',{'finished':True})


if __name__=='__main__':
    raise SystemExit(main())

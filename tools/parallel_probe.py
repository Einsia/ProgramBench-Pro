"""Trusted offline metadata/aggregation helper, mounted only by parallel_compare.

Use the verifier image's own manifest, identity and scoring implementation.
No candidate is started in this container. The host coordinator is trusted.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, '/tests')
import run
import suite
from evaluation.contract import candidate_identity, digest, source_identity, tree, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inspect', 'aggregate', 'export'])
    parser.add_argument('--lane', type=int)
    parser.add_argument('--resume-export', action='store_true')
    args = parser.parse_args()
    if args.action == 'export':
        if args.lane is None or args.lane < 0:
            raise ValueError('export needs a nonnegative lane')
        root = Path('/result')
        source_root = Path('/previous') if args.resume_export else root
        source = source_root/'lanes'/str(args.lane)/'output/episodes'
        target = root/'resume-exports'/str(args.lane) if args.resume_export else root/'lanes'/str(args.lane)/'collected-episodes'
        target.parent.mkdir(exist_ok=True)
        owner = root.stat()
        if target.exists():
            raise ValueError('use a fresh evidence export destination')

        def copy(entry, destination):
            info = entry.lstat()
            if stat.S_ISDIR(info.st_mode):
                destination.mkdir(mode=0o750)
                for child in sorted(entry.iterdir()):
                    copy(child, destination/child.name)
            elif stat.S_ISREG(info.st_mode):
                fd = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as stream:
                    opened = os.fstat(stream.fileno())
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        raise ValueError('evidence changed during export')
                    data = stream.read()
                destination.write_bytes(data)
                destination.chmod(0o640)
                if digest(destination.read_bytes()) != digest(data):
                    raise ValueError('exported evidence differs')
            else:
                raise ValueError('non-regular evidence entry: '+str(entry))
            os.chown(destination, owner.st_uid, owner.st_gid)

        if source.exists():
            copy(source, target)
        else:
            target.mkdir(mode=0o750)
            os.chown(target, owner.st_uid, owner.st_gid)
        return
    manifest, _, meta = suite.load(Path('/truth'))
    if args.action == 'inspect':
        value = {'manifest': manifest, 'sources': source_identity(),
                 'candidate': candidate_identity('/app/solution'),
                 'truth': tree('/truth', ''), 'durations': meta['record']['durations']}
        write(Path('/result/metadata.json'), value)
        return
    root = Path('/result')
    plan = json.loads((root/'identity.json').read_text())
    if source_identity() != plan['sources'] or tree('/truth', '') != plan['truth']:
        raise ValueError('aggregation source/truth identity changed')
    if digest(manifest) != plan['manifest_sha256']:
        raise ValueError('aggregation manifest changed')
    selected = [w for w in manifest['episodes'] if w['id'] in plan['episodes']]
    if len(selected) != len(plan['episodes']):
        raise ValueError('unknown or duplicate selected episodes')
    collection = json.loads((root/'collection.json').read_text())
    rows, usages = [], []
    for wf in selected:
        directory = root/'episodes'/wf['id']
        if wf['id'] in collection['incomplete']:
            points = run.failure_rows(wf, 'Episode has no complete valid execution; resume required.', 'infrastructure')
            usage = {}
        else:
            points = [json.loads(s) for s in (directory/'results.jsonl').read_text().splitlines()]
            usage = json.loads((directory/'usage.json').read_text())
        run.validate_rows(points, [wf])
        rows.extend(points)
        usages.append(usage)
    selected_manifest = dict(manifest, episodes=selected)
    summary = run.summarize(selected_manifest, rows, usages, mode='compare',
                            diagnostic=plan['diagnostic'], elapsed=collection['elapsed_seconds'],
                            invalid=bool(collection['incomplete']), evaluator=plan['evaluator'],
                            resumed=collection['resumed'])
    summary.update(parallelism=collection['parallelism'],
                   selected_episodes=len(selected),
                   incomplete_episodes=collection['incomplete'],
                   identity_sha256=digest(plan))
    for row in rows:
        row['identity_sha256'] = digest(plan)
    (root/'results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
    summary['results_sha256'] = digest((root/'results.jsonl').read_bytes())
    write(root/'summary.json', summary)
    if summary['reward'] is not None:
        write(root/'reward.json', {'reward': summary['reward']})
        (root/'reward.txt').write_text(str(summary['reward'])+'\n')


if __name__ == '__main__':
    main()

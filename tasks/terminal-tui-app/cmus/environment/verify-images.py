#!/usr/bin/env python3
"""Check built image contents against live task files and the task's product-file policy."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def fingerprint(stream):
    value = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(chunk)
    return value.hexdigest()


def local_tree(root):
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            with path.open('rb') as stream:
                files[str(path.relative_to(root))] = fingerprint(stream)
    return files


def remote(image, script, *arguments):
    done = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--user', '0',
                           '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python3',
                           image, '-c', script, *arguments], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


TREE = '''
import hashlib,json,pathlib,sys
b=pathlib.Path(sys.argv[1])
print(json.dumps({str(p.relative_to(b)):hashlib.sha256(p.read_bytes()).hexdigest()
 for p in sorted(b.rglob('*')) if p.is_file()}))
'''


def shared_reference_paths(policy):
    """Validate optional, exact absolute reference-file exceptions and their reasons."""
    entries = policy.get('shared_reference_files', [])
    if not isinstance(entries, list):
        raise ValueError('shared_reference_files must be a list of path/reason objects')
    paths = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'reason'}:
            raise ValueError('shared_reference_files entries must contain exactly path and reason')
        path, reason = entry['path'], entry['reason']
        if not isinstance(path, str) or not path.startswith('/') or path == '/' \
                or any(character in path for character in '*?[]\x00') \
                or any(part in ('', '.', '..') for part in path.split('/')[1:]):
            raise ValueError('shared_reference_files requires exact absolute file paths: ' + repr(path))
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('shared_reference_files requires a nonempty reason: ' + path)
        if path in paths:
            raise ValueError('duplicate shared_reference_files path: ' + path)
        paths.add(path)
    return paths


def verify(root, verifier, reference, agent):
    policy_path = root / 'environment/image-policy.json'
    policy = json.loads(policy_path.read_text())
    forbidden = policy.get('reference_paths')
    if not isinstance(forbidden, list) or not forbidden or any(
        not isinstance(p, str) or not p.startswith('/') or 'REPLACE_' in p for p in forbidden
    ):
        raise ValueError(f'{policy_path}: list the actual installed product paths')
    exceptions = policy.get('shared_solution_files', [])
    if not isinstance(exceptions, list) or any(
        not isinstance(item, dict) or not item.get('file') or not item.get('reason') for item in exceptions
    ):
        raise ValueError('shared_solution_files must contain file/reason objects')
    allowed = {item['file'] for item in exceptions}
    shared_reference = shared_reference_paths(policy)
    runtime = local_tree(root / 'environment/runtime')
    agent_runtime = local_tree(root / 'environment/agent_runtime')
    tests = local_tree(root / 'tests')
    scoring = root.resolve().parents[2] / 'tools/scoring.py'
    with scoring.open('rb') as stream:
        tests['evaluation/scoring.py'] = fingerprint(stream)
    for image, directory, expected in (
        (verifier, '/tests', tests), (reference, '/tests', {}), (agent, '/tests', {}),
        (verifier, '/opt/blackbox/runtime', runtime), (reference, '/opt/blackbox/runtime', runtime),
        (agent, '/opt/blackbox/runtime', runtime),
        (agent, '/opt/blackbox-agent', agent_runtime),
        (reference, '/opt/blackbox-agent', {}), (verifier, '/opt/blackbox-agent', {}),
    ):
        actual = remote(image, TREE, directory)
        if actual != expected:
            changed = sorted(set(actual) ^ set(expected) | {
                key for key in set(actual) & set(expected) if actual[key] != expected[key]
            })
            raise ValueError(f'{image}:{directory} differs from the expected repository contents: {changed[:20]}')
    tools = remote(agent, TREE, '/usr/local/bin')
    for name, digest in (('blackbox', runtime['blackbox_client.py']), ('blackbox-health', agent_runtime['health.py'])):
        if tools.get(name) != digest:
            raise ValueError(f'{agent}:/usr/local/bin/{name} differs from the repository')
    for command, expected in (('claude', '2.1.296 (Claude Code)'), ('codex', 'codex-cli 0.162.1')):
        done = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint',
                               '/usr/local/bin/' + command, agent, '--version'], capture_output=True, text=True, check=True)
        if done.stdout.strip() != expected:
            raise ValueError(f'{command}: unexpected installed version: {done.stdout.strip()}')

    # Compare product-specific files from the reference, wherever the agent image
    # might place them. Generic system dependencies stay outside this list.
    reference_files = remote(reference, '''
import hashlib,json,pathlib,sys
files={};missing=[]
for name in json.loads(sys.argv[1]):
    root=pathlib.Path(name)
    if not root.exists(): missing.append(name);continue
    for path in ([root] if root.is_file() else root.rglob('*')):
        if path.is_file(): files[str(path)]={'size':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
print(json.dumps({'files':files,'missing':missing}))
''', json.dumps(forbidden))
    if reference_files['missing'] or not reference_files['files']:
        raise ValueError('reference_paths must name existing product files/directories: ' + str(reference_files['missing']))
    unknown = shared_reference - set(reference_files['files'])
    if unknown:
        raise ValueError('shared_reference_files must name known reference files, not directories: ' + str(sorted(unknown)))
    protected = {}
    sizes = set()
    for path, item in reference_files['files'].items():
        if path in shared_reference:
            continue
        sizes.add(item['size'])
        protected.setdefault(item['sha256'], []).append(path)
    solution = root / 'solution'
    known = set()
    for path in sorted(solution.rglob('*')):
        if not path.is_file() or '.git' in path.relative_to(solution).parts:
            continue
        relative = str(path.relative_to(solution))
        known.add(relative)
        if relative in allowed or path.stat().st_size == 0:
            continue
        with path.open('rb') as stream:
            protected.setdefault(fingerprint(stream), []).append('solution/' + relative)
        sizes.add(path.stat().st_size)
    if allowed - known:
        raise ValueError('unknown shared_solution_files entries: ' + str(sorted(allowed - known)))

    # Inspect the merged filesystem without running the application or unpacking
    # the image. The stream and every temporary file stay under external TMPDIR.
    made = subprocess.run(['docker', 'create', '--entrypoint', '/bin/true', agent],
                          capture_output=True, text=True, check=True)
    container = made.stdout.strip()
    failures = []
    try:
        with tempfile.TemporaryDirectory(prefix='image-check-') as temporary:
            archive = Path(temporary) / 'filesystem.tar'
            subprocess.run(['docker', 'export', '--output', str(archive), container], check=True)
            with tarfile.open(archive, mode='r|') as filesystem:
                for member in filesystem:
                    name = '/' + member.name.removeprefix('./').lstrip('/')
                    if any(name == entry or name.startswith(entry.rstrip('/') + '/') for entry in forbidden):
                        failures.append(name + ': reference product path')
                    if name.startswith('/app/solution/'):
                        failures.append(name + ': nonempty solution directory')
                    if member.isreg() and member.size and member.size in sizes:
                        with filesystem.extractfile(member) as stream:
                            matches = protected.get(fingerprint(stream))
                        if matches:
                            failures.append(name + ': matches ' + ', '.join(matches[:3]))
    finally:
        subprocess.run(['docker', 'rm', container], check=True, stdout=subprocess.DEVNULL)
    if failures:
        raise ValueError('agent image contains restricted product files:\n' + '\n'.join(failures[:50]))
    print('image verification passed: tests, runtime, tool versions and product-file separation')


def main():
    if len(sys.argv) != 5:
        raise SystemExit('usage: verify-images.py TASK_ROOT VERIFIER_IMAGE REFERENCE_IMAGE AGENT_IMAGE')
    if not os.environ.get('TMPDIR'):
        raise SystemExit('verify-images.py: set TMPDIR to an external directory')
    try:
        verify(Path(sys.argv[1]), *sys.argv[2:])
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit('image verification failed: ' + str(exc)) from exc


if __name__ == '__main__':
    main()

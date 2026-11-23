#!/usr/bin/env python3
"""Fetch and verify the downloads listed in solution/SOURCE.json using the standard library."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def fetch(task_root):
    solution = task_root.resolve() / 'solution'
    source = solution / 'SOURCE.json'
    metadata = json.loads(source.read_text(encoding='utf-8'))
    downloads = metadata.get('downloads')
    if not isinstance(downloads, list):
        raise ValueError(f'{source}: downloads must be a list')
    seen = set()
    for entry in downloads:
        if not isinstance(entry, dict):
            raise ValueError(f'{source}: each download must be an object')
        name, url, expected = (entry.get(key) for key in ('file', 'url', 'sha256'))
        if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError(f'{source}: invalid download filename: {name!r}')
        if name in seen:
            raise ValueError(f'{source}: repeated download filename: {name}')
        seen.add(name)
        if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme not in ('https', 'http'):
            raise ValueError(f'{name}: url must use https or http')
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
            raise ValueError(f'{name}: sha256 must contain 64 hexadecimal characters')
        expected = expected.lower()
        destination = solution / name
        if not destination.resolve().is_relative_to(solution) or any(
            p.is_symlink() for p in (destination, *destination.parents) if p.is_relative_to(solution)
        ):
            raise ValueError(f'{name}: download destination must stay inside solution without links')
        if destination.exists() and not destination.is_file():
            raise ValueError(f'{name}: download destination is not a regular file')
        if destination.is_file() and sha256(destination) == expected:
            print(f'verified: {name}')
            continue
        print(f'downloading: {name}', flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'program-bench-fetch/1.0.0'})
        with tempfile.TemporaryDirectory(prefix='source-download-') as temporary:
            pending = Path(temporary) / 'download'
            try:
                with urllib.request.urlopen(request, timeout=120) as response, pending.open('wb') as output:
                    shutil.copyfileobj(response, output)
            except (OSError, urllib.error.URLError) as exc:
                raise RuntimeError(f'{name}: download failed from {url}: {exc}') from exc
            actual = sha256(pending)
            if actual != expected:
                raise ValueError(f'{name}: sha256 mismatch: expected {expected}, got {actual}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pending), str(destination))
            destination.chmod(0o644)
        print(f'verified: {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        fetch(args.task_root)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'fetch: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

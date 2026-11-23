"""Minimal public setup for the GUI episodes that view packages and LFS objects.

Only the uploads those pages show, through the product's public protocols (the
generic and npm package APIs, the OCI registry and the LFS batch API, following
the actions the server advertises); never a replay of scored protocol cases.
Any success status is accepted.
"""
import hashlib
import json
import urllib.parse

from api_packages_lfs import LFS_HEADERS, OCI_LAYER, npm_payload
from harness import b64

GENERIC_FILES = (('notes.txt', b'package notes\n'), ('payload.bin', bytes(range(64))),
                 ('file with spaces.txt', '包文件 café'.encode()))
LFS_OBJECTS = (b'', 'LFS object café\n'.encode(), bytes(range(256)) * 3)


def succeeded(response, what):
    assert 200 <= response.status_code < 300, f'setup {what}: status {response.status_code}'


def generic(c):
    for version in ('1.0.0', '2.0.0-rc.1'):
        for filename, data in GENERIC_FILES:
            path = '/api/packages/alice/generic/pbp-generic/' + version + '/' + urllib.parse.quote(filename, safe='')
            r, _ = c.request('PUT', path, 'alice', data=data)
            succeeded(r, 'generic package upload')


def npm(c):
    payload, _, _ = npm_payload('pbp-npm', '1.0.0')
    r, _ = c.request('PUT', '/api/packages/alice/npm/pbp-npm', 'alice', body=payload)
    succeeded(r, 'npm publish')


def container(c):
    r, p = c.request('GET', '/v2/token', 'alice')
    succeeded(r, 'registry token')
    assert isinstance(p, dict) and isinstance(p.get('token'), str), 'registry token is missing'
    bearer = {'Authorization': 'Bearer ' + p['token']}
    repo = '/v2/alice/pbp-image'
    config = json.dumps({'architecture': 'amd64', 'os': 'linux', 'rootfs': {'type': 'layers', 'diff_ids': []}},
                        sort_keys=True, separators=(',', ':')).encode()
    layer = OCI_LAYER
    for data in (config, layer):
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        r, _ = c.request('POST', repo + '/blobs/uploads', None, headers=bearer)
        succeeded(r, 'registry upload start')
        location = c.local_resource_path(r.headers.get('Location'))
        location += ('&' if '?' in location else '?') + 'digest=' + urllib.parse.quote(digest, safe=':')
        r, _ = c.request('PUT', location, None, headers={**bearer, 'Content-Type': 'application/octet-stream'},
                         data=data)
        succeeded(r, 'registry blob upload')
    manifest = {'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.manifest.v1+json',
                'config': {'mediaType': 'application/vnd.oci.image.config.v1+json',
                           'digest': 'sha256:' + hashlib.sha256(config).hexdigest(), 'size': len(config)},
                'layers': [{'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip',
                            'digest': 'sha256:' + hashlib.sha256(layer).hexdigest(), 'size': len(layer)}]}
    raw = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    r, _ = c.request('PUT', repo + '/manifests/latest', None,
                     headers={**bearer, 'Content-Type': 'application/vnd.oci.image.manifest.v1+json'}, data=raw)
    succeeded(r, 'registry manifest')


def lfs_objects(c):
    """alice/pbp-lfs-public with three stored LFS objects and a committed pointer, uploaded as a Git LFS client
    would: batch, then the advertised upload and verify actions."""
    r, _ = c.request('POST', 'user/repos', 'alice', body={'name': 'pbp-lfs-public', 'auto_init': True})
    succeeded(r, 'repository')
    lp = '/alice/pbp-lfs-public.git/info/lfs'
    for data in LFS_OBJECTS:
        obj = {'oid': hashlib.sha256(data).hexdigest(), 'size': len(data)}
        r, plan = c.request('POST', lp + '/objects/batch', 'alice', headers=LFS_HEADERS,
                            body={'operation': 'upload', 'transfers': ['basic'], 'objects': [obj]})
        succeeded(r, 'LFS batch')
        assert isinstance(plan, dict) and isinstance(plan.get('objects'), list) and plan['objects'], 'LFS batch plan'
        actions = plan['objects'][0].get('actions') or {}
        if 'upload' in actions:
            action = actions['upload']
            headers = {k: v for k, v in (action.get('header') or {}).items() if k.lower() != 'transfer-encoding'}
            headers.setdefault('Content-Type', 'application/octet-stream')
            r, _ = c.request('PUT', c.local_resource_path(action['href']), None, headers=headers, data=data)
            succeeded(r, 'LFS upload')
        if 'verify' in actions:
            action = actions['verify']
            headers = {**LFS_HEADERS, **(action.get('header') or {})}
            r, _ = c.request('POST', c.local_resource_path(action['href']), None, headers=headers, body=obj)
            succeeded(r, 'LFS verify')
    data = LFS_OBJECTS[-1]
    pointer = ('version https://git-lfs.github.com/spec/v1\noid sha256:' + hashlib.sha256(data).hexdigest()
               + '\nsize ' + str(len(data)) + '\n')
    r, _ = c.request('POST', 'repos/alice/pbp-lfs-public/contents/large.bin', 'alice',
                     body={'content': b64(pointer), 'message': 'Add LFS pointer'})
    succeeded(r, 'LFS pointer commit')


PREPARE = {'generic-packages': generic, 'npm-package': npm, 'container-image': container, 'lfs-objects': lfs_objects}


def prepare(c, name):
    PREPARE[name](c)

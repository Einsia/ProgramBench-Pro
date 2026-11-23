#!/usr/bin/env python3
"""Initialize the public Miniflux accounts and start one configured instance.

The official executable is unchanged; state belongs to this instance.
"""
import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

PG_BIN = Path('/usr/lib/postgresql/16/bin')
CREDS = {'alice': 'Alice-Local-2026!', 'bob': 'Bob-Local-2026!', 'carol': 'Carol-Local-2026!'}
ADMIN = 'alice'
# Deployment configuration of the reference installation (the About page lists it to administrators).
SETTINGS = {
    'RUN_MIGRATIONS': '1',
    'POLLING_FREQUENCY': '1440',
    'INTEGRATION_ALLOW_PRIVATE_NETWORKS': '1',
    'MEDIA_PROXY_PRIVATE_KEY': 'miniflux-reference-media-proxy',
    'LOG_LEVEL': 'info',
}
# Miniflux reads every environment variable named like one of its options; PORT would replace LISTEN_ADDR.
DROPPED = ('PORT', 'HOST', 'LISTEN_ADDR', 'DATABASE_URL', 'CREATE_ADMIN', 'ADMIN_USERNAME', 'ADMIN_PASSWORD')


def socket_directory(data):
    """The PostgreSQL socket lives in DATA_DIR unless that path is too long for a Unix socket name."""
    preferred = data / 'run'
    if len(str(preferred / '.s.PGSQL.5432')) <= 100:
        return preferred
    return Path(os.environ['TMPDIR']) / ('pg-' + hashlib.sha256(str(data).encode()).hexdigest()[:16])


def wait_for(predicate, seconds, what):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise SystemExit('launch: ' + what + ' did not become ready')


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__('localhost', timeout=10)
        self.path_name = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect(self.path_name)


def call(path, method, route, body=None, auth=None):
    connection = UnixHTTP(str(path))
    headers = {'Content-Type': 'application/json'}
    if auth:
        headers['Authorization'] = 'Basic ' + base64.b64encode(':'.join(auth).encode()).decode()
    try:
        connection.request(method, route, json.dumps(body).encode() if body is not None else None, headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def stop(proc, signum, seconds):
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.send_signal(signum)
        proc.wait(seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(5)
    except ProcessLookupError:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', required=True)
    parser.add_argument('--data', default=os.environ.get('DATA_DIR'))
    parser.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '3000')))
    args = parser.parse_args()
    if not args.data:
        parser.error('--data or DATA_DIR is required')
    data = Path(args.data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    cluster, ready = data / 'postgres', data / 'baseline.ready'
    sockets = socket_directory(data)
    sockets.mkdir(mode=0o700, parents=True, exist_ok=True)
    sockets.chmod(0o700)
    first = not ready.exists()
    if first:
        shutil.rmtree(cluster, ignore_errors=True)
        subprocess.run([str(PG_BIN / 'initdb'), '-D', str(cluster), '-U', 'miniflux', '--auth=trust', '-E', 'UTF8',
                        '--locale=C.UTF-8', '--no-instructions'], check=True, stdout=subprocess.DEVNULL)

    children = {}

    def shutdown(signum=None, frame=None):
        stop(children.get('miniflux'), signal.SIGTERM, 8)
        stop(children.get('bootstrap'), signal.SIGTERM, 8)
        stop(children.get('postgres'), signal.SIGINT, 8)
        if signum is not None:
            sys.exit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, shutdown)

    children['postgres'] = subprocess.Popen(
        [str(PG_BIN / 'postgres'), '-D', str(cluster), '-k', str(sockets), '-c', 'listen_addresses=',
         '-c', 'unix_socket_permissions=0700', '-c', 'fsync=off', '-c', 'synchronous_commit=off',
         '-c', 'full_page_writes=off', '-c', 'max_connections=40', '-c', 'shared_buffers=32MB',
         '-c', 'log_min_messages=warning'], stdin=subprocess.DEVNULL)
    wait_for(lambda: subprocess.run([str(PG_BIN / 'pg_isready'), '-q', '-h', str(sockets), '-U', 'miniflux',
                                     '-d', 'postgres']).returncode == 0, 60, 'PostgreSQL')
    env = {k: v for k, v in os.environ.items() if k not in DROPPED}
    env.update(SETTINGS, DATABASE_URL=f'user=miniflux dbname=miniflux host={sockets} sslmode=disable',
               BASE_URL=f'http://127.0.0.1:{args.port}')
    if first:
        subprocess.run([str(PG_BIN / 'createdb'), '-h', str(sockets), '-U', 'miniflux', 'miniflux'], check=True)
        # The baseline accounts: alice (administrator) from the first start, bob and carol through the public
        # API of a bootstrap instance that listens only on a private Unix socket.
        listener = sockets / 'bootstrap.sock'
        children['bootstrap'] = subprocess.Popen(
            [args.binary], env={**env, 'LISTEN_ADDR': str(listener), 'CREATE_ADMIN': '1', 'ADMIN_USERNAME': ADMIN,
                                'ADMIN_PASSWORD': CREDS[ADMIN]}, stdin=subprocess.DEVNULL)

        def answering():
            if children['bootstrap'].poll() is not None:
                raise SystemExit('launch: the bootstrap instance exited')
            try:
                return listener.exists() and call(listener, 'GET', '/healthcheck')[0] == 200
            except OSError:
                return False
        wait_for(answering, 60, 'the bootstrap instance')
        for user in CREDS:
            if user != ADMIN:
                status, body = call(listener, 'POST', '/v1/users', {'username': user, 'password': CREDS[user]},
                                    auth=(ADMIN, CREDS[ADMIN]))
                if status != 201:
                    raise SystemExit(f'launch: creating {user} returned {status}: {body[:200]!r}')
        stop(children.pop('bootstrap'), signal.SIGTERM, 8)
        listener.unlink(missing_ok=True)
        ready.write_text('three accounts: alice (administrator), bob, carol\n')
    children['miniflux'] = subprocess.Popen([args.binary], env={**env, 'LISTEN_ADDR': f'{args.host}:{args.port}'},
                                            stdin=subprocess.DEVNULL)
    code = 1
    while True:
        if children['miniflux'].poll() is not None:
            code = children['miniflux'].returncode
            break
        if children['postgres'].poll() is not None:
            break
        time.sleep(0.2)
    shutdown()
    sys.exit(code)


if __name__ == '__main__':
    main()

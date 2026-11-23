"""Configure the unmodified release and initialize its database through its normal web entrypoint."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default='3000')
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    root, data = Path(args.root).resolve(), Path(args.data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    config = (root / 'grocy/config-dist.php').read_text()
    config = config.replace("Setting('STOCK_BARCODE_LOOKUP_PLUGIN', 'OpenFoodFactsBarcodeLookupPlugin');",
                            "Setting('STOCK_BARCODE_LOOKUP_PLUGIN', 'DemoBarcodeLookupPlugin');")
    (data / 'config.php').write_text(config)
    env = dict(os.environ, GROCY_DATAPATH=str(data), TZ='UTC',
               LD_LIBRARY_PATH=str(root / 'php/lib'), PHP_CLI_SERVER_WORKERS='4')
    executable = str(root / 'php/bin/php')
    common = [executable, '-d', 'date.timezone=UTC', '-d', 'display_errors=0',
              '-d', 'log_errors=1', '-d', 'expose_php=0']
    # Grocy performs its own migrations on a page request. Warm the normal
    # entrypoint before offering the main listener, including its redirects.
    if not (data / 'baseline.ready').exists():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cmd = common + ['-S', f'127.0.0.1:{port}', '-t', str(root / 'grocy/public'), str(root / 'router.php')]
        warm_env = dict(env)
        warm_env.pop('PHP_CLI_SERVER_WORKERS', None)
        warm = subprocess.Popen(cmd, env=warm_env)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if warm.poll() is not None:
                    raise RuntimeError('Grocy initialization server exited')
                try:
                    with opener.open(f'http://127.0.0.1:{port}/', timeout=5) as response:
                        if response.status == 200:
                            response.read()
                            break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.1)
            else:
                raise RuntimeError('Grocy initialization timed out')
        finally:
            warm.terminate()
            warm.wait(timeout=5)
        (data / 'baseline.ready').write_text('Grocy 4.7.1\n')
    if args.start:
        command = common + ['-S', f'{args.host}:{args.port}', '-t', str(root / 'grocy/public'), str(root / 'router.php')]
        os.execve(executable, command, env)


if __name__ == '__main__':
    main()

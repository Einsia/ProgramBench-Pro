"""Prepare root-owned broker directories before starting the reference runtime."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blackbox_runtime import open_directory


def main():
    if os.geteuid() != 0:
        raise SystemExit('the reference broker must run as root')
    if len(sys.argv) < 2:
        raise SystemExit('a reference runtime command is required')
    # /reference must be traversable to reach the product-owned instance data.
    # Private logs/work and the root-only RPC socket stay inaccessible to it.
    for path, mode in (('/reference', 0o711), ('/reference/logs', 0o700),
                       ('/reference/work', 0o700), ('/blackbox', 0o755),
                       ('/tmp/reference-runtime', 0o700)):
        with open_directory(path, create=True) as fd:
            os.fchown(fd, 0, 0)
            os.fchmod(fd, mode)
    os.environ['TMPDIR'] = '/tmp/reference-runtime'
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()

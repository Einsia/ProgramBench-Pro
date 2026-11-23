"""Check the installed read-only reference can initialize its writable instance."""
import json
from pathlib import Path
import sys

sys.path.insert(0, '/opt/blackbox/runtime')
import blackbox_runtime as runtime

config = runtime.options(ready_timeout=105).parse_args([
    '--solution', '/app/solution', '--state', '/check/instance', '--log-dir', '/check/logs',
    '--work', '/check/work', '--user', 'agent',
])
product = runtime.Product(config, log=runtime.BoundedLog(config.log_dir))
passed = False
try:
    passed = product.start(fresh=True) and runtime.wait_http(product)
    print(json.dumps({'reference_startup': product.status()}), flush=True)
finally:
    product.stop()
if not passed:
    raise SystemExit('Reference startup failed; inspect the external startup-check logs.')
with runtime.open_directory('/check') as directory:
    for name, _info in runtime.list_directory(directory):
        runtime.remove_entry(directory, name)

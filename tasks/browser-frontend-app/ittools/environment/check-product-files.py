#!/usr/bin/env python3
"""Check product-specific artifact names in the development image."""
import subprocess
import sys

SCAN = 'import os\nfound=[]\nfor d,ds,fs in os.walk("/"):\n    ds[:]=[x for x in ds if os.path.join(d,x) not in ("/proc","/sys","/dev")]\n    found+=[os.path.join(d,f) for f in fs if f.startswith("it-tools") or f in ("index-f8ba620c.js","mac-address-lookup-5cb65627.js","text-diff-f40b7f4a.js")]\nprint("\\n".join(found))'

result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--user', '0',
                         '--entrypoint', 'python3', sys.argv[1], '-B', '-c', SCAN],
                        capture_output=True, text=True, check=True)
paths = [line for line in result.stdout.splitlines() if line.strip()]
if paths:
    raise SystemExit('development image contains product artifacts: ' + ', '.join(paths[:20]))
print('product-specific artifact names: absent')

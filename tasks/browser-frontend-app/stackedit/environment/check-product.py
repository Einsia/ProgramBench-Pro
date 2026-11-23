#!/usr/bin/env python3
"""Check product filenames and immutable reference installation permissions."""
import json
import subprocess
import sys

agent, reference = sys.argv[1:]
script = ('import os\nfound=[]\nfor d,ds,fs in os.walk("/"):\n    ds[:]=[x for x in ds if os.path.join(d,x) not in ("/proc","/sys","/dev")]\n'
          '    found+=[os.path.join(d,f) for f in fs if f.startswith("stackedit") or f in ("docker-build-layer.tar.gz", "stackedit-db")]\n'
          'print("\\n".join(found))')

leaked = subprocess.run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python3',agent,'-B','-c',script],capture_output=True,text=True,check=True).stdout.split()
if leaked:
    raise SystemExit('Unexpected product files in application workspace image: '+repr(leaked[:10]))
check = """
import json,os,pathlib,stat
root=pathlib.Path('/app/solution')
exceptions=EXCEPTIONS
bad=[]
for path in [root,*root.rglob('*')]:
    info=path.lstat()
    required=0o755 if str(path) in exceptions else 0o711 if path.is_dir() else 0o555 if info.st_mode&0o111 else 0o444
    if info.st_uid or info.st_gid or stat.S_IMODE(info.st_mode)!=required or path.is_symlink():bad.append(str(path))
if pathlib.Path('/solution').exists():bad.append('/solution: installation staging remains')
print(json.dumps(bad))
""".replace('EXCEPTIONS','[]')
bad=json.loads(subprocess.run(['docker','run','--rm','--network','none','--user','0','--entrypoint','python3',reference,'-B','-c',check],capture_output=True,text=True,check=True).stdout)
if bad:raise SystemExit('Reference installation permissions differ: '+repr(bad[:10]))
print('product filenames and reference installation permissions verified')

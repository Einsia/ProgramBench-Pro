"""Launch the unmodified upstream release with fixed deployment configuration and OS restrictions."""
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parent
env=dict(os.environ,CMUS_LIB_DIR=str(root/'cmus/lib/cmus'),CMUS_DATA_DIR=str(root/'cmus/share/cmus'))
binary=str(root/'cmus/bin/cmus')
if len(sys.argv)>1:
    if len(sys.argv)!=2 or sys.argv[1] not in ('--help','--version','--plugins'):
        raise SystemExit('Unsupported terminating option')
    os.execve(binary,[binary,sys.argv[1]],env)
data=Path(env['DATA_DIR']);work=data/'workspace';conf=data/'config/cmus'
for path in (work,conf):
    path.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise SystemExit('Invalid instance directory')
# This deployment's fixed startup configuration is not user-supplied code.
fd=os.open(conf/'rc',os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:f.write('set output_plugin=pulse\nset softvol=true\n')
# Native autosave only contains set/bind/fset/factivate. Reject replacement scripts before startup.
path=conf/'autosave'
if path.exists() or path.is_symlink():
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as f:
        text=f.read(2_000_001)
    if len(text)>2_000_000 or any(line.strip() and line.split(None,1)[0] not in ('set','bind','fset','factivate') for line in text.splitlines()):
        raise SystemExit('Invalid saved configuration')
# Resume browser paths must stay in the public workspace even during early startup.
resume=conf/'resume'
if resume.is_file():
    lines=resume.read_text().splitlines()
    for i,line in enumerate(lines):
        if line.startswith('browser-dir '):
            candidate=Path(line[12:])
            if not candidate.is_absolute() or not candidate.resolve().is_relative_to(work.resolve()):lines[i]='browser-dir '+str(work)
    fd=os.open(resume,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW)
    with os.fdopen(fd,'w') as f:f.write('\n'.join(lines)+'\n')
env.update(XDG_CONFIG_HOME=str(data/'config'),LD_PRELOAD=str(root/'denyexec.so'),CMUS_PUBLIC_THEMES=str(root/'cmus/share/cmus'))
os.chdir(work)
os.execve(binary,[binary,'--listen',env['CMUS_SOCKET']],env)

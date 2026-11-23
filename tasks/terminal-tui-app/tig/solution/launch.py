#!/usr/bin/env python3
"""Launch the unmodified upstream binary with the instance contract."""
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
os.chdir(Path(os.environ['DATA_DIR'])/'repository')
args=json.loads(os.environ.get('TIG_ARGS','[]'))
if os.environ.get('TIG_PAGER_FILE'):
    fd=os.open(os.environ['TIG_PAGER_FILE'],os.O_RDONLY)
    os.dup2(fd,0)
    os.close(fd)
env=dict(os.environ,LD_PRELOAD=str(HERE/'confine.so'))
os.execve(str(HERE/'tig'),['tig',*args],env)

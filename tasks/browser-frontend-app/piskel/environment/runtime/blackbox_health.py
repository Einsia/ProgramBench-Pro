#!/usr/bin/env python3
"""Container health check: the runtime answers and reports its product ready (op status)."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
for location in (here / 'blackbox', here / 'blackbox_client.py', Path('/usr/local/bin/blackbox')):
    if location.is_file():
        spec = importlib.util.spec_from_loader('blackbox_client', SourceFileLoader('blackbox_client', str(location)))
        client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client)
        break
else:
    sys.exit(1)
try:
    result = client.call({'op': 'status'}, timeout=10)
except Exception:
    sys.exit(1)
sys.exit(0 if isinstance(result, dict) and result.get('ready') is True else 1)

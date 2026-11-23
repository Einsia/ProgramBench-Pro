"""Driving and observation helpers over the task black-box runtime (terminal surface).

Everything reaches the product through the runtime's channels: GUI operations (key/keys/type/wait) and the
screen observation for the interactive terminal; the home-directory inspector (calcurse's data and configuration
files), the command-line channel and file placement for setup and backend checks; and the lifecycle operations
(status/reset/restart). No product internals are touched.
"""
from __future__ import annotations

import time

from evaluation.broker import BrokerError


class Session:
    """Thin convenience wrapper over ctx.broker for recipes, setup and checks."""

    def __init__(self, broker):
        self.broker = broker

    def call(self, request, **kw):
        return self.broker.call(request, **kw)

    # -- GUI operations ------------------------------------------------------------------------------------
    def key(self, name):
        return self.broker.call({'op': 'key', 'key': name})

    def keys(self, names):
        return self.broker.call({'op': 'keys', 'keys': list(names)})

    def type(self, text):
        return self.broker.call({'op': 'type', 'text': text})

    def wait(self, seconds=0.5):
        return self.broker.call({'op': 'wait', 'seconds': seconds})

    def screen(self):
        return self.broker.call({'op': 'screen'})

    # -- lifecycle -----------------------------------------------------------------------------------------
    def status(self):
        return self.broker.call({'op': 'status'})

    def reset(self):
        return self.broker.call({'op': 'reset'})

    def restart(self):
        return self.broker.call({'op': 'restart'})

    def place(self, files):
        return self.broker.call({'op': 'place', 'files': files})

    # -- non-GUI read channels ------------------------------------------------------------------------------
    def files(self, action='list', path='~'):
        return self.broker.call({'op': 'files', 'action': action, 'path': path})

    def read(self, path):
        """The text of a file below the home directory, or None when it does not exist."""
        try:
            return self.files('read', path)['text']
        except BrokerError as exc:
            if 'no such' in exc.detail:
                return None
            raise

    def cli(self, args):
        return self.broker.call({'op': 'cli', 'args': list(args)}, timeout=90)

    def ready(self, timeout=40):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.status().get('ready'):
                    return True
            except BrokerError:
                pass
            time.sleep(0.3)
        return False

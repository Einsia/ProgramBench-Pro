"""Pinned-standard GUI driving of the reviewed goals, through the black-box runtime.

Recipes drive only the installed standard answer during record, with the same
runtime operations the evaluator and the model use (open, click, type, press,
the accessible menu, and typed file-dialog paths). Their routes belong to the
pinned standard only; they are never a candidate requirement.
"""
from __future__ import annotations

import json
import time

import drive


def begin(ctx, checkpoint):
    settle(ctx)


def execute(ctx, checkpoint):
    drive.run(ctx, checkpoint['recipe'])
    if not checkpoint.get('modal_end'):
        settle(ctx)


def settle(ctx, timeout=8.0, quiet=1.0):
    """Wait until the accessibility observation stops changing before evidence is captured."""
    deadline = time.monotonic() + timeout
    last, since = None, time.monotonic()
    while time.monotonic() < deadline:
        try:
            observation = ctx.broker.call({'op': 'observe'})
        except Exception:
            time.sleep(0.25)
            continue
        key = json.dumps(observation, sort_keys=True)
        now = time.monotonic()
        if key != last:
            last, since = key, now
        elif now - since >= quiet:
            return
        time.sleep(0.25)

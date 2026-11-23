"""Deterministic reference recipes for GUI checkpoints: drive the pinned standard answer through the
same runtime GUI operations the evaluator and the model use. Never a candidate requirement."""
import checks
from harness import Session


def execute(ctx, checkpoint):
    checks.drive(Session(ctx.broker), checkpoint.get('steps', []))

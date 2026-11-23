"""Reference GUI routes through the same public runtime as exploration and evaluation."""


def execute(ctx, checkpoint):
    from hooks import run_steps
    run_steps(ctx, checkpoint['recipe'])
    ctx.broker.call({'op': 'wait', 'seconds': .3})

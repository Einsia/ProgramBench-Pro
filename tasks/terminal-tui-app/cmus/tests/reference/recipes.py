from checks import drive
def execute(ctx, checkpoint): drive(ctx.state["session"],checkpoint.get("steps",[]))

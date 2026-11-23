from checks import drive
def execute(ctx,checkpoint):drive(ctx,checkpoint.get('steps',[]))

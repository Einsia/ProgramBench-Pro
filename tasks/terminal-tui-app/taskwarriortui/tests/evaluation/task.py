"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'taskwarriortui'
VERSION = '1.0.0'
REFERENCE = 'taskwarrior-tui 0.27.0 (Taskwarrior 3.3.0)'
SURFACE = 'terminal'
# The task's black-box runtime (environment/runtime/), installed read-only in the reference and verifier
# images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 30
# Evaluator surface: the runtime's terminal operations; observation is its screen snapshot (no image).
SESSION = {}
START = {'op': 'screen'}
OBSERVE = ('screen', None)
GUI_OPS = ('key', 'keys', 'type', 'wait')
GUIDE_NOTES = '''Each observation is the terminal as a user sees it: "screen" lists the rows as "NN|text"
(NN is the zero-based row number, not part of the screen), "styles" lists the runs of text whose colour or
attributes differ from the most common style (for example bold, reverse video or colours), and "process" says
whether the application is still running or has exited with a status. key presses one key or chord (for example
Enter, Escape, Down, Control+U), keys presses several in order, type sends literal text (never Enter or other
control keys), and wait waits for asynchronous output. Every operation returns once the screen has settled.
'''

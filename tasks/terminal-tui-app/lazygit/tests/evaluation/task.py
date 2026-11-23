"""Task identity and black-box runtime configuration for the shared evaluation package ."""
TASK = 'lazygit'
VERSION = '1.0.0'
REFERENCE = 'lazygit 0.66.2'
SURFACE = 'terminal'
# The task's black-box runtime (environment/runtime/), installed read-only in the reference and verifier
# images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 30
# Evaluator surface: the runtime's terminal operations; observation is its screen snapshot (no image).
SESSION = {}
START = {'op': 'screen'}
OBSERVE = ('screen', None)
GUI_OPS = ('key', 'keys', 'type', 'wait')
GUIDE_NOTES = '''Each observation is the terminal as a user sees it: "screen" lists the rows as "NN|text"
(NN is the zero-based row number, not part of the screen), "styles" lists the runs of text whose colour or
attributes differ from the most common style (for example the selected line and the focused panel), and
"process" says whether the application is still running or has exited with a status. key presses one key or
chord (for example Enter, Escape, Down, Control+O, Space), keys presses several in order, type sends literal
text (never Enter or other control keys), and wait waits for asynchronous output. Input sent before the
screen settles may be dropped, so read the settled screen before sending the next keys. Ages that follow the
real clock are shown as placeholders. The application's key map is in the help response under
reference_controls.
'''

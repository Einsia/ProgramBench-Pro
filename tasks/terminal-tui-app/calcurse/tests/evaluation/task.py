"""Task identity and black-box runtime configuration for the shared evaluation package ."""
TASK = 'calcurse'
VERSION = '1.0.0'
REFERENCE = 'calcurse 4.8.2'
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
(NN is the zero-based row number, not part of the screen), "styles" lists the runs of text drawn with colours
or attributes (bold, reverse, underline, foreground and background colours), which is how the selected panel,
day and item are marked, and "process" says whether the application is still running or has exited with a
status. key presses one key or chord (for example Enter, Escape, Tab, Down, Control+A, Shift+Tab), keys presses
several in order, type sends literal text (never Enter or other control keys), and wait waits for asynchronous
output. Input sent before the screen settles may be dropped, so read the settled screen before sending the next
keys. Prompts and messages appear at the bottom of the screen; the application's main key bindings are listed
there too.
'''

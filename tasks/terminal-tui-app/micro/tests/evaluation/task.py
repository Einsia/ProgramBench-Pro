"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'micro'
VERSION = '1.0.0'
REFERENCE = 'micro 2.0.15'
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
GUI_OPS = ('key', 'keys', 'type', 'paste', 'wait')
GUIDE_NOTES = '''Each observation is the terminal as a user sees it: "screen" lists the rows as "NN|text"
(NN is the zero-based row number, not part of the screen), "styles" lists the runs of text whose colour or
attributes differ from the most common style (selected text, search matches, the cursor line, the status line
and the active tab are shown this way), "cursor" is the terminal cursor and "process" says whether the
application is still running or has exited with a status. key presses one key or chord (for example Enter,
Escape, Control+S, Shift+Right, Alt+Shift+Down), keys presses several in order, type sends literal printable
text, paste sends text as the terminal's own paste (it may contain newlines), and wait waits for asynchronous
output. Read the settled screen before sending the next keys.
'''

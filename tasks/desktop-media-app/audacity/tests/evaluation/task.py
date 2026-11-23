"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'audacity'
VERSION = '1.0.0'
REFERENCE = 'Audacity 2.4.2'
SURFACE = 'desktop'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
# Seconds the application has to show an accessible window after a start (the runtime's readiness rule).
READY_SECONDS = 30
# Evaluator surface: the runtime's desktop input operations; one desktop, no sessions.
SESSION = {}
START = {'op': 'wait', 'seconds': 0.5}
OBSERVE = ('observe', 'screenshot')
GUI_OPS = ('click', 'activate', 'fill', 'type', 'press', 'check', 'move', 'drag', 'scroll', 'zoom', 'focus_window',
           'maximize', 'wait')
GUIDE_NOTES = '''File dialogs take the absolute document paths the episode gives: type the
path of an input document or of a requested output in the dialog's file-name
field (in an open dialog press Control+L first), then confirm with Return or
the dialog's Open/Save button. Input documents named by an episode are already
in place; file dialogs stay inside those document folders.
'''

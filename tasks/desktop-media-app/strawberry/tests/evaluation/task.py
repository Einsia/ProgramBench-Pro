"""Task identity and black-box runtime configuration for the evaluation runtime."""
TASK = 'strawberry'
VERSION = '1.0.0'
REFERENCE = 'Strawberry 1.2.31'
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
GUIDE_NOTES = """Use the absolute document paths supplied in the episode. File dialogs accept them in their filename or directory fields. Use fill for exact Unicode text. Dialogs may be maximized or scrolled. Right clicks hold briefly to open popup menus; some menus are visible only in screenshots, so coordinates are also available. Inputs already exist in the document folders."""

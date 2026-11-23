"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'zotero'
VERSION = '1.0.0'
REFERENCE = 'Zotero 10.0.6'
SURFACE = 'desktop'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 90
# Evaluator surface: the runtime's desktop GUI operations; observations are its accessibility
# snapshot plus a full-screen screenshot. The desktop has no sessions.
SESSION = {}
START = {'op': 'wait', 'seconds': 1.0}
OBSERVE = ('observe', 'screenshot')
GUI_OPS = ('click', 'activate', 'fill', 'type', 'press', 'check', 'move', 'drag', 'scroll', 'zoom', 'focus_window',
           'maximize', 'wait')
GUIDE_NOTES = '''In file dialogs enter the full path a goal gives (Control+L opens the location field
of an Open dialog; the name field of a Save dialog accepts a full path). The interface refuses
folders outside the episode's inbox and outbox.
'''

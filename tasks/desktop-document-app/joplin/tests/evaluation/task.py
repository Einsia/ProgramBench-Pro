"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'joplin'
VERSION = '1.0.0'
REFERENCE = 'Joplin 3.7.21'
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
START = {'op': 'wait', 'seconds': 0.5}
OBSERVE = ('observe', 'screenshot')
GUI_OPS = ('click', 'activate', 'fill', 'type', 'press', 'check', 'move', 'drag', 'scroll', 'zoom', 'focus_window',
           'maximize', 'wait')
GUIDE_NOTES = '''File dialogs open in the exchange outbox. In file dialogs enter the full path a goal gives (Control+L opens the location field
of an Open dialog; the name field of a Save dialog accepts a full path). The interface refuses
folders outside the episode's inbox and outbox.
'''

"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'marktext'
VERSION = '1.0.0'
REFERENCE = 'MarkText 0.23.0'
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
GUIDE_NOTES = '''The application menu is reached through the "Application Menu" button at the top left (or the F10
key); its menus and submenus are ordinary accessible menu items. In a native save or open dialog, type the full
path a goal gives (Ctrl+L opens the location field of an Open dialog; a Save dialog's name field accepts a full
path) and confirm with the button in the dialog's bottom bar; folders outside the episode's inbox and outbox are
refused.
'''

"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'drawdb'
VERSION = '1.0.0'
REFERENCE = 'drawDB 1.8.2'
SURFACE = 'browser'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
# Evaluator surface: the runtime's GUI operations on its single application page, starting at the editor.
SESSION = {}
START = {'op': 'open', 'path': '/editor'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'back', 'click', 'hover', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag',
           'wheel', 'wait', 'upload', 'dialog')
GUIDE_NOTES = '''This interface is a database diagram editor in a browser page. Menus open when you click or hover
their titles; submenus open when you click or hover their entries. Many toolbar controls are icons without names:
hover one to see its tooltip in the next observation, or use the side panel, the menus and keyboard shortcuts.
The diagram canvas is an SVG drawing surface; tables, views and notes on it are listed with their visible texts and
controls, and their positions are in the controls' bounds and in the screenshot. To connect two columns, drag from
the small dot in front of a column name to the row of the other column. Keyboard shortcuts act on the page when no
text field has focus. Pending downloads appear under "downloads" and a pending file chooser under "file_chooser".
'''

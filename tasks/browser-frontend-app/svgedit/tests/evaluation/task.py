"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'svgedit'
VERSION = '1.0.0'
REFERENCE = 'SVG-edit 7.4.2'
SURFACE = 'browser'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
# Evaluator surface: the runtime's GUI operations on its single editor page, starting at the entry page.
SESSION = {}
START = {'op': 'open'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'click', 'hover', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag', 'wheel',
           'wait', 'upload', 'dialog')
GUIDE_NOTES = '''This interface is a drawing editor. Many controls are icons: the snapshot names them by their tooltip
(title), and a control inside a panel may carry the panel's tooltip as context. Drawing surfaces are listed as
canvas0, canvas1, ... and "drawing" summarises the SVG shapes drawn there (container, kind, attributes, viewport
bounds); the screenshot shows the same drawing. pointer and drag accept target {"document": true} with x/y in the
drawing's own units, or a canvasN ref with pixels relative to that surface, or plain viewport pixels. Keyboard
shortcuts act on the page when no text field has focus. Native prompts are answered with their default unless you
first call dialog (accept with text, or dismiss) right before the action that opens them; answered dialogs are
listed under "dialogs". Downloads and exported images appear under "downloads".
'''

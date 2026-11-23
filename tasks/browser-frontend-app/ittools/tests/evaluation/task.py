'''Task identity and black-box runtime configuration for the shared evaluation package.'''
TASK = 'ittools'
VERSION = '1.0.0'
REFERENCE = 'IT-Tools 2024.10.22-7ca5933'
SURFACE = 'browser'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
# Evaluator surface: the runtime's GUI operations on its single browser page, starting at the home page.
SESSION = {}
START = {'op': 'open', 'path': '/'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'click', 'hover', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag', 'wheel',
           'wait', 'clock', 'upload', 'dialog')
GUIDE_NOTES = '''This interface is a collection of small developer tools. Each tool is a page of its own: the menu lists
them by category and the home page shows one card per tool; open goes to a page by its address. The snapshot lists the
controls of the whole page, also below the fold, each with bounds and an onscreen flag; result fields are listed as
controls with readonly true and their value, preformatted results appear under blocks and other results under text.
Switches, sliders, selects and buttons are listed with their state. Operate a control by its ref (the page scrolls it
into view); pointer, drag and wheel take viewport pixels from the screenshot. The page clock stands still unless clock
advances it; a search box that waits before it applies its input applies it only after the clock has advanced. Copy buttons show a short confirmation; the copied text itself is not part of the observation.
'''

# Task identity and black-box runtime configuration for the shared evaluation package.
TASK = 'navidrome'
VERSION = '1.0.0'
REFERENCE = 'Navidrome 0.64.2'
SURFACE = 'browser'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
# Evaluator surface: the runtime's GUI operations on one browser session, starting at the web application.
SESSION = {'session': 'main'}
START = {'op': 'open', 'path': '/app/'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'back', 'click', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag', 'wheel',
           'scroll', 'upload', 'wait')
GUIDE_NOTES = '''Pages may be taller than the viewport: the snapshot lists every control with its bounds (offscreen
ones are marked) and page_size gives the page height; scroll to bring a part of the page into the screenshot.
The application is a single page: its views are # routes below /app/, and a view can be opened directly by its address.
'''

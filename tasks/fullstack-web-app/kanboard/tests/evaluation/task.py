"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'kanboard'
VERSION = '1.0.0'
REFERENCE = 'Kanboard 1.2.56'
SURFACE = 'browser'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
# Evaluator surface: the runtime's GUI operations on one browser session, starting at the sign-in page.
SESSION = {'session': 'main'}
START = {'op': 'open', 'path': '/login'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'back', 'click', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag', 'wheel',
           'scroll', 'upload', 'wait')
GUIDE_NOTES = '''Pages may be taller than the viewport: the snapshot lists every control with its bounds (offscreen
ones are marked) and page_size gives the page height; scroll to bring a part of the page into the screenshot.
Forms and confirmations often open in a dialog over the page; wait briefly after opening one.
'''

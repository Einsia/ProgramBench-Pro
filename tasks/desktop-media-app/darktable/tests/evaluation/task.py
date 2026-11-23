"""Task identity and black-box runtime configuration for the shared evaluation package."""
TASK = 'darktable'
VERSION = '1.0.0'
REFERENCE = 'darktable 5.6.2'
SURFACE = 'desktop'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
# Seconds the application has to show an accessible window after a start (the runtime's readiness rule).
READY_SECONDS = 60
# Evaluator surface: the runtime's desktop input operations; one desktop, no sessions.
SESSION = {}
START = {'op': 'wait', 'seconds': 2}
OBSERVE = ('observe', 'screenshot')
GUI_OPS = ('click', 'activate', 'fill', 'type', 'press', 'check', 'move', 'drag', 'scroll', 'zoom', 'focus_window',
           'maximize', 'wait')
GUIDE_NOTES = """Input documents are already present at the absolute paths in the episode.
File dialogs accept those paths. The import dialog provides a home place that
contains the inputs and outputs folders. A standard file chooser accepts a
location after Control+L. Use the screenshots for the photo canvas and custom
sliders; other controls expose accessible names and descriptions. Menus,
keyboard shortcuts and other equivalent visible routes are all acceptable.
"""

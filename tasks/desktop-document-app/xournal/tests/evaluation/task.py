"""Public runtime and task identity for the runtime."""
TASK = 'xournal'
VERSION = '1.0.0'
REFERENCE = 'Xournal++ 1.3.8'
SURFACE = 'desktop'
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 90
SESSION = {}
START = {'op': 'wait', 'seconds': .5}
OBSERVE = ('observe', 'screenshot')
GUI_OPS = ('click', 'activate', 'fill', 'type', 'press', 'check', 'move', 'drag', 'scroll', 'zoom', 'focus_window', 'maximize', 'wait')
GUIDE_NOTES = '''Enter file paths exactly as given in a goal. The name field of a Save dialog accepts an absolute path;
Control+L opens the location field of an Open dialog. Files must stay inside the inbox and outbox.
The canvas has no accessible children; use screenshots and pointer coordinates for drawing and selecting.
Do not inspect private files. A save finishes when its dialog closes; files are checked separately.'''

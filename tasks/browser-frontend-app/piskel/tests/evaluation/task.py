"""Task identity and runtime configuration."""
TASK = 'piskel'
VERSION = '1.0.0'
REFERENCE = 'Piskel 0.15.0'
SURFACE = 'browser'
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
SESSION = {}
START = {'op': 'open'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'click', 'hover', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag',
           'wheel', 'wait', 'upload', 'dialog')
GUIDE_NOTES = '''This is a pixel drawing and animation editor. Icon controls are named by their tooltip in the
snapshot. Sprite coordinates are zero-based pixel columns and rows, with (0, 0) at the top left. Use pointer or
drag with target {"sprite": true} to address a pixel centre, or use ordinary viewport coordinates. The snapshot
also lists drawing surfaces and the sprite's viewport origin and pixel size. Keyboard shortcuts act on the page
when a text field is not focused. For a native prompt, call dialog with response="accept" and the desired text BEFORE the action that
opens it; otherwise it is immediately accepted with its default. Answered prompts and their messages remain
listed under dialogs in subsequent snapshots, so read them before retrying a prompt interaction. Answer a pending file chooser with upload.
Downloads are listed in observations. A colour field may need Enter and a click outside its chooser to commit.
Each goal begins in its stated prepared state; do not infer that the previous goal's result is still loaded.
'''

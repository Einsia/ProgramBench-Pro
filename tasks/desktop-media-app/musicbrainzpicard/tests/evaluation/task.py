"""Task identity and black-box runtime configuration for the evaluation runtime."""
TASK = 'musicbrainzpicard'
VERSION = '1.0.0'
REFERENCE = 'MusicBrainz Picard 3.0.3'
SURFACE = 'desktop'
# The task's black-box runtime (environment/runtime/), installed read-only in the
# reference and verifier images; the verifier's source identity covers it.
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-B', '-I', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
# Seconds the application has to show an accessible window after a start (the runtime's readiness rule).
READY_SECONDS = 30
# Evaluator surface: the runtime's desktop input operations; one desktop, no sessions.
SESSION = {}
START = {'op': 'wait', 'seconds': 0.5}
OBSERVE = ('observe', 'screenshot')
GUI_OPS = ('click', 'activate', 'fill', 'type', 'press', 'check', 'move', 'drag', 'scroll', 'zoom', 'focus_window',
           'maximize', 'wait')
GUIDE_NOTES = '''File dialogs take the absolute paths the episode gives: type the path of a
document or folder in the dialog's file-name field, then confirm with Return or
the dialog's Open/Save/Choose button. Documents named by an episode are already
in place. Popup context menus (opened with a right click) are drawn on the
screen but are not listed among the accessible controls: read them in the
screenshot and click their entries by coordinates, or use the keyboard.
'''

TASK = 'stackedit'
VERSION = '1.0.0'
REFERENCE = 'StackEdit 5.15.4'
SURFACE = 'browser'
RUNTIME = '/opt/blackbox/runtime'
RUNTIME_COMMAND = ('python3', '-I', '-B', RUNTIME + '/broker.py')
RUNTIME_ARGS = ()
READY_SECONDS = 75
SESSION = {}
START = {'op': 'open'}
OBSERVE = ('snapshot', 'screenshot')
GUI_OPS = ('open', 'reload', 'click', 'hover', 'fill', 'type', 'select', 'check', 'press', 'pointer', 'drag', 'wheel',
           'wait', 'upload', 'dialog', 'select_text', 'paste')
GUIDE_NOTES = """Operate the editor through visible controls, keyboard and pointer. The snapshot names icon buttons by their tooltip/title or aria label. Editable document controls have editable:true and a value; select_text selects offsets in that value. Some menus scroll inside the side bar: wheel over the side bar to reach lower items. Native file choosers are answered with upload. A goal input file can be uploaded from the offered inputs. Downloads are listed in observations. Each checkpoint has its own prepared state unless the goal explicitly says it continues the previous state. An implementation may use different controls, text and layout to achieve the same visible result."""

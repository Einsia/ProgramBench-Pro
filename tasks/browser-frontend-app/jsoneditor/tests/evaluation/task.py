"""Task identity and public runtime configuration."""
TASK='jsoneditor'
VERSION = '1.0.0'
REFERENCE='JSON Editor 10.4.3'
SURFACE='browser'
RUNTIME='/opt/blackbox/runtime'
RUNTIME_COMMAND=('python3','-I','-B',RUNTIME+'/broker.py')
RUNTIME_ARGS=()
READY_SECONDS=75
SESSION={}
START={'op':'open'}
OBSERVE=('snapshot','screenshot')
GUI_OPS=('open','reload','click','hover','fill','type','paste','select','check','press','pointer','drag','wheel','wait','upload','dialog')
GUIDE_NOTES='''This is a JSON editor. Every checkpoint prepares the document and mode described in its goal. Tree fields and values are editable controls; the snapshot lists their current text, value and bounding box. Buttons often have tooltip titles. Controls in the same row can be distinguished by their bounds. Use the visible controls, keyboard and pointer to operate the editor. Typing without a target uses current focus. For text and code editors, click the editing area and use Control+A then paste to replace its contents. paste inserts a whole text block without triggering automatic bracket pairing for each character. File chooser inputs accept upload. Downloads appear in the snapshot. Dialog answers use dialog_action: accept or dismiss, and can be set before the action that opens a native prompt. The action field is used for pointer gestures only.'''

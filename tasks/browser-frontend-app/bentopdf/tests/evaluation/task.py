"""Task identity and the one shared black-box runtime."""
TASK='bentopdf'
VERSION = '1.0.0'
REFERENCE='BentoPDF 2.8.10 (Simple)'
SURFACE='browser'
RUNTIME='/opt/blackbox/runtime'
RUNTIME_COMMAND=('python3','-B','-I',RUNTIME+'/broker.py')
RUNTIME_ARGS=()
READY_SECONDS=75
SESSION={}
START={'op':'open'}
OBSERVE=('snapshot','screenshot')
GUI_OPS=('open','reload','click','hover','fill','type','select','check','press','pointer','drag','wheel','wait','upload','reuse_download','dialog')
GUIDE_NOTES='''Product downloads are listed in each observation, with their names and sizes. A listed download is a concrete output artifact. Use reuse_download with a listed download ref after opening a file chooser to reopen a generated document. All input files are listed under inputs; upload supplies one file after a chooser is opened through the application. Add More controls can add additional files. For a chooser allowing multiple files, upload the earlier files with stage true and the final file with stage false to select them together. Long pages and tool panels can be scrolled with wheel. Canvas and frame controls use the viewport coordinates in the snapshot. Native color, date and range fields can be set with fill. Goals state the tool page and required input files; any equivalent visible implementation is valid.'''

"""Task identity and the shared runtime interface."""
TASK='tig'
VERSION = '1.0.0'
REFERENCE='tig 2.6.1'
SURFACE='terminal'
RUNTIME='/opt/blackbox/runtime'
RUNTIME_COMMAND=('python3','-B','-I',RUNTIME+'/broker.py')
RUNTIME_ARGS=()
READY_SECONDS=30
SESSION={}
START={'op':'screen'}
OBSERVE=('screen',None)
GUI_OPS=('key','keys','type','wait','resize','mouse','console','grep')
GUIDE_NOTES='''The screen has numbered rows NN|text and styled spans; NN is an observation prefix.
The product is Tig, a Git browser. m main, d diff, l log, L reflog, t tree, f blob, b blame,
r refs, y stash, h help, s status, c stage, p pager. j/k move, Home/End first/last,
Enter open, Tab focus, O maximize, q close/back, R refresh, comma parent, < back.
/ and ? search, n/N next/previous. Search for a filename to select it in status.
u stages or unstages a file in status; in stage it stages the selected hunk.
1 stages a single line; ! reverts with confirmation. Use console for native commands
without a leading colon (set/toggle/color/bind/goto/echo/internal actions), and grep
for repository search. Raw colon and g do not open prompts in this environment.
console is the native Tig prompt, not a shell. The options menu is o; # toggles line
numbers, A author, T committer, D date, X IDs, G main graph, F references/filenames.
Use visible outcomes to judge; exact layout, color, wording, IDs and timestamps may differ.
'''

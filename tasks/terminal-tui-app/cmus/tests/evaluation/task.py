TASK='cmus'
VERSION = '1.0.0'
REFERENCE='cmus 2.13.0'
SURFACE='terminal'
RUNTIME='/opt/blackbox/runtime'
RUNTIME_COMMAND=('python3','-I',RUNTIME+'/broker.py')
RUNTIME_ARGS=()
READY_SECONDS=30
SESSION={}
START={'op':'screen'}
OBSERVE=('screen',None)
GUI_OPS=('key','keys','type','wait','resize')
GUIDE_NOTES="screen lists settled rows as NN|text and style spans identifying selections and marks. Keys 1-7 switch library tree, sorted library, playlist, queue, browser, filters and settings. Tab switches panes. In a playlist the left pane selects/marks a playlist; switch to its track pane to edit tracks. j/k or arrows move, g/G jump. Enter plays/activates, Space marks or expands, D removes, p/P move. x plays, c pauses, v stops; b/z skip tracks. : opens the command line; / opens search, n/N move matches. Commands include add -l/-p/-q/-Q PATH; clear -l/-p/-q; filter EXPRESSION; live-filter TEXT; set OPTION=VALUE; toggle OPTION; pl-create NAME; pl-rename NAME; player-play PATH; player-pause-playback; seek TIME; vol VALUE; bind -f common KEY COMMAND. The public /workspace alias is accepted in typed text. Use one checkpoint's goal at a time. Terminal layout and equivalent commands are free."

'''Diff controls, list navigation, terminal resizing, persisted display settings and message editing.'''
from spec_base import *  # noqa: F401,F403
from spec_flow import H3


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid,goal,S(scenario(fixture),keys,wait(.6)),checks,requires=requires)


def multiline(value):
    steps = []
    for i, line in enumerate(value.split('\n')):
        if i:
            steps += K('Enter')
        if line:
            steps.append(typ(line))
    return steps


def build():
    W=[]
    context=S(commit('base',{'f.txt':text(*['line %02d'%i for i in range(1,21)])}),
              put({'f.txt':text(*['changed' if i==10 else 'line %02d'%i for i in range(1,21)])}))
    W.append(program('diff-context','diff',context,[
        step('smaller','Reduce the context around the modified line.',K('2','j','{'),
             [('hunks','The diff displays fewer context lines.',scr('diff-hunks'))]),
        step('larger','Increase the context again.',K('}'),
             [('hunks','The diff displays the restored context.',scr('diff-hunks'))],depends=['smaller']),
    ]))
    white=S(commit('base',{'f.txt':text('first-line','old-second-line','third-line')}),
            put({'f.txt':text(' first-line',' new-second-line',' third-line')}))
    W.append(program('diff-whitespace','diff',white,[
        step('ignore','Ignore whitespace-only changes in the diff.',K('2','j','Control+W'),
             [('changes','Only the substantive second-line change remains.',scr('diff-changes'))]),
        step('restore','Show whitespace-only changes again.',K('Control+W'),
             [('changes','The first and third line changes are visible again.',scr('diff-changes'))],depends=['ignore']),
    ]))
    renamed=S(commit('original',{'original':text('one','two','three','four','five')}),git('rm','original'),
              commit('rename and extend',{'renamed':text('one','two','three','four','five','six','seven','eight','nine','ten')}))
    W.append(program('diff-rename-threshold','diff',renamed,[
        step('lower','Lower the rename similarity threshold.',K('4','('),
             [('summary','The diff recognises a rename and five added lines.',scr('diff-summary'))]),
        step('raise','Restore the original rename threshold.',K(')'),
             [('summary','The diff shows a deletion and an addition.',scr('diff-summary'))],depends=['lower']),
    ]))
    dirs=S(H3,put({'a/first.txt':text('first'),'b/second.txt':text('second'),'top.txt':text('top')}))
    W.append(program('file-tree-navigation','navigation',dirs,[
        step('collapse','Collapse the root before exploring navigation.',K('2','-'),
             [('items','Only the collapsed root is listed.',pan(2))]),
        step('expand','Expand every directory.',K('='),
             [('items','Both nested files are listed.',pan(2))],depends=['collapse']),
        step('flat','Switch from the tree to the flat file list.',K('`'),
             [('items','The files are listed with their relative paths.',pan(2))],depends=['expand']),
        step('tree','Switch back to the directory tree.',K('`'),
             [('items','The nested tree returns.',pan(2))],depends=['flat']),
        step('wide','Resize the terminal and select the second directory.',S({'resize':[150,42]},K('2','<','j','j','j')),
             [('selected','Directory b is selected in the enlarged terminal.',pan(2,'selected')),
              ('items','The directory contents are preserved.',pan(2))],depends=['tree'], requires={'items':['selected']}),
        step('restore','Restore the terminal size and select its file.',S({'resize':[120,36]},K('j')),
             [('selected','second.txt is selected after resizing.',pan(2,'selected'))],depends=['wide']),
    ]))
    W.append(program('commit-page-navigation','navigation',history(*['entry-%02d'%i for i in range(1,31)]),[
        step('page-down','Move one page down the commits list.',K('4','.'),
             [('selected','The selection moves by one page.',pan(4,'selected'))]),
        step('next-page','Move another page down.',K('.'),
             [('selected','The selection moves farther down.',pan(4,'selected'))],depends=['page-down']),
        step('page-up','Move one page back.',K(','),
             [('selected','The earlier page selection returns.',pan(4,'selected'))],depends=['next-page']),
    ]))
    W.append(program('screen-modes','navigation',dirs,[
        step('full','Expand the focused files panel to full screen.',K('2','j','j','+','+'),
             [('panels','Only the focused panel remains visible.',scr('visible-panels')),
              ('selection','The selected file remains available.',pan(2,'selected'))],requires={'selection':['panels']}),
        step('restore','Return from full screen to the preceding screen mode.',K('_'),
             [('panels','The main view is visible beside the files panel again.',scr('visible-panels'))],depends=['full']),
    ]))
    branches=S(commit('base',{'base.txt':text('base')}),git('checkout','-q','-b','alpha'),
               commit('alpha commit',{'a.txt':text('a')}),git('checkout','-q','main'),git('checkout','-q','-b','zeta'),
               commit('zeta commit',{'z.txt':text('z')}),git('checkout','-q','alpha'),git('checkout','-q','main'))
    W.append(program('branch-sort','branches',branches,[
        step('alphabetical','Sort branches alphabetically.',K('3','s','a'),
             [('items','The branch names are alphabetically ordered after the current branch.',pan(3))]),
        step('date','Sort branches by commit date.',K('s','d'),
             [('items','zeta precedes alpha by commit date.',pan(3))],depends=['alphabetical']),
        step('recency','Sort branches by checkout recency.',K('s','r'),
             [('items','alpha precedes zeta by checkout recency.',pan(3))],depends=['date']),
    ]))
    W.append(program('command-log-state','state',H3,[
        step('hide','Hide the command log.',K('@','t'),
             [('state','The hidden command log preference is saved.',state(field='hidecommandlog'))]),
        step('restart','Restart with the saved preference.',[restart()],
             [('state','The preference remains saved after restart.',state(field='hidecommandlog'))],depends=['hide']),
        step('show','Show the command log again.',K('@','t'),
             [('state','The visible command log preference is saved.',state(field='hidecommandlog'))],depends=['restart']),
    ]))
    messages=[('paragraphs','subject with body','first paragraph\n\nsecond paragraph'),
              ('unicode','Résumé change','café 中文\nnext line'),
              ('quotes','Fix "quoted" input',"reader's note\n`literal` text"),
              ('trailers','Change with trailer','explanation\n\nReviewed-by: Example <reader@example.com>')]
    for name,subject,body in messages:
        W.append(program('message-'+name,'commits',S(H3,put({'new.txt':text('new')})),[
            step('commit','Commit the specified subject and multiline description.',
                 S(K('2','a','c'),typ(subject),K('Tab'),multiline(body),K('Tab','Enter')),
                 [('message','The complete message is preserved.',gitc('log','-1','--format=%B')),
                  ('log','One commit was added and the worktree is clean.',repo('log','status'))]),
            step('reword','Change the subject while retaining the prefilled description.',
                 S(K('4','r','Control+U'),typ('reworded '+subject),K('Enter')),
                 [('message','The new subject retains the original description.',gitc('log','-1','--format=%B'))],depends=['commit']),
        ]))
    for name,bad in [('double-dot','bad..name'),('lock-suffix','topic.lock'),('tilde','topic~1'),('colon','topic:name'),('trailing-slash','topic/')]:
        W.append(program('branch-invalid-'+name,'branches',H3,[
            step('reject','Try to create an invalid branch name.',S(K('3','n'),prompt(bad)),
                 [('error','The interface reports the invalid reference name.',scr('popup')),
                  ('branches','No branch was created.',repo('branches'))],requires={'branches':['error']}),
        ]))
    return W

'''Submodule update, patch reapplication, ref comparisons, branch ranges and checkout undo/redo.'''
from spec_base import *  # noqa: F401,F403
from spec_flow import H3, FEATURE, SUBMOD


def build():
    W=[]
    old_branch=S(H3,git('branch','older','HEAD~1'))
    W.append(program('undo-redo-checkout','undo',old_branch,[
        step('checkout','Check out older.',K('3','j','Space'),
             [('head','older is checked out.',repo('head'))]),
        step('undo','Undo the branch checkout.',K('z','Enter'),
             [('head','main is checked out again.',repo('head')),
              ('files','The newest file returns.',gitc('ls-tree','-r','--name-only','HEAD'))],depends=['checkout']),
        step('redo','Redo the branch checkout.',K('Z','Enter'),
             [('head','older is checked out again.',repo('head'))],depends=['undo']),
    ]))
    W.append(program('select-branch-commits','commits',FEATURE,[
        step('drop','Select all commits belonging to feature and drop them.',K('4','*','d','Enter'),
             [('log','feature is reset to base.',repo('head','log')),
              ('files','Only the base file remains.',gitc('ls-tree','-r','--name-only','HEAD'))]),
    ]))
    advanced=S(SUBMOD,commit('sub two',{'second.txt':text('second')},repo='sub1'),git('add','sub1'),
               git('commit','-q','-m','record newer submodule'),git('checkout','-q','HEAD~1',repo='sub1'))
    W.append(program('submodule-update','submodules',advanced,[
        step('update','Update sub1 to the commit recorded in the parent index.',K('2',']',']','u'),
             [('commit','sub1 is at sub two again.',gitc('log','-1','--format=%s',repo='sub1')),
              ('status','The submodule matches the parent index.',gitc('submodule','status')),
              ('files','The newer submodule file is restored.',listing('/workspace/sub1',fields=['sha256']))]),
    ]))
    W.append(program('custom-patch-reapply','patch',H3,[
        step('reverse','Reverse the second commit patch in the index.',K('4','j','Enter','Space','Escape','Control+P','r'),
             [('status','c2.txt is staged for deletion.',repo('status')),
              ('diff','The reverse patch is staged.',gitc('diff','--cached'))]),
        step('apply','Apply the patch again.',K('Control+P','a'),
             [('status','The original indexed tree is restored.',repo('status')),
              ('file','The restored index contains c2.txt.',gitc('show',':c2.txt'))],depends=['reverse'],requires={'file':['status']}),
    ]))
    W.append(program('diff-two-refs','diff',H3,[
        step('compare','Compare the newest commit against HEAD~2.',S(K('4','W','j','Enter'),prompt('HEAD~2')),
             [('summary','The comparison includes both intervening file additions.',scr('diff-summary')),
              ('changes','The view contains the changes between the two refs.',scr('diff-changes'))]),
        step('swap','Swap the two sides of the comparison.',K('W','j','j','Enter'),
             [('changes','The additions become deletions.',scr('diff-changes'))],depends=['compare']),
    ]))
    return W

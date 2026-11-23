'''Conflict entry, resolution, abort and skip, with fixtures that distinguish all three recovery outcomes.'''
from spec_base import *  # noqa: F401,F403
from spec_flow import CONFLICT

PICK = S(K('3','j','Enter','v','j','C','Escape','4','V','Enter'),wait(1))
REBASE = S(K('3','j','r','Enter'),wait(1))
RESOLVE = S(K('Enter','Enter','j','Space'),wait(.5),K('Enter'),wait(1))


def recovery_checks():
    return [('history','The operation finishes with the expected branch history.',repo('head','log')),
            ('file','The final committed file has the chosen side or restored content.',gitc('show','HEAD:f.txt')),
            ('status','The index and working tree are clean.',repo('status'))]


def build():
    W=[]
    for kind,keys in [('cherry-pick',PICK),('rebase',REBASE)]:
        fixture = (S(CONFLICT,git('checkout','-q','feature'),commit('after-conflict',{'after.txt':text('after')}),
                     git('checkout','-q','main')) if kind=='cherry-pick'
                   else S(CONFLICT,commit('after-conflict',{'after.txt':text('after')})))
        W.append(program(kind+'-conflict','conflicts',fixture,[
            step('conflict','Start the operation so that f.txt conflicts.',keys,
                 [('status','f.txt has unresolved stages.',repo('status')),
                  ('stages','The index contains the base and both sides.',gitc('ls-files','--unmerged'))]),
            step('abort','Abort the operation and restore the original state.',S(K('a'),wait(1)),recovery_checks(),
                 depends=['conflict'],requires={'file':['history','status'],'history':['status']}),
            step('skip','Repeat the operation and skip the conflicting commit, retaining the subsequent commit.',
                 S(scenario(fixture),keys,K('Escape','m','s'),wait(1)),recovery_checks(),
                 requires={'file':['history'],'status':['history']}),
            step('continue','Repeat the operation, keep the incoming side and continue through the subsequent commit.',
                 S(scenario(fixture),keys,RESOLVE),recovery_checks(),
                 requires={'file':['history'],'status':['history']}),
        ]))
    stashed=S(commit('base',{'f.txt':text('base')}),put({'f.txt':text('stashed')}),
              git('stash','push','-q','-m','conflicting stash'),commit('changed',{'f.txt':text('current')}))
    W.append(program('stash-pop-conflict','conflicts',stashed,[
        step('pop','Pop the stash whose change conflicts with the current file.',S(K('5','g','Enter'),wait(1)),
             [('index','The index contains the conflicting versions.',gitc('ls-files','--unmerged')),
              ('stash','The stash is retained when applying it conflicts.',repo('stash'))],requires={'stash':['index']}),
    ]))
    return W

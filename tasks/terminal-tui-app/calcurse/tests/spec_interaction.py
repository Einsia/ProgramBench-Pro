"""Deterministic interaction edges, saved-state lifecycle and key configuration."""
from spec_common import *
from fixtures import ui, apt, event, NOTE, DEFAULT_KEYS
import re
from spec_gui import add_event, add_appt, replace, command, setting_steps


def build():
    cases=[]
    for name,actions in [
        ('cancel-start',[K('a'),K('Escape')]),
        ('cancel-end',S(K('a'),answer('12:00'),K('Escape'))),
        ('cancel-description',S(K('a'),answer('12:00'),answer('13:00'),K('Escape'))),
        ('blank-event',S(K('a'),K('Enter'),K('Enter'))),
        ('cancel-edit',S(KS('e','3'),TY(' changed'),K('Escape'))),
        ('cancel-delete',S(K('d'),K('Escape'))),
        ('cancel-repeat',S(K('r'),K('Escape'))),
    ]:
        # First create a positive result through the same application before exercising cancellation.
        actions=S(add_appt('10:00','11:00','Retained'),actions,SAVE)
        cases.append((step(name,'Create a retained appointment, then exercise '+name+'.',actions,[
            ('data','The real appointment remains and the cancelled operation has no saved effect.',apts())]),ui()))
    for name,editing in [
        ('home-insert',S(K('Control+A'),TY('Prefix '))),
        ('end-append',S(K('Control+E'),TY(' suffix'))),
        ('backward-delete',S(K('Control+E'),K('Backspace'))),
        ('forward-delete',S(K('Control+A'),K('Control+D'))),
        ('kill-to-end',S(K('Control+A'),KS('Control+F','Control+F'),K('Control+K'))),
        ('delete-word',S(K('Control+E'),K('Control+W'))),
        ('left-insert',S(K('Control+E'),K('Left'),TY('X'))),
        ('unicode-backspace',S(K('Control+E'),TY('é'),K('Backspace'),TY('東京'))),
    ]:
        cases.append((step(name,'Edit the description with '+name+'.',S(K('e'),editing,K('Enter'),SAVE),[
            ('text','Line editing produces the intended saved description.',apts())]),ui(apts=[event(text='Alpha beta')])) )
    for name,actions,cfg in [
        ('save-command',command('write'),{}),
        ('save-alias',command('w'),{}),
        ('write-quit',command('wq!'),{}),
        ('quit-autosave',KS('q','y'),{}),
        ('quit-discard',command('q!'),{'general.autosave':'no'}),
    ]:
        actions=S(K('a'),K('Enter'),answer('Pending event'),actions)
        cases.append((step(name,'Create an event and apply '+name+'.',actions,[
            ('data','Saved state follows the selected save/quit operation.',apts())]),ui(apts=[event(text='Existing')],conf=cfg)))
    # A user-defined binding has to perform the action; preserving a keys file alone is insufficient.
    for name,binding,steps in [
        ('add','generic-add-appt  z\n',S(K('z'),K('Enter'),answer('Bound event'),SAVE)),
        ('save','generic-save  z\n',S(K('a'),K('Enter'),answer('Bound save'),K('z'))),
        ('todo','generic-add-todo  z\n',S(K('z'),answer('Bound todo'),K('2'),SAVE)),
    ]:
        check=dict(todos() if name=='todo' else apts(), nonempty=True)
        action=binding.split()[0]
        binding=re.sub(r'^'+re.escape(action)+r' .*$', binding.strip(), DEFAULT_KEYS, flags=re.M)
        cases.append((step('binding-'+name,'Use a configured key binding for '+name+'.',steps,[
            ('action','The assigned key performs its configured action.',check)]),ui(keys=binding)))
    out=scenarios('interaction','editing',cases,chunk=8)

    out.append(program('reload-persistence','persistence',ui(apts=[event(text='Saved')]),[
        step('change','Make an unsaved edit.',S(K('e'),replace('Unsaved')),[(
            'visible','The unsaved edit is shown in the application.',scr('contains',needles=['Unsaved']))]),
        step('reload','Reload the saved files, discarding local changes.',S(K('R'),K('c')),[
            ('saved','The saved event is visible after reload.',scr('contains',needles=['Saved']))],depends=['change']),
    ]))
    return out

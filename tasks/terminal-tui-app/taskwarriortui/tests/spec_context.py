"""Contexts: the context switcher menu (c) lists Taskwarrior's read contexts; selecting one runs `task context` (the
setting persists in the configuration), names it in the top bar and narrows the report; a context's write filter
applies to tasks added while it is active.
"""
from spec_core import *
from spec_data import MAIN

CONTEXTS = [('context.home.read', 'project:Home'), ('context.home.write', 'project:Home'),
            ('context.work.read', 'project:Work'), ('context.urgent.read', '+DUE or +OVERDUE')]
CURRENT = cli('_get', 'rc.context')


def menu_episode():
    menu = lambda text: ('menu', text, scr('menu', title='Context'))
    fx = {'tasks': MAIN, 'config': CONTEXTS}
    items = [
        ('open', fx, 'Press c.', K('c'),
         [menu('The menu lists none and the read contexts with their definitions; none is active and highlighted.')]),
        ('select', fx, 'Open the menu, press Down and Enter.', K('c', 'Down', 'Enter'),
         [('label', 'The top bar names the home context.', scr('label')),
          ('rows', 'The report lists only the tasks of the context.', scr('rows')),
          ('setting', 'The context setting is stored in the configuration.', CURRENT),
          ('boxes', 'The menu closes after the selection.', scr('boxes'))], ['open']),
        ('reopen', None, 'Press c again.', K('c'), [menu('home is now the active and highlighted context.')],
         ['select']),
        ('search', fx, 'Open the menu and type wo.', [key('c'), typ('wo')], [menu('Only the work context is left.')],
         ['open']),
        ('work', None, 'Press Enter.', K('Enter'),
         [('label', 'The work context is active.', scr('label')),
          ('rows', 'The report lists the tasks of the work context.', scr('rows')),
          ('setting', 'The stored context is work.', CURRENT)], ['search']),
        ('add-in-context', None, 'Add the task "Context chore" while the work context (without a write filter) is '
                                 'active.', add('Context chore'),
         [('task', 'Without a write filter the new task gets no project.', ex(['Context chore'], 'project'))],
         ['work']),
        ('letters', {'tasks': MAIN, 'config': CONTEXTS + [('context.joint.read', 'project:Work or project:Home')]},
         'Open the menu and type j.', [key('c'), typ('j')],
         [menu('j is search text in the menu, not a movement key: only contexts containing j are left.')], ['open']),
        ('urgent', fx, 'Select the urgent context (a filter with or) from the menu.', [key('c'), typ('urg'),
                                                                                      key('Enter')],
         [('rows', 'The report lists the tasks of the urgent context.', scr('rows')),
          ('label', 'The top bar names the urgent context.', scr('label'))], ['open']),
        ('none', {'tasks': MAIN, 'config': CONTEXTS + [('context', 'work')]},
         'With the work context active, select none from the menu.', [key('c'), typ('none'), key('Enter')],
         [('label', 'No context is active.', scr('label')),
          ('rows', 'The report lists every pending task again.', scr('rows')),
          ('setting', 'The context setting is cleared.', CURRENT)], ['open']),
        ('escape', fx, 'Open the menu, press Down and then Escape.', K('c', 'Down', 'Escape'),
         [('label', 'Escape closes the menu without switching.', scr('label')),
          ('boxes', 'The menu is closed.', scr('boxes'))], ['open']),
        ('quit-key', fx, 'Open the menu and press q.', K('c', 'q'),
         [('boxes', 'q closes the menu when its search is empty.', scr('boxes')),
          ('running', 'The application keeps running.', scr('running'))], ['open']),
    ]
    return cases('context-menu', 'context', items, names=['Context chore'])


def write_episode():
    cps = [
        step('home', 'Select the home context with the context menu.', [key('c'), typ('home'), key('Enter')],
             [('label', 'The home context is active.', scr('label'))]),
        step('add', 'Add the task "Mend gate".', add('Mend gate'),
             [('task', 'The context\'s write filter gives the new task the project Home.', ex(['Mend gate'], 'project')),
              ('rows', 'The new task is listed in the context.', scr('rows'))], depends=['home']),
        step('restart', 'Restart the application.', [restart()],
             [('label', 'The context is still active after a restart.', scr('label')),
              ('rows', 'The report is still narrowed to the context.', scr('rows'))], depends=['add']),
        step('filter', 'With the context active, filter the report with +bills.', filt('+bills'),
             [('rows', 'The filter applies within the context.', scr('rows'))], depends=['home'],
             lifecycle='restart'),
    ]
    return program('context-write', 'context', fixture(MAIN, CONTEXTS), cps, names=['Mend gate'])


def preset_episode():
    # A context made active through the configuration before the application starts.
    cps = [
        step('start', 'Observe the application started with the work context active.', [],
             [('label', 'The top bar names the work context.', scr('label')),
              ('rows', 'Only the work tasks are listed.', scr('rows'))]),
        step('menu', 'Open the context menu.', K('c'),
             [('menu', 'work is the active and highlighted context.', scr('menu', title='Context'))],
             depends=['start']),
    ]
    return program('context-preset', 'context', fixture(MAIN, CONTEXTS + [('context', 'work')]), cps)


def options_episode():
    options = [('uda.taskwarrior-tui.context-menu.select-on-move', 'true'),
               ('uda.taskwarrior-tui.context-menu.close-on-select', 'false')]
    cps = [
        step('move', 'Open the context menu and press Down.', K('c', 'Down'),
             [('label', 'With select-on-move the highlighted context becomes active at once.', scr('label')),
              ('setting', 'The stored context follows the highlight.', CURRENT),
              ('menu', 'The menu stays open.', scr('menu', title='Context'))]),
        step('enter', 'Press Down and Enter.', K('Down', 'Enter'),
             [('menu', 'With close-on-select false the menu stays open after Enter.', scr('menu', title='Context')),
              ('label', 'The work context is active.', scr('label'))], depends=['move']),
    ]
    return program('context-options', 'context', fixture(MAIN, CONTEXTS + options), cps)


def episodes():
    return [menu_episode(), write_episode(), preset_episode(), options_episode()]

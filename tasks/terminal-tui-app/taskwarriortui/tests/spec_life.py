"""Persistence and lifecycle: what survives a restart of the application (tasks, context, histories) and what does
not (the chosen report, marks, the typed filter, the selection), a reset to an empty data directory, refreshing
after changes made from the command line, and quitting.
"""
from spec_core import *
from spec_data import MAIN

CONTEXTS = [('context.home.read', 'project:Home'), ('context.work.read', 'project:Work')]


def restart_episode():
    cps = [
        step('add', 'Add the task "Survivor" with project:Keep.', add('Survivor', 'project:Keep'),
             [('task', 'The task is added.', ex(['Survivor'], 'status', 'project'))]),
        step('changes', 'Switch to the oldest report, mark the first task and select the third.',
             [key('R'), typ('oldest'), key('Enter'), key('g'), key('v'), key('j'), key('j')],
             [('label', 'The oldest report is shown.', scr('label')),
              ('marked', 'The first task is marked.', scr('marked'))], lifecycle='restart'),
        step('restart', 'Restart the application.', [restart()],
             [('rows', 'The added task is still listed after the restart.', scr('rows')),
              ('label', 'The application starts on the next report again.', scr('label')),
              ('marked', 'Marks are not kept.', scr('marked')),
              ('selected', 'The first task is selected.', scr('selected'))], depends=['add', 'changes']),
        step('filter', 'Filter with +bills, then restart.', filt('+bills') + [restart()],
             [('line', 'The filter line shows the report\'s filter again.', scr('line')),
              ('rows', 'Every pending task is listed again.', scr('rows'))], depends=['add'], lifecycle='restart'),
        step('context', 'Select the home context from the context menu, then restart.',
             [key('c'), typ('home'), key('Enter'), restart()],
             [('label', 'The context is kept after the restart.', scr('label')),
              ('rows', 'The report is narrowed to the context.', scr('rows'))], lifecycle='restart'),
        step('quit', 'Press q.', K('q'), [('running', 'The application quits.', scr('running'))],
             depends=['context']),
        step('after-quit', 'Restart the application after it quit.', [restart()],
             [('rows', 'It starts again on the same data and context.', scr('rows')),
              ('running', 'It is running.', scr('running'))], depends=['quit']),
        step('reset', 'Reset to a fresh data directory.', [{'reset': True}],
             [('tasks', 'No task is left.', summary()), ('rows', 'The report is empty.', scr('rows')),
              ('label', 'No context is active.', scr('label'))], depends=['add', 'context']),
        step('reset-history', 'Open the add prompt and press Up.', K('a', 'Up'),
             [('prompt', 'The command history is empty after the reset.', scr('prompt'))], depends=['reset']),
    ]
    wf = program('lifecycle', 'persistence', fixture(MAIN, CONTEXTS), cps, names=['Survivor'])
    return bind(wf, {'restart/marked': ['restart/rows']})


def refresh_episode():
    fx = {'tasks': MAIN}
    items = [
        ('refresh', fx, 'Add a task "From outside" with the command line, then press r.',
         [cmd('rc.confirmation=off', 'add', 'From outside', 'project:Ext'), key('r')],
         [('rows', 'After r the report lists the task added outside the application.', scr('rows'))]),
        ('outside-done', fx, 'Complete task 1 with the command line, then press r.',
         [cmd('rc.confirmation=off', '1', 'done'), key('r')],
         [('rows', 'After r the completed task is gone from the report.', scr('rows'))]),
        ('outside-modify', fx, 'Give task 2 the tag outside with the command line, press r and select task 2.',
         [cmd('rc.confirmation=off', '2', 'modify', '+outside'), key('r')] + jump(2),
         [('details', 'The details show the change made outside.', scr('detail', key='Tags'))]),
    ]
    return cases('refresh', 'persistence', items, names=['From outside'])


def episodes():
    return [restart_episode(), refresh_episode()]

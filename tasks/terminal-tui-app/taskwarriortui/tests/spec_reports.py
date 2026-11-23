"""Reports: the report switcher menu (R), each of Taskwarrior's built-in reports as taskwarrior-tui shows it (its
name, its labelled columns and its tasks in the report's own filter and order), and a custom report defined in the
configuration.

Each report checkpoint starts from a restarted application, opens the menu, types the report name to narrow the
menu and confirms it, so the checkpoints are independent of each other.
"""
from spec_core import *
from spec_data import MAIN

# The main fixture plus a recurring task, so the recurring report has content.
SETUP = fixture(MAIN, commands=[('add', 'Weekly sync', 'recur:weekly', 'due:friday', 'project:Work')])
NAMES = [t['description'] for t in MAIN] + ['Weekly sync']

# (report, how the rows are compared: rows in order, or rowset where the report's sort ties)
REPORTS = [('active', 'rows'), ('all', 'rows'), ('blocked', 'rows'), ('blocking', 'rows'), ('completed', 'rows'),
           ('list', 'rows'), ('long', 'rowset'), ('ls', 'rows'), ('minimal', 'rows'), ('newest', 'rows'),
           ('oldest', 'rows'), ('overdue', 'rows'), ('ready', 'rows'), ('recurring', 'rows'), ('unblocked', 'rows'),
           ('waiting', 'rows')]


# The text typed into the report menu to narrow it to the report (the menu searches names and descriptions).
SEARCH = {'ls': 'few'}


def pick(name):
    return [key('R'), typ(SEARCH.get(name, name)), key('Enter')]


def reports_episode():
    cps = []
    for name, order in REPORTS:
        cps.append(step(name, f'Switch to the {name} report with the report menu.', pick(name),
                        [('headers', f'The report shows the labelled columns of the {name} report that have content.',
                          scr('headers')),
                         (order, f'The report lists the tasks of the {name} report in its order.', scr(order)),
                         ('filter', f'The filter line shows the {name} report\'s filter.', scr('line'))]))
    cps.append(step('next', 'Switch to the completed report and back to the next report.',
                    pick('completed') + pick('next'),
                    [('label', 'The top bar names the report shown: next again.', scr('label')),
                     ('rows', 'The next report lists the pending tasks by urgency.', scr('rows'))]))
    wf = program('reports', 'reports', SETUP, fresh(cps), names=NAMES)
    return bind(wf, {'all/filter': ['list/filter']})


def menu_episode():
    menu = lambda text: ('menu', text, scr('menu', title='Report'))
    cps = [
        step('open', 'Press R.', K('R'),
             [menu('The menu lists every report with its description; next is active and highlighted.')]),
        step('down', 'Open the menu and press Down twice.', K('R', 'Down', 'Down'),
             [menu('The highlight moves two reports further.')], depends=['open']),
        step('up', 'Open the menu, press Down twice and Up once.', K('R', 'Down', 'Down', 'Up'),
             [menu('The highlight moves back one report.')], depends=['down']),
        step('search', 'Open the menu and type comp.', [key('R'), typ('comp')],
             [menu('Only the reports whose name or description contains "comp" are left.')], depends=['open']),
        step('backspace', 'Open the menu, type comp and press Backspace twice.',
             [key('R'), typ('comp'), key('Backspace'), key('Backspace')],
             [menu('The search shrinks to "co" and more reports match.')], depends=['search']),
        step('letters', 'Open the menu and type jk.', [key('R'), typ('jk')],
             [menu('j and k are search text in the menu, not movement keys.')], depends=['search']),
        step('clear', 'Open the menu, type comp and press Escape.', [key('R'), typ('comp'), key('Escape')],
             [menu('Escape first clears the search; the menu stays open with every report.')], depends=['search']),
        step('close', 'Open the menu and press Escape.', K('R', 'Escape'),
             [('boxes', 'The menu is closed.', scr('boxes')), ('label', 'The report did not change.', scr('label'))],
             depends=['open']),
        step('no-match', 'Open the menu, type zzz and press Enter.', [key('R'), typ('zzz'), key('Enter')],
             [menu('Nothing matches; Enter selects nothing and the menu stays open.'),
              ('label', 'The report did not change.', scr('label'))], depends=['open']),
        step('quit-key', 'Open the menu and press q.', K('R', 'q'),
             [('boxes', 'q closes the menu when the search is empty.', scr('boxes')),
              ('running', 'The application keeps running.', scr('running'))], depends=['open']),
        step('select', 'Open the menu, move down to the report after next (oldest) and press Enter.',
             K('R', 'Down', 'Enter'),
             [('label', 'The oldest report is shown.', scr('label')),
              ('rows', 'The tasks are listed oldest first.', scr('rows')),
              ('boxes', 'The menu closes after the selection.', scr('boxes'))], depends=['open']),
        step('reopen', 'Open the menu again.', K('R'),
             [menu('The oldest report is now the active and highlighted one.')], depends=['select']),
    ]
    for cp in cps[1:]:
        if cp['id'] != 'reopen':
            cp['lifecycle'] = 'restart'
    return program('report-menu', 'reports', fixture(MAIN), cps)


CUSTOM = [('report.mine.description', 'My tagged tasks'), ('report.mine.columns', 'id,project,tags,priority,description'),
          ('report.mine.labels', 'Num,Area,Labels,Pri,What'), ('report.mine.filter', 'status:pending +TAGGED'),
          ('report.mine.sort', 'project+,description+')]


def custom_episode():
    cps = [
        step('menu', 'Open the report menu and type mine.', [key('R'), typ('mine')],
             [('menu', 'The custom report appears with its description.', scr('menu', title='Report'))]),
        step('select', 'Press Enter.', K('Enter'),
             [('label', 'The custom report is shown.', scr('label')),
              ('headers', 'Its own labels head its columns.', scr('headers')),
              ('rows', 'Its filter and sort apply.', scr('rows'))], depends=['menu']),
        step('cells', 'Observe the Area column.', [],
             [('cells', 'The Area column shows each task\'s project.', scr('cells', label='Area'))], depends=['select']),
    ]
    return program('report-custom', 'reports', fixture(MAIN, CUSTOM), cps)


def columns_episode():
    # One custom report per column type; each checkpoint shows the column for every listed task.
    columns = [('due', 'due'), ('due-relative', 'due.relative'), ('scheduled', 'scheduled'),
               ('scheduled-countdown', 'scheduled.countdown'), ('entry', 'entry'), ('entry-age', 'entry.age'),
               ('start', 'start'), ('start-age', 'start.age'), ('until', 'until'), ('until-remaining', 'until.remaining'),
               ('wait-remaining', 'wait.remaining'), ('end', 'end'), ('end-age', 'end.age'), ('status', 'status'),
               ('status-short', 'status.short'), ('tags-count', 'tags.count'), ('depends', 'depends'),
               ('depends-count', 'depends.count'), ('description-count', 'description.count'), ('urgency', 'urgency'),
               ('priority', 'priority'), ('project', 'project')]
    config = []
    for cid, column in columns:
        name = 'c' + cid.replace('-', '')
        listed = 'status:completed or status:deleted' if column.startswith('end') else 'status.not:recurring'
        config += [(f'report.{name}.columns', f'id,{column},description'), (f'report.{name}.labels', 'ID,Value,Desc'),
                   (f'report.{name}.filter', listed), (f'report.{name}.sort', 'entry+'),
                   (f'report.{name}.description', f'Column {column}')]
    cps = [step(cid, f'Switch to the report that shows the {column} column.', pick('c' + cid.replace('-', '')),
                [('cells', f'The Value column shows each task\'s {column} the way the report renders it.',
                  scr('cells', label='Value'))])
           for cid, column in columns]
    return program('report-columns', 'reports', fixture(MAIN, config), fresh(cps))


def episodes():
    return [reports_episode(), menu_episode(), custom_episode(), columns_episode()]

"""The task details pane: Taskwarrior's information about the selected task (fields, dates with ages, tags, virtual
tags, dependencies, annotations, urgency), its placement (below or right of the report, toggled with z and \\,
automatic by terminal width) and its scrolling (Control+E, Control+Y).
"""
from spec_core import *
from spec_data import MAIN, TRIO

TASKS = [(1, 'Pay rent'), (2, 'Write report'), (3, 'Call plumber'), (4, 'Review PR'), (5, 'Buy groceries'),
         (6, 'Plan trip'), (8, 'Read book'), (9, 'Fix bike'), (10, 'Water plants'), (11, 'Learn piano'),
         (12, 'Team lunch')]


def details_episode():
    cps = [step(f'task-{tid}', f'Select task {tid} ({description}).', jump(tid),
                [('details', f'The details pane shows the information of {description}: its fields, dates with '
                             'their age, tags, virtual tags, dependencies, annotations and urgency.', scr('details'))])
           for tid, description in TASKS]
    cps += [
        step('after-annotate', 'Annotate task 6 with "pack light".', jump(6) + [key('A'), typ('pack light'),
                                                                              key('Enter')],
             [('details', 'The details show the new annotation under the description.', scr('details'))]),
        step('after-start', 'Start task 2.', jump(2) + K('s'),
             [('details', 'The details show the start date and the ACTIVE virtual tag.', scr('details'))]),
        step('after-modify', 'Give task 12 the project Social and priority L.', jump(12) + modify('project:Social '
                                                                                                    'priority:L'),
             [('details', 'The details show the new project and priority.', scr('details'))]),
        step('added', 'Add the task "Fresh idea" due tomorrow.', add('Fresh idea', 'due:tomorrow'),
             [('details', 'The details of the new, selected task show its due date.', scr('details'))]),
    ]
    return program('details', 'details', fixture(MAIN), fresh(cps), names=['Fresh idea'])


def layout_episode():
    layout = lambda text: ('layout', text, scr('layout'))
    wide = {'resize': [180, 36]}
    cps = [
        step('initial', 'Observe the screen at 120 columns.', [],
             [layout('The details pane is below the report.')]),
        step('zoom', 'Press z.', K('z'), [layout('z hides the details pane.'),
                                           ('rows', 'The report still lists the tasks.', scr('rows'))],
             depends=['initial']),
        step('unzoom', 'Press z twice.', K('z', 'z'), [layout('z shows the details pane again.')], depends=['zoom']),
        step('transpose', 'Press \\.', K('\\'), [layout('\\ moves the details to the right of the report.')],
             depends=['initial']),
        step('transpose-back', 'Press \\ twice.', K('\\', '\\'), [layout('The details are below the report again.')],
             depends=['transpose']),
        step('wide', 'Widen the terminal to 180 columns.', [wide],
             [layout('On a terminal wider than 160 columns the details are placed to the right.')],
             depends=['initial']),
        step('wide-transpose', 'Press \\.', K('\\'), [layout('\\ moves them below the report.')], depends=['wide']),
        step('narrow', 'Widen the terminal to 180 columns and return it to 120 columns.', [wide, {'resize': [120, 36]}],
             [layout('Back at 120 columns, the automatic placement is below again.')], depends=['wide']),
    ]
    for cp in cps[1:]:
        if cp['id'] != 'wide-transpose':
            cp['lifecycle'] = 'restart'
    return program('details-layout', 'details', fixture(MAIN), cps)


def scroll_episode():
    text = lambda req: ('text', req, scr('details_text', first=3))
    cps = [
        step('initial', 'Select task 5 (Buy groceries).', jump(5), [text('The details start at their first line.')]),
        step('down', 'Press Control+E twice.', K('Control+e', 'Control+e'),
             [text('The details scroll down by two lines.')], depends=['initial']),
        step('up', 'Press Control+Y once.', K('Control+y'), [text('The details scroll back up by one line.')],
             depends=['down']),
    ]
    return program('details-scroll', 'details', fixture(MAIN), cps)


def options_episode():
    items = [
        ('hidden', {'tasks': MAIN, 'config': [('uda.taskwarrior-tui.task-report.info-show', 'false')]},
         'Observe the application started with info-show false, then press z.', [],
         [('layout', 'With info-show false the details pane starts hidden.', scr('layout'))]),
        ('hidden-z', {'tasks': MAIN, 'config': [('uda.taskwarrior-tui.task-report.info-show', 'false')]},
         'With info-show false, press z.', K('z'),
         [('layout', 'z shows the details pane.', scr('layout'))]),
        ('right', {'tasks': MAIN, 'config': [('uda.taskwarrior-tui.task-report.info-location', 'right')]},
         'Observe the application started with info-location right.', [],
         [('layout', 'The details pane is to the right even at 120 columns.', scr('layout'))]),
        ('bottom-wide', {'tasks': MAIN, 'config': [('uda.taskwarrior-tui.task-report.info-location', 'bottom')]},
         'With info-location bottom, widen the terminal to 180 columns.', [{'resize': [180, 36]}],
         [('layout', 'The details pane stays below the report.', scr('layout'))]),
        ('legacy', {'tasks': MAIN, 'config': [('uda.taskwarrior-tui.tasklist.vertical', 'false')]},
         'Observe the application started with the legacy tasklist.vertical false.', [],
         [('layout', 'The legacy setting false places the details to the right.', scr('layout'))]),
        ('auto-wide', {'tasks': MAIN}, 'Without a setting, widen the terminal to 180 columns.', [{'resize': [180, 36]}],
         [('layout', 'The automatic placement puts the details to the right.', scr('layout'))]),
    ]
    wf = cases('details-options', 'details', items)
    bind = {'hidden': 'hidden-z/layout', 'bottom-wide': 'auto-wide/layout'}
    for cp in wf['checkpoints']:
        if cp['id'] in bind:
            for a in cp['assertions']:
                a['requires'] = ['details-options/' + bind[cp['id']]]
    return wf


def narrow_episode():
    cps = [
        step('w80', 'Resize the terminal to 80 columns by 24 rows.', [{'resize': [80, 24]}],
             [('headers', 'At 80 columns the report keeps its columns with narrower widths.', scr('headers')),
              ('count', 'The report pane shows as many tasks as fit above the details pane.', scr('count')),
              ('layout', 'The details pane stays below the report.', scr('layout'))]),
        step('w60', 'Resize the terminal to 60 columns by 20 rows.', [{'resize': [60, 20]}],
             [('headers', 'At 60 columns the column labels are cut to the column widths.', scr('headers')),
              ('count', 'Fewer tasks fit in the shorter report pane.', scr('count'))], lifecycle='restart'),
        step('w60-prompt', 'Open the add prompt.', K('a'),
             [('prompt', 'The prompt still uses the last two rows with its title and quotes.', scr('prompt'))],
             depends=['w60']),
    ]
    return program('details-narrow', 'details', fixture(MAIN), cps)


WIDE = [T(31, '日本語のメモ', entry='20260410T080000Z', project='旅行', tags=['重要']),
        T(32, 'Café ☕ break', entry='20260411T080000Z', project='Home'),
        T(33, '中文 任务 列表', entry='20260412T080000Z', tags=['工作'], priority='M')]


def wide_episode():
    names = [t['description'] for t in WIDE + TRIO]
    cps = [
        step('report', 'Observe the report with descriptions, projects and tags in wide characters.', [],
             [('cells', 'The Project column lines up although wide characters take two cells.',
               scr('cells', label='Project'))]),
        step('details', 'Select task 4 (日本語のメモ).', jump(4),
             [('details', 'The details pane shows the wide-character description, project and tags.',
               scr('details', keys=['ID', 'Description', 'Project', 'Tags']))]),
    ]
    return program('details-wide', 'details', fixture(TRIO + WIDE), cps, names=names)


def episodes():
    return [details_episode(), layout_episode(), scroll_episode(), options_episode(), narrow_episode(),
            wide_episode()]

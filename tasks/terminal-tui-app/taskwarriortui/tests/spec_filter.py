"""The live filter (/): Taskwarrior filter expressions replace the report's filter and the report lists the matching
tasks by urgency; the prompt's own behaviour (live update, Enter, Escape, Ctrl+R, no match, invalid filter).

Every expression checkpoint starts from a restarted application and replaces the whole filter (Ctrl+U clears the
prompt), so the checkpoints are independent. The main fixture's tasks all have distinct urgencies, so the listed order
is deterministic.
"""
from spec_core import *
from spec_data import MAIN

EXPRESSIONS = [
    # attributes and their modifiers
    ('project', 'project:Home'), ('project-sub', 'project:Home.Repairs'), ('project-abbrev', 'pro:Work'),
    ('project-is', 'project.is:Home'), ('project-not', 'project.not:Home'), ('project-has', 'project.has:o'),
    ('project-hasnt', 'project.hasnt:o'), ('project-startswith', 'project.startswith:Wo'),
    ('project-endswith', 'project.endswith:ode'), ('project-none', 'project.none:'), ('project-any', 'project.any:'),
    ('project-empty', 'project:'),
    ('tag', '+bills'), ('not-tag', '-bills'), ('two-tags', '+shop +errand'), ('tags-has', 'tags.has:garden'),
    ('tags-hasnt', 'tags.hasnt:shop'), ('tags-any', 'tags.any:'), ('tags-none', 'tags.none:'),
    ('priority-h', 'priority:H'), ('priority-l', 'priority:L'), ('priority-abbrev', 'pri:M'),
    ('priority-none', 'priority.none:'), ('priority-any', 'priority.any:'), ('priority-above', 'priority.above:L'),
    ('priority-below', 'priority.below:H'), ('priority-not', 'priority.not:L'),
    ('due-before', 'due.before:tomorrow'), ('due-after', 'due.after:today'), ('due-by', 'due.by:eow'),
    ('due-before-now', 'due.before:now'), ('due-equal', 'due:tomorrow'), ('due-none', 'due.none:'),
    ('due-any', 'due.any:'), ('due-iso', 'due.before:2026-05-14T12:00'), ('due-under', 'due.under:eom'),
    ('scheduled-any', 'scheduled.any:'), ('wait-any', 'wait.any:'), ('until-any', 'until.any:'),
    ('entry-before', 'entry.before:2026-05-01'), ('entry-after', 'entry.after:2026-05-05'),
    ('end-any', 'end.any:'), ('start-any', 'start.any:'), ('depends-any', 'depends.any:'),
    ('urgency-over', 'urgency.over:10'), ('urgency-under', 'urgency.under:2'),
    # status
    ('status-pending', 'status:pending'), ('status-completed', 'status:completed'),
    ('status-deleted', 'status:deleted'), ('status-waiting', 'status:waiting'),
    # virtual tags
    ('overdue', '+OVERDUE'), ('due-tag', '+DUE'), ('duetoday', '+DUETODAY'), ('today', '+TODAY'),
    ('tomorrow', '+TOMORROW'), ('week', '+WEEK'), ('month', '+MONTH'), ('year', '+YEAR'), ('active', '+ACTIVE'),
    ('blocked', '+BLOCKED'), ('blocking', '+BLOCKING'), ('unblocked', '+UNBLOCKED'), ('ready', '+READY'),
    ('scheduled-tag', '+SCHEDULED'), ('waiting-tag', '+WAITING'), ('annotated', '+ANNOTATED'),
    ('tagged', '+TAGGED'), ('not-tagged', '-TAGGED'), ('project-tag', '+PROJECT'), ('priority-tag', '+PRIORITY'),
    ('pending-tag', '+PENDING'), ('completed-tag', '+COMPLETED'), ('deleted-tag', '+DELETED'),
    ('until-tag', '+UNTIL'), ('latest', '+LATEST'),
    # description and identifiers
    ('word', 'bike'), ('word-case', 'Bike'), ('regex', '/plum/'), ('desc-startswith', 'description.startswith:Re'),
    ('desc-endswith', 'description.endswith:t'), ('desc-has', 'description.has:o'),
    ('desc-word', 'description.word:book'), ('desc-noword', 'description.noword:book'), ('id', 'id:3'),
    ('bare-id', '3'), ('id-range', '1-3'), ('id-list', '1,4'), ('uuid', '00000004'),
    # boolean combinations
    ('or', 'project:Home or project:Work'), ('and', 'project:Home and +bills'), ('xor', 'project:Home xor +bills'),
    ('parentheses', '(+shop or +bills) and priority:L'), ('implicit-and', 'project:Work +social'),
    ('or-tags', '+shop or +bills'), ('mixed', '+PROJECT -TAGGED'),
]


def expressions_episode():
    cps = [step(cid, f'Filter the report with: {expr}', filt(expr),
                [('rows', f'Exactly the tasks matching {expr} are listed, by urgency.', scr('rows'))])
           for cid, expr in EXPRESSIONS]
    wf = program('filter-expressions', 'filter', fixture(MAIN), fresh(cps))
    return bind(wf, {'word-case': ['word/rows']})


def prompt_episode():
    fx = {'tasks': MAIN}
    items = [
        ('open', fx, 'Press /.', K('/'),
         [('prompt', 'The filter prompt shows the next report\'s filter.', scr('prompt'))]),
        ('live', None, 'Clear the prompt and type project:Work status:pending without pressing Enter.',
         [key('Control+u'), typ('project:Work status:pending')],
         [('rows', 'The report already lists only the matching tasks while typing.', scr('rows')),
          ('prompt', 'The prompt shows the typed filter.', scr('prompt'))], ['open']),
        ('enter', None, 'Press Enter.', K('Enter'),
         [('rows', 'The filter stays applied.', scr('rows')),
          ('prompt', 'The prompt closes; the filter line shows the filter.', scr('prompt')),
          ('selected', 'The first matching task is selected.', scr('selected'))], ['live']),
        ('action', None, 'Complete the selected task (d) with the filter applied.', K('d'),
         [('rows', 'The report keeps the filter after the change; the completed task leaves it.', scr('rows')),
          ('task', 'The selected task is completed.', ex(['Review PR'], 'status'))], ['enter']),
        ('escape', fx, 'Filter with project:Work status:pending, then open the filter prompt and press Escape.',
         filt('project:Work status:pending') + K('/', 'Escape'),
         [('rows', 'Escape resets the filter to the report\'s own filter.', scr('rows')),
          ('prompt', 'The filter line shows the report\'s filter again.', scr('prompt'))], ['enter']),
        ('ctrl-r', fx, 'Open the prompt, replace the filter by +bills and press Control+R.',
         [key('/'), key('Control+u'), typ('+bills'), key('Control+r')],
         [('prompt', 'Control+R restores the report\'s filter in the prompt.', scr('prompt')),
          ('rows', 'The report lists the tasks of the report\'s filter.', scr('rows'))], ['live']),
        ('nothing', fx, 'Filter with project:Nowhere.', filt('project:Nowhere'),
         [('rows', 'No task is listed.', scr('rows')),
          ('details', 'The details pane says that no task is found.', scr('details_text', first=1))], ['enter']),
        ('invalid', fx, 'Filter with due.before:zzz.', filt('due.before:zzz'),
         [('error', 'An error popup reports the invalid date.', scr('error', mentions=['zzz']))]),
        ('after-error', None, 'Dismiss the error with j and filter with +garden.', K('j') + filt('+garden'),
         [('rows', 'Filtering works again.', scr('rows'))], ['invalid']),
        ('empty', fx, 'Filter with an empty filter.', filt(''),
         [('rows', 'Every task is listed, including completed and deleted ones, by urgency.', scr('rows'))],
         ['enter']),
    ]
    return cases('filter-prompt', 'filter', items)


def episodes():
    return [expressions_episode(), prompt_episode()]

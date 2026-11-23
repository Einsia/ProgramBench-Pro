"""The application's Taskwarrior command line (the task operation): counts, DOM queries, exports with filters, the
feedback of the commands that change tasks, confirmations (also answered on standard input), errors, configuration
and context commands, the text reports and their columns, task information, the charts, calendar and timesheet,
metadata listings and the helper commands.

Each checkpoint runs one command and reads its recorded result: the exit status and the output lines (whitespace
squashed), the exported task descriptions, or the error output. Text output is produced for a width of 120 columns
and a height of 40 rows (rc.defaultwidth, rc.defaultheight), since the command runs without a terminal.
"""
from spec_core import *
from spec_data import MAIN
from spec_reports import CUSTOM
from spec_taskwarrior import INSTANCE, TEMPLATE

C = 'rc.confirmation=off'


def run_step(cid, goal, args, requirement, project='lines', stdin=None, extra=(), depends=(), **kw):
    return step(cid, goal, [cmd(*args, stdin=stdin, keep=True)], [('output', requirement, ran(project, **kw))]
                + list(extra), depends=depends)


def queries_episode():
    cps = [
        run_step('count', 'Run: task count', ['count'], 'count prints the number of tasks (every status).'),
        run_step('count-pending', 'Run: task status:pending count', ['status:pending', 'count'],
                 'count honours a filter.'),
        run_step('count-tag', 'Run: task +bills count', ['+bills', 'count'], 'count with a tag filter.'),
        run_step('get-description', 'Run: task _get 1.description', ['_get', '1.description'],
                 '_get prints the description of task 1.'),
        run_step('get-project', 'Run: task _get 3.project', ['_get', '3.project'], '_get prints a project.'),
        run_step('get-due', 'Run: task _get 1.due', ['_get', '1.due'], '_get prints a date in ISO form.'),
        run_step('get-tags', 'Run: task _get 5.tags', ['_get', '5.tags'], '_get prints the tags joined by commas.'),
        run_step('get-config', 'Run: task _get rc.report.next.filter', ['_get', 'rc.report.next.filter'],
                 '_get reads configuration values.'),
        run_step('projects', 'Run: task _projects', ['_projects'], '_projects lists the projects of pending tasks.'),
        run_step('ids', 'Run: task _ids', ['_ids'], '_ids lists the IDs of the working set.'),
        run_step('version', 'Run: task --version', ['--version'], '--version prints the version.'),
        run_step('export-filter', 'Run: task project:Home rc.json.array=on export', ['project:Home', 'rc.json.array=on',
                                                                                   'export'],
                 'export honours a filter.', project='json'),
        run_step('export-report', 'Run: task rc.json.array=on export blocked', ['rc.json.array=on', 'export',
                                                                              'blocked'],
                 'export with a report name applies the report\'s filter.', project='json'),
        run_step('export-lines', 'Run: task rc.json.array=off status:completed export',
                 ['rc.json.array=off', 'status:completed', 'export'],
                 'Without json.array every task is one JSON object on its own line.', project='json'),
        run_step('unknown-id', 'Run: task 99 done', ['99', 'done'], 'A missing task ID is an error with a message.',
                 project='stderr', mentions=['No tasks specified.']),
        run_step('export-filter-report', 'Run: task +bills rc.json.array=on export next',
                 ['+bills', 'rc.json.array=on', 'export', 'next'],
                 'A filter before export combines with the named report\'s filter.', project='json'),
    ]
    return program('cli-queries', 'cli', fixture(MAIN), cps)


def item(cid, fx, goal, args, requirement, project='lines', stdin=None, extra=(), depends=(), **kw):
    """One command-line checkpoint for cases(): its own fixture (or None to continue), one kept run, its checks."""
    return (cid, fx, goal, [cmd(*args, stdin=stdin, keep=True)],
            [('output', requirement, ran(project, **kw))] + list(extra), list(depends))


def changes_episode():
    fx = {'tasks': MAIN}
    items = [
        item('add', fx, 'Run: task add CLI added +cli', ['add', 'CLI added', '+cli'], 'add reports the new task\'s ID.',
             extra=[('task', 'The task is stored.', ex(['CLI added'], 'tags'))]),
        item('modify', fx, 'Run: task 2 modify +viacli', ['2', 'modify', '+viacli'],
             'modify reports the task it changes and the count.'),
        item('annotate', fx, 'Run: task 1 annotate cli note', ['1', 'annotate', 'cli note'],
             'annotate reports the task and the count.'),
        item('start', fx, 'Run: task 8 start', ['8', 'start'], 'start reports the task and the count.'),
        item('stop', None, 'Run: task 8 stop', ['8', 'stop'], 'stop reports the task and the count.', depends=['start']),
        item('duplicate', fx, f'Run: task {C} 10 duplicate', [C, '10', 'duplicate'],
             'duplicate reports the copy\'s new ID.'),
        item('delete-ask', fx, 'Run: task 6 delete (without a terminal to confirm)', ['6', 'delete'],
             'delete asks for confirmation; without an answer nothing is deleted.', project='result',
             extra=[('task', 'The task stays pending.', ex(['Plan trip'], 'status'))]),
        item('delete', fx, f'Run: task {C} 6 delete', [C, '6', 'delete'], 'With confirmation off the task is deleted.',
             project='result', extra=[('task', 'The task is deleted.', ex(['Plan trip'], 'status'))]),
        item('done', fx, 'Run: task 3 done', ['3', 'done'], 'done reports the completed task and the count.'),
        item('log', fx, 'Run: task log CLI logged', ['log', 'CLI logged'], 'log stores a completed task.',
             project='exit', extra=[('task', 'The task is completed.', ex(['CLI logged'], 'status'))]),
        item('append', fx, 'Run: task 2 append quickly', ['2', 'append', 'quickly'],
             'append reports the task with its new description and the count.',
             extra=[('task', 'The word is appended to the description.', ex(['Write report quickly'], 'status'))]),
        item('prepend', fx, 'Run: task 3 prepend Urgently', ['3', 'prepend', 'Urgently'],
             'prepend reports the task with its new description and the count.',
             extra=[('task', 'The word is put before the description.', ex(['Urgently Call plumber'], 'status'))]),
        item('denotate', fx, 'Run: task 8 denotate Chapter', ['8', 'denotate', 'Chapter'],
             'denotate reports the annotation it found by its start and deleted.',
             extra=[('task', 'The annotation is gone.', ex(['Read book'], 'annotations'))]),
        item('purge', fx, f'Run: task {C} {U(11)} purge', [C, U(11), 'purge'],
             'purge reports how many deleted tasks it removed.',
             extra=[('tasks', 'The deleted task is removed entirely.', summary())]),
        item('purge-refused', fx, f'Run: task {C} {U(10)} purge (a completed task)', [C, U(10), 'purge'],
             'Only deleted tasks are purged; a completed one is kept.', project='result',
             extra=[('tasks', 'Nothing is removed.', summary())]),
        item('undo-ask', fx, 'Run: task 2 modify +undoable, then task undo (without a terminal to confirm)',
             ['undo'], 'undo lists the operations it would revert; without an answer it reverts nothing.',
             project='result', extra=[('task', 'The change stays.', ex(['Write report'], 'tags'))]),
        item('undo', fx, f'Run: task 2 modify +undoable, then task {C} undo', [C, 'undo'],
             'With confirmation off, undo reverts the last command.',
             extra=[('task', 'The tag is removed again.', ex(['Write report'], 'tags'))]),
    ]
    for it in items:
        if it[0] in ('undo-ask', 'undo'):
            it[3].insert(0, cmd(C, '2', 'modify', '+undoable'))
    wf = cases('cli-changes', 'cli', items, names=['CLI added', 'CLI logged', 'Write report quickly',
                                                    'Urgently Call plumber'])
    return bind(wf, {'delete-ask': ['delete/task'], 'purge-refused': ['purge/tasks'], 'undo-ask': ['undo/task'],
                     'undo/task': ['undo/output'], 'log/output': ['log/task']})


def config_episode():
    cps = [
        run_step('config-ask', 'Run: task config foo.bar baz (without a terminal to confirm)', ['config', 'foo.bar', 'baz'],
                 'config asks for confirmation; without an answer nothing changes.', project='result'),
        run_step('config-set', f'Run: task {C} config foo.bar baz', [C, 'config', 'foo.bar', 'baz'],
                 'With confirmation off the setting is stored.', project='result',
                 extra=[('value', 'The value is stored.', cli('_get', 'rc.foo.bar'))]),
        run_step('config-remove', f'Run: task {C} config foo.bar', [C, 'config', 'foo.bar'],
                 'config without a value removes the setting.', project='result',
                 extra=[('value', 'The value is gone.', cli('_get', 'rc.foo.bar'))], depends=['config-set']),
        run_step('context-define', f'Run: task {C} context define focus project:Work',
                 [C, 'context', 'define', 'focus', 'project:Work'],
                 'context define stores a read and a write filter.', project='result'),
        run_step('context-list', 'Run: task context list', ['context', 'list'], 'context list shows the contexts.',
                 depends=['context-define']),
        run_step('context-set', 'Run: task context focus', ['context', 'focus'], 'context NAME activates it.',
                 project='exit', extra=[('value', 'The context setting is stored.', cli('_get', 'rc.context'))],
                 depends=['context-define']),
        run_step('context-show', 'Run: task context show', ['context', 'show'], 'context show describes the active '
                                                                               'context.', depends=['context-set']),
        run_step('context-add', 'Run: task add In focus', ['add', 'In focus'], 'add applies the context\'s write '
                                                                             'filter.', project='exit',
                 extra=[('task', 'The task gets the project Work.', ex(['In focus'], 'project'))],
                 depends=['context-set']),
        run_step('context-none', 'Run: task context none', ['context', 'none'], 'context none deactivates it.',
                 project='exit', extra=[('value', 'The context setting is cleared.', cli('_get', 'rc.context'))],
                 depends=['context-set']),
    ]
    wf = program('cli-config', 'cli', fixture(MAIN), cps, names=['In focus'])
    for cp in wf['checkpoints']:
        if cp['id'] == 'config-ask':
            for a in cp['assertions']:
                a['requires'] = ['cli-config/config-set/value']
    return wf


W = ['rc.defaultwidth=120', 'rc.defaultheight=40']
LISTED = dict(tasks=MAIN + [TEMPLATE, INSTANCE], config=CUSTOM)
REPORTS = ['next', 'list', 'long', 'ls', 'minimal', 'newest', 'oldest', 'active', 'blocked', 'blocking', 'unblocked',
           'ready', 'recurring', 'waiting', 'completed', 'all', 'overdue']


def reports_episode():
    cps = [run_step(name, f'Run: task {name}', W + [name], f'The {name} report prints its columns, labels, tasks and '
                                                                 'footnote as text.') for name in REPORTS]
    cps.append(run_step('custom', 'Run: task mine (a report defined in the configuration)', W + ['mine'],
                        'A report defined in the configuration prints its own columns, labels, filter and sort.'))
    return program('cli-reports', 'cli', fixture(**LISTED), cps)


def information_episode():
    cases_ = [('plain', '2', 'a plain task'), ('annotated', '8', 'an annotated task'), ('blocked', '9', 'a blocked task'),
              ('active', '4', 'an active task with priority and tags'), ('completed', U(10), 'a completed task'),
              ('instance', '14', 'a recurring instance')]
    cps = [run_step(cid, f'Run: task {ref} information', W + [ref, 'information'],
                    f'information prints the fields, virtual tags, urgency terms and history of {what}.')
           for cid, ref, what in cases_]
    return program('cli-information', 'cli', fixture(**LISTED), cps)


def metadata_episode():
    config = [('uda.estimate.type', 'numeric'), ('context.home.read', 'project:Home')]
    listing = [('tags', ['tags'], 'tags lists the tags with their counts.'),
               ('projects', ['projects'], 'projects lists the projects and subprojects with their counts.'),
               ('summary', ['summary'], 'summary lists remaining tasks, average age and completion per project.'),
               ('udas', ['udas'], 'udas lists the user-defined attributes with their type, values and usage.'),
               ('columns', ['columns'], 'columns lists every column with its formats and examples.'),
               ('show', ['show', 'urgency'], 'show lists the configuration variables that match, with their values.'),
               ('reports', ['reports'], 'reports lists the reports with their descriptions.'),
               ('commands', ['commands'], 'commands lists every command with its category and behaviour.'),
               ('help', ['help'], 'help prints the usage of every command.'),
               ('version', ['version'], 'version prints the version, copyright and documentation note.')]
    cps = [run_step(cid, f'Run: task {" ".join(args)}', W + args, req) for cid, args, req in listing]
    cps.append(run_step('stats', 'Run: task stats', W + ['stats'],
                        'stats prints the counts, dates and averages of the task data.',
                        drop=['Undo transactions', 'Sync backlog transactions']))
    return program('cli-metadata', 'cli', fixture(tasks=MAIN + [TEMPLATE, INSTANCE], config=config), cps)


CHARTS = ['history.daily', 'history.weekly', 'history.monthly', 'history.annual', 'ghistory.daily', 'ghistory.weekly',
          'ghistory.monthly', 'ghistory.annual', 'burndown.daily', 'burndown.weekly', 'burndown.monthly']


def charts_episode():
    cps = [run_step(name, f'Run: task {name}', W + [name], f'{name} charts the task history as text.')
           for name in CHARTS]
    cps += [run_step('calendar', 'Run: task calendar', W + ['calendar'],
                     'calendar prints the current and following months with week numbers.'),
            run_step('calendar-year', 'Run: task calendar 2026', W + ['calendar', '2026'],
                     'calendar YEAR prints the twelve months of the year.'),
            run_step('timesheet', 'Run: task timesheet', W + ['timesheet'],
                     'timesheet lists the tasks completed and started this week.')]
    return program('cli-charts', 'cli', fixture(MAIN), cps)


def helpers_episode():
    config = [('uda.estimate.type', 'numeric'), ('context.home.read', 'project:Home')]
    helpers = [('calc-arithmetic', ['calc', '1+2*3'], 'calc evaluates arithmetic.', 'lines'),
               ('calc-date', ['calc', 'now+1d'], 'calc evaluates date expressions.', 'lines'),
               ('calc-duration', ['calc', 'eom-som'], 'calc prints the difference of two dates as a duration.',
                'lines'),
               ('ids', ['ids'], 'ids prints the IDs of the working set as ranges.', 'lines'),
               ('uuids', ['uuids'], 'uuids prints the UUIDs of every task on one line.', 'lines'),
               ('tags', ['_tags'], '_tags lists the virtual and user tags.', 'lines'),
               ('unique', ['_unique', 'project'], '_unique lists the distinct values of an attribute.', 'lines'),
               ('urgency', ['_urgency'], '_urgency prints the urgency of every task.', 'sorted'),
               ('uuid-list', ['_uuids'], '_uuids lists the UUIDs of every task.', 'lines'),
               ('zshids', ['_zshids'], '_zshids lists ID and description pairs.', 'sorted'),
               ('zshuuids', ['_zshuuids'], '_zshuuids lists UUID and description pairs.', 'sorted'),
               ('aliases', ['_aliases'], '_aliases lists the command aliases.', 'lines'),
               ('columns', ['_columns'], '_columns lists the column names.', 'lines'),
               ('commands', ['_commands'], '_commands lists the command names.', 'lines'),
               ('config', ['_config'], '_config lists the configuration variable names.', 'lines'),
               ('context', ['_context'], '_context lists the defined contexts.', 'lines'),
               ('udas', ['_udas'], '_udas lists the user-defined attributes.', 'lines'),
               ('version', ['_version'], '_version prints the version number.', 'lines'),
               ('show', ['_show'], '_show prints every configuration setting as name=value (the data location, a '
                                   'path of the installation, is not compared).', 'lines'),
               ('zshattributes', ['_zshattributes'], '_zshattributes lists the attribute names.', 'lines'),
               ('zshcommands', ['_zshcommands'], '_zshcommands lists the commands with their categories.', 'lines')]
    cps = [run_step(cid, f'Run: task {" ".join(args)}', args, req, project=project,
                    **({'drop': ['data.location=']} if cid == 'show' else {}))
           for cid, args, req, project in helpers]
    return program('cli-helpers', 'cli', fixture(tasks=MAIN + [TEMPLATE, INSTANCE], config=config), cps)


def confirm_episode():
    fx = {'tasks': MAIN}
    recurring = {'tasks': MAIN + [TEMPLATE, INSTANCE]}
    items = [
        item('bulk-answers', fx, 'Run: task rc.bulk=2 project:Work modify +bulk, answering yes, no and yes',
             ['rc.bulk=2', 'project:Work', 'modify', '+bulk'], 'Each task is confirmed on its own: yes, no, yes.',
             stdin='yes\nno\nyes\n', project='result',
             extra=[('tasks', 'Only the confirmed tasks get the tag.', ex(['Write report', 'Review PR', 'Team lunch'],
                                                                          'tags'))]),
        item('bulk-all', fx, 'Run: task rc.bulk=2 +shop or +bills or +garden modify priority:M, answering all',
             ['rc.bulk=2', '+shop', 'or', '+bills', 'or', '+garden', 'modify', 'priority:M'],
             'all confirms the remaining tasks at once.', stdin='all\n', project='result',
             extra=[('tasks', 'Every matching task gets the priority.',
                     ex(['Buy groceries', 'Pay rent', 'Water plants'], 'priority'))]),
        item('bulk-quit', fx, 'Run: task rc.bulk=2 project:Travel or project:Music delete, answering quit',
             ['rc.bulk=2', 'project:Travel', 'or', 'project:Music', 'delete'], 'quit stops before any task changes.',
             stdin='quit\n', project='result',
             extra=[('tasks', 'Nothing is deleted.', ex(['Plan trip', 'Renew passport', 'Learn piano'], 'status'))]),
        item('delete-answers', fx, 'Run: task 1 2 delete, answering yes twice', ['1', '2', 'delete'],
             'delete asks for each task; yes deletes it.', stdin='yes\nyes\n', project='result',
             extra=[('tasks', 'Both tasks are deleted.', ex(['Pay rent', 'Write report'], 'status'))]),
        item('recurring-delete', recurring, 'Run: task 13 delete (the recurring template), answering yes twice',
             ['13', 'delete'], 'Deleting a recurring task also asks whether to delete its pending recurrences.',
             stdin='yes\nyes\n', project='result',
             extra=[('tasks', 'The template and its pending instance are deleted.',
                     ex(['Weekly sync'], 'status', 'end'))]),
    ]
    wf = cases('cli-confirm', 'cli', items)
    return bind(wf, {'bulk-quit': ['bulk-all/tasks']})


def contexts_episode():
    items = [
        item('define', {'tasks': MAIN}, f'Run: task {C} context define home project:Home',
             [C, 'context', 'define', 'home', 'project:Home'], 'context define reports the read and write filters.'),
        item('show-write', None, 'Run: task context home, then task context show', ['context', 'show'],
             'context show prints the read and the write filter of the active context.', depends=['define']),
        item('redefine', None, f'Run: task {C} context define home +bills, then task context show',
             ['context', 'show'], 'Defining an existing context again replaces both filters.', depends=['show-write']),
        item('delete', None, f'Run: task {C} context delete home, then task context list', ['context', 'list'],
             'context delete removes the context; context list then fails with the message that none is defined.',
             project='stderr', mentions=['No contexts defined.'],
             extra=[('setting', 'The deleted context is no longer active.', cli('_get', 'rc.context'))],
             depends=['redefine']),
    ]
    items[1][3].insert(0, cmd('context', 'home'))
    items[2][3].insert(0, cmd(C, 'context', 'define', 'home', '+bills'))
    items[3][3].insert(0, cmd(C, 'context', 'delete', 'home'))
    return cases('cli-contexts', 'cli', items)


def episodes():
    return [queries_episode(), changes_episode(), config_episode(), reports_episode(), information_episode(),
            metadata_episode(), charts_episode(), helpers_episode(), confirm_episode(), contexts_episode()]

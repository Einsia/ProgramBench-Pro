"""Adding and logging tasks through the add (a) and log (l) prompts: descriptions, attributes and date expressions.

Every checkpoint adds one task with a description of its own and starts from a restarted application (so no error
popup or rejected prompt text carries over); the check reads that task back from `task export`. Rejected input (an
invalid date, priority or recurrence) shows an error popup and creates nothing; those checkpoints start from a fresh
fixture and each is bound to a positive point of the same rule.
"""
from spec_core import *
from spec_data import TRIO

# Date expressions accepted by the due attribute (clock: Wednesday 2026-05-13 10:00:00 UTC); wed, may and 13th name
# today's weekday, month and day, eoy+1d and soy-1d cross a year boundary.
DATES = [
    ('now', 'now'), ('today', 'today'), ('eod', 'eod'), ('yesterday', 'yesterday'),
    ('tomorrow', 'tomorrow'), ('sow', 'sow'), ('eow', 'eow'), ('soww', 'soww'), ('eoww', 'eoww'), ('som', 'som'),
    ('eom', 'eom'), ('soq', 'soq'), ('eoq', 'eoq'), ('soy', 'soy'), ('eoy', 'eoy'), ('sopd', 'sopd'), ('eopd', 'eopd'),
    ('sopw', 'sopw'), ('eopw', 'eopw'), ('sopm', 'sopm'), ('eopm', 'eopm'), ('sopq', 'sopq'), ('eopq', 'eopq'),
    ('sopy', 'sopy'), ('eopy', 'eopy'), ('monday', 'monday'), ('sunday', 'sunday'), ('wed', 'wed'),
    ('this-month', 'may'), ('this-day', '13th'), ('eoy-plus', 'eoy+1d'), ('soy-minus', 'soy-1d'), ('january', 'january'),
    ('feb', 'feb'), ('june', 'june'), ('december', 'december'), ('1st', '1st'), ('2nd', '2nd'), ('3rd', '3rd'),
    ('15th', '15th'), ('31st', '31st'), ('later', 'later'), ('easter', 'easter'),
    ('eastermonday', 'eastermonday'), ('ascension', 'ascension'), ('pentecost', 'pentecost'),
    ('goodfriday', 'goodfriday'), ('midsommar', 'midsommar'), ('midsommarafton', 'midsommarafton'),
    ('iso-date', '2026-06-01'), ('iso-minute', '2026-06-01T12:30'), ('iso-utc', '2026-06-01T12:30:15Z'),
    ('iso-offset', '2026-06-01T12:00:00+02:00'), ('iso-week', '2026-W25'), ('days', '3d'), ('weeks', '3w'),
    ('wk', '2wk'), ('months', '1mo'), ('quarters', '1q'), ('years', '1y'), ('hours', '10h'), ('minutes', '30min'),
    ('seconds', '90s'), ('minus-days', '-2d'), ('minus-week', '-1w'), ('now-plus', 'now+1h'),
    ('today-plus', 'today+3d'), ('eom-minus', 'eom-1d'), ('tomorrow-minus', 'tomorrow-2h'), ('iso-p1d', 'P1D'),
    ('iso-pt2h', 'PT2H'), ('iso-p2w', 'P2W'), ('8am', '8am'), ('3pm', '3pm'), ('clock', '15:30'),
    ('clock-am', '9:00am'), ('word-week', '1week'), ('word-days', '3days'), ('word-hours', '4hours'),
    ('fortnight', 'fortnight'), ('weekly', 'weekly'), ('monthly', 'monthly'),
]

# Rejected expressions and the accepted expression of the same rule they are bound to.
BAD_DATES = [('socw', 'socw', 'sow'), ('socm', 'socm', 'som'), ('compact', '20260601', 'iso-date'),
             ('slashes', '6/1/2026', 'iso-date'), ('noon', 'noon', '3pm'), ('word', 'whenever', 'tomorrow')]


def dates_episode():
    cps = [step(cid, f'Add a task "Due {cid}" due {expr}.', add(f'Due {cid}', f'due:{expr}'),
                [('due', f'The task is due at the date "{expr}" means.', ex([f'Due {cid}'], 'status', 'due'))])
           for cid, expr in DATES]
    others = [('scheduled', 'scheduled:tomorrow', 'scheduled'), ('scheduled-iso', 'scheduled:2026-06-01', 'scheduled'),
              ('scheduled-eow', 'sched:eow', 'scheduled'), ('wait', 'wait:tomorrow', 'wait'),
              ('wait-monday', 'wait:monday', 'wait'), ('until', 'until:eoy', 'until'),
              ('until-iso', 'until:2026-12-24', 'until'), ('due-and-scheduled', 'due:eom scheduled:sow', 'due')]
    for cid, attrs, field in others:
        cps.append(step(cid, f'Add a task "Date {cid}" with {attrs}.', add(f'Date {cid}', attrs),
                        [('task', f'The task has the {field} date {attrs} gives.',
                          ex([f'Date {cid}'], 'status', 'due', 'scheduled', 'wait', 'until'))]))
    return program('add-dates', 'add', fixture([]), fresh(cps),
                   names=[f'Due {cid}' for cid, _ in DATES] + [f'Date {cid}' for cid, _, _ in others])


def bad_dates_episode():
    exprs = dict(DATES)
    items, bind = [], {}
    for cid, expr, positive in BAD_DATES:
        items.append((cid, {'tasks': TRIO}, f'Try to add a task "Bad {cid}" due {expr}.',
                      add(f'Bad {cid}', f'due:{expr}'),
                      [('error', f'"{expr}" is rejected with an error popup that names it.',
                        scr('error', mentions=[expr])),
                       ('nothing', 'No task is created.', summary())]))
        bind[cid] = 'ok-' + positive
    for positive in sorted(set(bind.values())):
        expr = exprs[positive[3:]]
        items.append((positive, {'tasks': TRIO}, f'Add a task "Good {positive}" due {expr}.',
                      add(f'Good {positive}', f'due:{expr}'),
                      [('due', f'The task is due at the date "{expr}" means.', ex([f'Good {positive}'], 'due'))]))
    wf = cases('add-bad-dates', 'add', items, names=[f'Good {p}' for p in bind.values()])
    for cp in wf['checkpoints']:
        if cp['id'] in bind:
            for a in cp['assertions']:
                a['requires'] = [f'add-bad-dates/{bind[cp["id"]]}/due']
    return wf


ATTRIBUTES = [
    # (cid, description, attributes, fields)
    ('project', 'Fix fence', 'project:Home', ('project',)),
    ('subproject', 'Plant roses', 'project:Home.Garden', ('project',)),
    ('deep-project', 'Weed beds', 'project:Home.Garden.Beds', ('project',)),
    ('project-abbrev', 'File taxes', 'pro:Finance', ('project',)),
    ('tag', 'Buy stamps', '+errand', ('tags',)),
    ('tags', 'Call bank', '+phone +finance +urgent', ('tags',)),
    ('tag-twice', 'Email Tom', '+mail +mail', ('tags',)),
    ('priority-h', 'Renew lease', 'priority:H', ('priority',)),
    ('priority-m', 'Clean desk', 'priority:M', ('priority',)),
    ('priority-l', 'Dust shelves', 'priority:L', ('priority',)),
    ('priority-abbrev', 'Wash car', 'pri:H', ('priority',)),
    ('depends', 'Ship parcel', 'depends:1', ('depends',)),
    ('depends-two', 'Close sprint', 'depends:1,3', ('depends',)),
    ('depends-range', 'Final review', 'depends:1-2', ('depends',)),
    ('start', 'Draft memo', 'start:now', ('start',)),
    ('entry', 'Old idea', 'entry:2026-01-02', ('entry',)),
    ('recur', 'Water ferns', 'recur:weekly due:friday', ('recur', 'due', 'mask', 'parent', 'imask')),
    ('recur-until', 'Take pills', 'recur:2d due:tomorrow until:2026-05-20', ('recur', 'due', 'until', 'parent')),
    ('recur-monthly', 'Pay invoice', 'recur:monthly due:2026-05-31', ('recur', 'due', 'parent')),
    ('everything', 'Book flights', 'project:Travel +trip priority:M due:2026-06-10 scheduled:2026-06-01',
     ('project', 'tags', 'priority', 'due', 'scheduled')),
    ('order', 'Pack bags', 'due:2026-06-09 +trip project:Travel', ('project', 'tags', 'due')),
]

DESCRIPTIONS = [
    # (cid, typed description, the stored description)
    ('plain', 'Buy milk', 'Buy milk'),
    ('unicode', 'Café ☕ 日本語', 'Café ☕ 日本語'),
    ('apostrophe', "Don't forget", "Don't forget"),
    ('colon', 'Meet at 10:30', 'Meet at 10:30'),
    ('plus-word', '+notatag here', '+notatag here'),
    ('attribute-word', 'Read due:never', 'Read due:never'),
    ('long', 'A rather long description that keeps going well beyond the width of most report columns here',
     'A rather long description that keeps going well beyond the width of most report columns here'),
]


def attributes_episode():
    cps = []
    for cid, description, attrs, fields in ATTRIBUTES:
        cps.append(step(cid, f'Add a task "{description}" with {attrs}.', add(description, attrs),
                        [('task', f'The new task has the attributes {attrs} sets.',
                          ex([description], 'status', *fields))]))
    for cid, typed, stored in DESCRIPTIONS:
        cps.append(step('text-' + cid, f'Add a task whose description is: {typed}', add(typed),
                        [('task', 'The description is stored as typed, without the quotes.',
                          ex([stored], 'status', 'description', 'tags', 'due'))]))
    cps.append(step('outside', 'Type the words of the description after the empty quotes: "" Buy eggs.',
                    [key('a'), key('End'), typ(' Buy eggs'), key('Enter')],
                    [('task', 'Words after the quotes become the description.', ex(['Buy eggs'], 'status'))]))
    cps.append(step('minus-word', 'Add a task "Sort photos" followed by the word -later after the quotes.',
                    add('Sort photos', '-later'),
                    [('task', 'On add, -later is not a tag removal: it becomes part of the description.',
                      ex(['Sort photos -later'], 'status', 'tags'))]))
    cps.append(step('quotes-refill', 'Delete both automatic quotes, then type: Fold laundry project:Home',
                    [key('a'), key('Delete'), key('Backspace'), typ('Fold laundry project:Home'), key('Enter')],
                    [('task', 'An emptied add prompt gets its quotes back, so all typed words form the description.',
                      ex(['Fold laundry project:Home'], 'status', 'project'))]))
    names = [d for _, d, _, _ in ATTRIBUTES] + [s for _, _, s in DESCRIPTIONS] + ['Buy eggs', 'Sort photos -later',
                                                                                  'Fold laundry project:Home']
    return program('add-attributes', 'add', fixture(TRIO), fresh(cps), names=names)


def add_screen_episode():
    fx = {'tasks': TRIO}
    items = [
        ('open', fx, 'Open the add prompt.', K('a'),
         [('prompt', 'The add prompt opens with a pair of quotes for the description.', scr('prompt'))]),
        ('typed', None, 'Type: Bake bread', [typ('Bake bread')],
         [('prompt', 'The text is typed between the quotes.', scr('prompt'))], ['open']),
        ('confirm', None, 'Move to the end, type " +food" and press Enter.', [key('End'), typ(' +food'), key('Enter')],
         [('selected', 'The new task is selected in the report.', scr('selected')),
          ('rows', 'It is listed in the report by urgency.', scr('rows')),
          ('title', 'The prompt closes and the filter line is shown again.', scr('title'))], ['typed']),
        ('escape', fx, 'Open the add prompt, type Discarded and press Escape.', [key('a'), typ('Discarded'),
                                                                                key('Escape')],
         [('tasks', 'Escape discards the prompt: no task is added.', summary()),
          ('title', 'The filter line is shown again.', scr('title'))]),
        ('reopen', None, 'Open the add prompt again.', K('a'),
         [('prompt', 'It opens empty again (with its quotes).', scr('prompt'))], ['escape']),
        ('second', fx, 'Add the task Sweep floor with priority H.', add('Sweep floor', 'priority:H'),
         [('task', 'The task is added with its priority.', ex(['Sweep floor'], 'status', 'priority', 'id')),
          ('selected', 'The new task is selected.', scr('selected'))]),
    ]
    wf = cases('add-prompt', 'add', items, names=['Bake bread', 'Discarded', 'Sweep floor'])
    return bind(wf, {'escape': ['open/prompt', 'second/task']})


def add_errors_episode():
    items = [
        ('empty', {'tasks': TRIO}, 'Open the add prompt and confirm the empty quotes.', K('a', 'Enter'),
         [('error', 'An error popup says additional text is needed.', scr('error', mentions=['text'])),
          ('nothing', 'No task is created.', summary())]),
        ('priority', {'tasks': TRIO}, 'Add "Bad priority" with priority:X.', add('Bad priority', 'priority:X'),
         [('error', 'An error popup names the rejected priority value.', scr('error', mentions=['priority', 'X'])),
          ('nothing', 'No task is created.', summary())]),
        ('priority-case', {'tasks': TRIO}, 'Add "Lower priority" with priority:h.', add('Lower priority', 'priority:h'),
         [('error', 'Priority values are case sensitive: h is rejected.', scr('error', mentions=['priority'])),
          ('nothing', 'No task is created.', summary())]),
        ('recur-no-due', {'tasks': TRIO}, 'Add "Bad recurrence" with recur:weekly and no due date.',
         add('Bad recurrence', 'recur:weekly'),
         [('error', 'An error popup says a recurring task needs a due date.', scr('error', mentions=['due'])),
          ('nothing', 'No task is created.', summary())]),
        ('recur-unit', {'tasks': TRIO}, 'Add "Bad period" with recur:fortnightly due:tomorrow.',
         add('Bad period', 'recur:fortnightly due:tomorrow'),
         [('error', 'An error popup names the unsupported period.', scr('error', mentions=['fortnightly'])),
          ('nothing', 'No task is created.', summary())]),
        ('kept', {'tasks': TRIO}, 'Add "Bad date" due:zzz, dismiss the error with a key and open the add prompt '
                                  'again.', add('Bad date', 'due:zzz') + K('k', 'a'),
         [('prompt', 'The rejected text is still in the add prompt.', scr('prompt'))]),
        ('kept-fixed', {'tasks': TRIO}, 'After a rejected add, fix the text in the prompt and confirm it.',
         add('Bad date', 'due:zzz') + K('k', 'a', 'Backspace', 'Backspace', 'Backspace') + [typ('eom'),
                                                                                           key('Enter')],
         [('task', 'The corrected task is added.', ex(['Bad date'], 'status', 'due'))]),
        ('dismiss', {'tasks': TRIO}, 'After the error popup of an empty add, press j.', K('a', 'Enter', 'j'),
         [('error', 'The key dismisses the popup.', scr('error')),
          ('title', 'The filter line is shown again.', scr('title'))]),
    ]
    items += [
        ('ok-text', {'tasks': TRIO}, 'Add the task "Plain words".', add('Plain words'),
         [('task', 'The task is added.', ex(['Plain words'], 'status'))]),
        ('ok-priority', {'tasks': TRIO}, 'Add "High priority" with priority:H.', add('High priority', 'priority:H'),
         [('task', 'The task has priority H.', ex(['High priority'], 'priority'))]),
        ('ok-recur', {'tasks': TRIO}, 'Add "Good recurrence" with recur:weekly due:friday.',
         add('Good recurrence', 'recur:weekly due:friday'),
         [('task', 'The recurring task and its first instance are created.', ex(['Good recurrence'], 'status', 'recur'))]),
    ]
    wf = cases('add-errors', 'add', items, names=['Bad date', 'Plain words', 'High priority', 'Good recurrence'])
    return bind(wf, {'empty': ['ok-text/task'], 'priority': ['ok-priority/task'], 'priority-case': ['ok-priority/task'],
                     'recur-no-due': ['ok-recur/task'], 'recur-unit': ['ok-recur/task'],
                     'dismiss': ['empty/error']})


LOGS = [
    ('plain', 'Mowed lawn', ''),
    ('project', 'Paid bills', 'project:Home +money'),
    ('dated', 'Ran 5k', 'due:yesterday'),
]


def log_episode():
    cps = [step('open', 'Open the log prompt.', K('l'),
                [('prompt', 'The log prompt opens with a pair of quotes.', scr('prompt'))]),
           step('discard', 'Press Escape.', K('Escape'), [('title', 'The filter line is shown again.', scr('title'))],
                depends=['open'])]
    for cid, description, attrs in LOGS:
        cps.append(step(cid, f'Log the task "{description}" {attrs}.', add(description, attrs, opener='l'),
                        [('task', 'The task is recorded as already completed now.',
                          ex([description], 'status', 'end', 'project', 'tags', 'due')),
                         ('rows', 'A completed task does not appear in the next report.', scr('rows'))],
                        lifecycle='restart'))
    cps.append(step('log-rejected', 'Log "Bad log" with due:zzz.', add('Bad log', 'due:zzz', opener='l'),
                    [('task', 'The rejected log records nothing.', ex(['Bad log'], 'status')),
                     ('title', 'The prompt closes without an error popup.', scr('title'))], lifecycle='restart'))
    wf = program('add-log', 'log', fixture(TRIO), cps, names=[d for _, d, _ in LOGS] + ['Bad log'])
    return bind(wf, {'log-rejected': ['plain/task'], **{f'{cid}/rows': [f'{cid}/task'] for cid, _, _ in LOGS}})


def episodes():
    return [dates_episode(), bad_dates_episode(), attributes_episode(), add_screen_episode(),
            add_errors_episode(), log_episode()]

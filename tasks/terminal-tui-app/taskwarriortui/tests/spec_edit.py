"""Prompt editing: the line-editing keys of the prompts, tab completion (attributes, modifiers, tags, projects,
priorities, dates, statuses) and the command and filter histories (Up/Down with prefix search, kept across restarts).

Line-editing checkpoints each start a fresh add prompt with the text "alpha beta gamma" between the automatic
quotes (the cursor stands after "gamma"), apply editing keys and read the prompt's input line.
"""
from spec_core import *
from spec_data import MAIN, TRIO

START = [key('Escape'), key('Escape'), key('a'), typ('alpha beta gamma')]

EDITS = [
    # (cid, keys and text after START, requirement)
    ('left', [key('Left'), typ('1'), key('Control+b'), key('Control+b'), typ('2')],
     'Left and Control+B move the cursor one character back.'),
    ('right', [key('Home'), key('Right'), typ('1'), key('Control+f'), typ('2')],
     'Right and Control+F move the cursor one character forward.'),
    ('home', [key('Home'), typ('1'), key('Right'), key('Right'), key('Control+a'), typ('2')],
     'Home and Control+A move the cursor to the beginning of the line.'),
    ('end', [key('End'), typ('1'), key('Left'), key('Left'), key('Control+e'), typ('2')],
     'End and Control+E move the cursor to the end of the line.'),
    ('backspace', [key('Backspace'), key('Control+h')], 'Backspace and Control+H delete the character before the cursor.'),
    ('delete', [key('Home'), key('Right'), key('Delete'), key('Control+d')],
     'Delete and Control+D delete the character under the cursor.'),
    ('kill-end', [key('Home'), key('Right'), key('Right'), key('Right'), key('Control+k')],
     'Control+K deletes from the cursor to the end of the line.'),
    ('kill-start', [key('Left'), key('Left'), key('Left'), key('Left'), key('Control+u')],
     'Control+U deletes from the beginning of the line to the cursor.'),
    ('kill-word', [key('Control+w'), key('Alt+Backspace')],
     'Control+W and Alt+Backspace delete the word before the cursor.'),
    ('delete-word', [key('Home'), key('Right'), key('Alt+d')], 'Alt+D deletes the word after the cursor.'),
    ('word-back', [key('Alt+b'), typ('1'), key('Alt+b'), key('Alt+b'), typ('2')],
     'Alt+B moves the cursor to the start of the previous word.'),
    ('word-forward', [key('Home'), key('Alt+f'), typ('1'), key('Alt+f'), typ('2')],
     'Alt+F moves the cursor to the end of the next word.'),
    ('transpose', [key('Alt+t')], 'Alt+T transposes the words around the cursor.'),
]


def editing_episode():
    cps = [step('start', 'Open the add prompt and type alpha beta gamma.', START,
                [('line', 'The text stands between the automatic quotes.', scr('line'))])]
    for cid, keys, requirement in EDITS:
        cps.append(step(cid, f'In a fresh add prompt with alpha beta gamma, apply: {cid}.', START + keys,
                        [('line', requirement, scr('line'))]))
    cps.append(step('commit', 'In a fresh add prompt with alpha beta gamma, press Alt+B, Control+W and Enter.',
                    START + [key('Alt+b'), key('Control+w'), key('Enter')],
                    [('task', 'The edited text is what is added.', ex(['alpha gamma'], 'status'))]))
    cps.append(step('commit-2', 'In a fresh add prompt with alpha beta gamma, press Alt+T, End, type " +edited" and '
                                'press Enter.', START + [key('Alt+t'), key('End'), typ(' +edited'), key('Enter')],
                    [('task', 'The transposed text is added with the tag.', ex(['alpha gamma beta'], 'status', 'tags'))]))
    return program('edit-keys', 'editing', fixture([]), fresh(cps), names=['alpha gamma', 'alpha gamma beta'])


def add_prompt(text):
    return [key('Escape'), key('Escape'), key('a'), key('End'), typ(' ' + text)]


COMPLETIONS = [
    # (cid, steps, requirement, check)
    ('single', add_prompt('pro') + K('Tab'), 'A single matching attribute is completed at once.', scr('line')),
    ('hint', add_prompt('pro'), 'Before Tab the single completion is suggested after the cursor.', scr('hint')),
    ('first', add_prompt('p') + K('Tab', 'Enter'),
     'With several candidates, Tab opens the list on the first; Enter applies it.', scr('line')),
    ('cycle', add_prompt('p') + K('Tab', 'Tab', 'Enter'), 'Tab again moves to the next candidate.', scr('line')),
    ('back', add_prompt('p') + K('Tab', 'Shift+Tab', 'Enter'), 'Shift+Tab moves to the previous candidate (wrapping).',
     scr('line')),
    ('ctrl-n', add_prompt('p') + K('Control+n', 'Control+n', 'Enter'), 'Control+N cycles like Tab.', scr('line')),
    ('ctrl-p', add_prompt('p') + K('Control+n', 'Control+p', 'Enter'), 'Control+P cycles back like Shift+Tab.',
     scr('line')),
    ('escape', add_prompt('p') + K('Tab', 'Escape'), 'Escape closes the list and keeps the prompt and its text.',
     scr('prompt')),
    ('tag', add_prompt('+sh') + K('Tab'), 'A tag of the listed tasks completes after +.', scr('line')),
    ('tag-word', add_prompt('tag:gar') + K('Tab'), 'tag: completes tag names.', scr('line')),
    ('project', add_prompt('project:Mu') + K('Tab'), 'project: completes project names.', scr('line')),
    ('project-list', add_prompt('project:Ho') + K('Tab', 'Tab', 'Enter'),
     'Several matching projects are listed; the second is applied.', scr('line')),
    ('priority', add_prompt('priority:') + K('Tab', 'Enter'), 'priority: completes the priority values.',
     scr('line')),
    ('modifier', add_prompt('due.bef') + K('Tab'), 'Attribute modifiers complete after the dot.', scr('line')),
    ('due-date', add_prompt('due:') + K('Tab', 'Enter'), 'due: offers the due dates of the listed tasks.', scr('line')),
    ('filter-status', [key('Escape'), key('Escape'), key('/'), key('Control+u'), typ('status:')] + K('Tab', 'Tab',
                                                                                                    'Enter'),
     'In the filter prompt, status: completes the status names.', scr('line')),
    ('filter-attribute', [key('Escape'), key('Escape'), key('/'), key('Control+u'), typ('sched')] + K('Tab'),
     'The filter prompt completes attribute names too.', scr('line')),
    ('nothing', add_prompt('xyzzy') + K('Tab'), 'Tab does nothing when nothing matches.', scr('prompt')),
    ('log-tag', [key('Escape'), key('Escape'), key('l'), key('End'), typ(' +sh'), key('Tab')],
     'The log prompt completes tags too.', scr('line')),
    ('annotate-word', [key('Escape'), key('Escape'), key('A'), key('End'), typ(' pro'), key('Tab')],
     'The annotate prompt completes attribute names too.', scr('line')),
]


def completion_episode():
    cps = [step(cid, 'In the add prompt (after the quotes), ' + req[0].lower() + req[1:], steps, [('line', req, check)])
           for cid, steps, req, check in COMPLETIONS]
    cps.append(step('use', 'Add "Weed" with the tag typed as +gar and completed with Tab.',
                    [key('Escape'), key('Escape'), key('a'), typ('Weed'), key('End'), typ(' +gar'), key('Tab'),
                     key('Enter')],
                    [('task', 'The completed tag is part of the added task.', ex(['Weed'], 'tags'))]))
    cps.append(step('modify-tag', 'Select task 2, open the modify prompt, type +ph, press Tab and Enter.',
                    [key('Escape'), key('Escape')] + jump(2) + [key('m'), typ('+ph'), key('Tab'), key('Enter')],
                    [('task', 'The modify prompt completes the tag too.', ex(['Write report'], 'tags'))]))
    wf = program('completion', 'completion', fixture(MAIN), fresh(cps), names=['Weed'])
    return bind(wf, {'nothing': ['single/line'], 'escape': ['single/line']})


def history_episode():
    hist = lambda text: ('history', text, scr('prompt'))
    position = lambda text: ('position', text, scr('history'))
    # The filters select tasks that the reuse checkpoint does not add to, so their rows do not depend on it.
    filters = filt('project:P') + filt('First')
    cps = [
        step('fill', 'Add the tasks "First item", "Second item" +x and "Third thing" project:P.',
             add('First item') + add('Second item', '+x') + add('Third thing', 'project:P'),
             [('tasks', 'The three tasks are added.', ex(['First item', 'Second item', 'Third thing'], 'status'))]),
        step('open', 'Open the add prompt.', K('a'),
             [hist('The prompt opens empty.'), position('The history position is after the three commands.')],
             depends=['fill'], lifecycle='restart'),
        step('up', 'Open the add prompt and press Up.', K('a', 'Up'),
             [hist('Up recalls the latest command.'), position('The position moves.')], depends=['fill'],
             lifecycle='restart'),
        step('up-2', 'Open the add prompt and press Up three times.', K('a', 'Up', 'Up', 'Up'),
             [hist('Up walks back to the oldest command.')], depends=['up'], lifecycle='restart'),
        step('up-stop', 'Press Up again.', K('Up'), [hist('At the oldest command Up stays there.')],
             depends=['up-2']),
        step('down', 'Press Down.', K('Down'), [hist('Down moves forward again.')], depends=['up-stop']),
        step('reuse', 'Open the add prompt, press Up twice and Enter.', K('a', 'Up', 'Up', 'Enter'),
             [('tasks', 'The recalled command adds a second "Second item".', ex(['Second item'], 'status', 'tags'))],
             depends=['up'], lifecycle='restart'),
        step('prefix', 'Open the add prompt, delete the closing quote, type Th and press Up.',
             [key('a'), key('Delete'), typ('Th'), key('Up')],
             [hist('Up recalls the latest command that starts with the text before the cursor.')], depends=['fill'],
             lifecycle='restart'),
        step('annotate-shares', 'Select the first task, open the annotate prompt and press Up.', K('g', 'A', 'Up'),
             [hist('The annotate prompt shares the command history.')], depends=['reuse'], lifecycle='restart'),
        step('filters', 'Apply the filters project:P and then First.', filters,
             [('rows', 'The last filter applies.', scr('rows'))], depends=['fill'], lifecycle='restart'),
        step('filter-up', 'Open the filter prompt, clear it and press Up.', [key('/'), key('Control+u'), key('Up')],
             [hist('Up in the filter prompt recalls the filters typed before, latest first.')], depends=['filters']),
        step('filter-up-2', 'Press Up again.', K('Up'), [hist('Up recalls the filter before that.')],
             depends=['filter-up']),
        step('filter-apply', 'Press Enter.', K('Enter'), [('rows', 'The recalled filter applies.', scr('rows'))],
             depends=['filter-up-2']),
        step('restart', 'Restart the application, open the add prompt and press Up.', [restart(), key('a'), key('Up')],
             [hist('The command history survives a restart.')], depends=['reuse']),
        step('restart-filter', 'Restart the application, open the filter prompt, clear it and press Up twice.',
             [restart(), key('/'), key('Control+u'), key('Up'), key('Up')],
             [hist('The filter history survives a restart.')], depends=['filter-apply']),
    ]
    return program('history', 'history', fixture(TRIO), cps, names=['First item', 'Second item', 'Third thing'])


def episodes():
    return [editing_episode(), completion_episode(), history_episode()]

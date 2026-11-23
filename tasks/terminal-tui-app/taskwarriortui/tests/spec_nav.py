"""Navigation in the task report, jumping to a task ID, and marking tasks for actions on several tasks."""
from spec_core import *
from spec_data import LIST, SHORT

SEL = 'The task the goal names is the selected task of the report.'
NAMES = [t['description'] for t in LIST]


def sel(cid, goal, steps, expected, depends=(), extra=()):
    return step(cid, goal, steps, [('selected', f'{expected} is the selected task.', scr('selected'))] + list(extra),
                depends=depends)


def keys_episode():
    # Six tasks AA..FF listed in this order (urgency falls with the entry date). Every checkpoint restarts the
    # application, so each key is pressed from the first task (or from the position the goal reaches first).
    cps = [
        step('initial', 'Observe the report as it starts.', [],
             [('rows', 'The six pending tasks are listed by urgency, AA first.', scr('rows')),
              ('selected', 'The first task is selected.', scr('selected'))]),
        sel('j', 'Press j once.', K('j'), 'Item BB', ['initial']),
        sel('down', 'Press Down once.', K('Down'), 'Item BB', ['initial']),
        sel('k', 'Press j twice and k once.', K('j', 'j', 'k'), 'Item BB', ['j']),
        sel('up', 'Press j twice and Up once.', K('j', 'j', 'Up'), 'Item BB', ['j']),
        sel('wrap', 'Press k at the first task, then Down, Up and j.', K('k', 'Down', 'Up', 'j'),
            'Item AA (k and Up wrap from the first task to the last, j and Down from the last to the first)',
            ['initial']),
        sel('G', 'Press G.', K('G'), 'Item FF (the last task)', ['initial']),
        sel('end', 'Press End.', K('End'), 'Item FF', ['initial']),
        sel('g', 'Press j twice and g.', K('j', 'j', 'g'), 'Item AA (the first task)', ['j']),
        sel('home', 'Press j twice and Home.', K('j', 'j', 'Home'), 'Item AA', ['j']),
        sel('J', 'Press J (page down) on a list shorter than a page.', K('J'), 'Item FF', ['initial']),
        sel('pagedown', 'Press PageDown.', K('PageDown'), 'Item FF', ['initial']),
        sel('K', 'Press j twice and K (page up).', K('j', 'j', 'K'), 'Item AA', ['j']),
        sel('pageup', 'Press j twice and PageUp.', K('j', 'j', 'PageUp'), 'Item AA', ['j']),
        sel('page-wrap', 'Press G, then J at the last task and K at the first.', K('G', 'J', 'K'),
            'Item FF (J wraps from the last task to the first, K from the first to the last)', ['G']),
    ]
    return program('nav-keys', 'navigation', fixture(SHORT), fresh(cps))


def paging_episode():
    # Twenty pending tasks: more than the report shows at once, so it scrolls with the selection.
    cps = [
        step('initial', 'Observe the report of twenty tasks.', [],
             [('rows', 'The first fifteen tasks are visible, AA first.', scr('rows')),
              ('selected', 'The first task is selected.', scr('selected'))]),
        sel('G', 'Press G.', K('G'), 'Item TT', ['initial'],
            [('rows', 'The report scrolls so that the last task is visible.', scr('rows'))]),
        sel('J', 'Press J.', K('J'), 'Item RR (one report page further down)', ['initial']),
        sel('J-last', 'Press J twice.', K('J', 'J'), 'Item TT (the last task)', ['J']),
        sel('pagedown', 'Press PageDown.', K('PageDown'), 'Item RR', ['initial']),
        sel('K', 'Press G and K.', K('G', 'K'), 'Item CC (one report page further up)', ['G']),
        sel('pageup', 'Press G and PageUp.', K('G', 'PageUp'), 'Item CC', ['G']),
    ]
    return program('nav-paging', 'navigation', fixture(LIST), fresh(cps))


def jump_episode():
    cps = [
        sel('jump', 'Jump to task 4 with the : prompt.', jump(4), 'Item DD'),
        sel('jump-2', 'Jump to task 2.', jump(2), 'Item BB'),
        step('prompt', 'Open the jump prompt and type 5 without confirming.', [key(':'), typ('5')],
             [('prompt', 'The jump prompt shows the typed ID.', scr('prompt'))]),
        sel('escape', 'Jump to task 2, open the jump prompt, type 5 and press Escape.',
            jump(2) + [key(':'), typ('5'), key('Escape')], 'Item BB (the jump was cancelled)', ['jump-2', 'prompt'],
            [('title', 'The filter prompt is shown again.', scr('title'))]),
        step('unknown', 'Jump to task 42, which does not exist.', jump(42),
             [('error', 'An error popup says that task 42 cannot be located in the report.',
               scr('error', mentions=['42']))]),
        sel('dismiss', 'Jump to task 2, jump to task 42 and press any key (x) to dismiss the error.',
            jump(2) + jump(42) + K('x'), 'Item BB (the selection did not change)', ['jump-2', 'unknown'],
            [('tasks', 'The key only dismissed the error: no task was deleted.', summary())]),
        step('letters', 'Jump to the text abc.', jump('abc'),
             [('error', 'An error popup reports the invalid number.', scr('error'))]),
        sel('after', 'Dismiss the error with Escape and jump to task 6.', K('Escape') + jump(6), 'Item FF',
            ['letters']),
    ]
    for cp in cps[1:]:
        if cp['id'] != 'after':
            cp['lifecycle'] = 'restart'
    return program('nav-jump', 'navigation', fixture(SHORT), cps)


def marks_episode():
    marked = lambda text: ('marked', text, scr('marked'))
    cps = [
        step('mark', 'Mark the selected task with v.', K('v'),
             [marked('Item AA is marked.'),
              ('indicators', 'The selected marked task shows the marked-selection indicator.', scr('indicators'))]),
        step('move', 'Mark the first task and move down twice.', K('v', 'j', 'j'),
             [marked('Item AA stays marked while the selection moves.'),
              ('indicators', 'The marked task and the selected unmarked task show their indicators.',
               scr('indicators'))], depends=['mark']),
        step('second', 'Mark the first task, move down twice and mark Item CC too.', K('v', 'j', 'j', 'v'),
             [marked('Item AA and Item CC are marked.')], depends=['move']),
        step('unmark', 'Mark Item AA and Item CC, go back to Item AA and press v again.', K('v', 'j', 'j', 'v', 'g', 'v'),
             [marked('Only Item CC is still marked.')], depends=['second']),
        step('all', 'Mark Item CC and press V.', K('j', 'j', 'v', 'V'),
             [marked('V toggles every task: all but Item CC are now marked.')], depends=['mark']),
        step('all-again', 'Mark Item CC and press V twice.', K('j', 'j', 'v', 'V', 'V'),
             [marked('V toggles every task back: only Item CC is marked.')], depends=['all']),
        step('escape', 'Mark Item AA and Item BB and press Escape.', K('v', 'j', 'v', 'Escape'),
             [marked('Escape clears every mark.'),
              ('indicators', 'Only the selection indicator is shown.', scr('indicators'))], depends=['mark']),
        step('modify-title', 'Mark Item BB and Item DD, then open the modify prompt.',
             K('j', 'v', 'j', 'j', 'v', 'm'),
             [('prompt', 'The modify prompt names the two marked tasks and starts empty.', scr('prompt'))],
             depends=['mark']),
        step('done-marked', 'Mark Item BB and Item DD and complete them with d.', K('j', 'v', 'j', 'j', 'v', 'd'),
             [('tasks', 'Exactly the two marked tasks are completed.', summary()),
              ('rows', 'They leave the report.', scr('rows'))], depends=['mark']),
        step('cleared', 'Observe the marks after the completion.', [],
             [marked('No task is marked any more.')], depends=['done-marked']),
    ]
    for cp in cps[1:]:
        if cp['id'] != 'cleared':
            cp['lifecycle'] = 'restart'
    return program('nav-marks', 'selection', fixture(SHORT), cps)


def episodes():
    return [keys_episode(), paging_episode(), jump_episode(), marks_episode()]

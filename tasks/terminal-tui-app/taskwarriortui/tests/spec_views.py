"""The other views ([ and ]): Projects (Taskwarrior's project summary), Timesheet (the tasks completed and started
in recent weeks) and Calendar (a year of months; j/k change the year, J ten years), the help popup (?), and quitting.
"""
from spec_core import *
from spec_data import MAIN

VIEW = ('view', 'The named view is the active tab.', scr('view'))


def tabs_episode():
    fx = {'tasks': MAIN}
    items = [
        ('projects', fx, 'Press ].', K(']'),
         [VIEW, ('content', 'The Projects view shows the project summary: remaining tasks, average age and '
                            'completion per project and subproject.', scr('content'))]),
        ('timesheet', fx, 'Press ] twice.', K(']', ']'),
         [VIEW, ('content', 'The Timesheet view lists this week\'s completed and started tasks.', scr('content'))],
         ['projects']),
        ('calendar', fx, 'Press ] three times.', K(']', ']', ']'),
         [VIEW, ('content', 'The Calendar view shows the twelve months of 2026.', scr('content', first=12))],
         ['timesheet']),
        ('calendar-stop', None, 'Press ] on the Calendar view.', K(']'),
         [('view', 'Calendar is the last view: ] does not move further.', scr('view'))], ['calendar']),
        ('back', fx, 'Press ] three times and [ three times.', K(']', ']', ']', '[', '[', '['),
         [('view', 'The Tasks view is shown again.', scr('view')),
          ('rows', 'The task report is shown.', scr('rows'))], ['calendar']),
        ('tasks-stop', None, 'Press [ on the Tasks view.', K('['),
         [('view', 'Tasks is the first view: [ does not move further.', scr('view'))], ['back']),
        ('projects-change', fx, 'Complete task 1 (Pay rent), then open the Projects view.', jump(1) + K('d', ']'),
         [('content', 'The summary counts Home\'s completed task.', scr('content'))], ['projects']),
        ('timesheet-change', None, 'Go to the Timesheet view.', K(']'),
         [('content', 'The timesheet lists the task completed now.', scr('content'))], ['projects-change']),
        ('quit', None, 'Press q on the Timesheet view.', K('q'),
         [('running', 'q quits the application from this view too.', scr('running'))], ['timesheet-change']),
    ]
    return cases('views-tabs', 'views', items)


def calendar_episode():
    year = lambda text: ('content', text, scr('content', first=1))
    cal = K(']', ']', ']')
    cps = [
        step('open', 'Go to the Calendar view.', cal, [year('The calendar shows the year 2026.')]),
        step('next-year', 'Go to the Calendar view and press j.', cal + K('j'),
             [year('j shows the next year, 2027.'),
              ('months', 'The months of 2027 start on their weekdays.', scr('content', first=8))], depends=['open']),
        step('previous-year', 'Go to the Calendar view and press k.', cal + K('k'),
             [year('k shows the previous year: 2025.')], depends=['open']),
        step('decade', 'Go to the Calendar view and press J.', cal + K('J'),
             [year('J moves ten years forward, to 2036.')], depends=['open']),
        step('down-key', 'Go to the Calendar view and press Down.', cal + K('Down'),
             [year('Down moves one year forward too: 2027.')], depends=['open']),
        step('up-key', 'Go to the Calendar view and press Up.', cal + K('Up'),
             [year('Up moves one year back: 2025.')], depends=['open']),
        step('leap', 'Go to the Calendar view and press k twice.', cal + K('k', 'k'),
             [('content', 'February of the leap year 2024 has 29 days.', scr('content', first=12))],
             depends=['previous-year']),
        step('tasks', 'Go to the Calendar view, press j, then [ three times and ] three times.',
             cal + K('j', '[', '[', '[', ']', ']', ']'),
             [year('The calendar keeps the chosen year while the application runs.')], depends=['next-year']),
    ]
    return program('views-calendar', 'views', fixture(MAIN), fresh(cps))


def calendar_options_episode():
    cps = [step('monday', 'Go to the Calendar view.', K(']', ']', ']'),
                [('content', 'With weekstart monday and three months per row, weeks start on Monday and the months '
                             'come three to a row.', scr('content', first=9))])]
    return program('views-calendar-options', 'views',
                   fixture(MAIN, [('weekstart', 'monday'), ('uda.taskwarrior-tui.calendar.months-per-row', '3')]), cps)


def rotate_episode():
    cps = [
        step('left', 'Press [ on the Tasks view.', K('['),
             [('view', 'With change-focus-rotate, [ wraps from Tasks to Calendar.', scr('view'))]),
        step('right', 'Press ] on the Calendar view.', K(']'),
             [('view', '] wraps from Calendar to Tasks.', scr('view'))], depends=['left']),
    ]
    return program('views-rotate', 'views', fixture(MAIN, [('uda.taskwarrior-tui.tabs.change-focus-rotate', 'true')]),
                   cps)


def help_episode():
    box = lambda text: ('help', text, scr('popup', title='Help', first=8))
    cps = [
        step('open', 'Press ?.', K('?'), [box('The help popup lists the key bindings from the top.')]),
        step('scroll', 'Press ? and j three times.', K('?', 'j', 'j', 'j'), [box('The help text scrolls down.')],
             depends=['open'], lifecycle='restart'),
        step('scroll-back', 'Press k once.', K('k'), [box('The help text scrolls back up by one line.')],
             depends=['scroll']),
        step('close', 'Press ? and Escape.', K('?', 'Escape'),
             [('boxes', 'The help popup is closed.', scr('boxes')),
              ('rows', 'The report is shown again.', scr('rows'))], depends=['open'], lifecycle='restart'),
        step('close-q', 'Press ? and q.', K('?', 'q'),
             [('boxes', 'q closes the help popup.', scr('boxes')),
              ('running', 'The application keeps running.', scr('running'))], depends=['open'], lifecycle='restart'),
    ]
    return program('views-help', 'help', fixture(MAIN), cps)


def quit_episode():
    items = [
        ('q', {'tasks': MAIN}, 'Press q on the task report.', K('q'),
         [('running', 'The application quits.', scr('running'))]),
        ('ctrl-c', {'tasks': MAIN}, 'Press Control+C on the task report.', K('Control+c'),
         [('running', 'The application quits.', scr('running'))]),
        ('calendar-q', {'tasks': MAIN}, 'Go to the Calendar view and press q.', K(']', ']', ']', 'q'),
         [('running', 'The application quits.', scr('running'))]),
        ('projects-q', {'tasks': MAIN}, 'Go to the Projects view and press q.', K(']', 'q'),
         [('running', 'The application quits.', scr('running'))]),
        ('prompt-q', {'tasks': MAIN}, 'Open the filter prompt and type q.', K('/', 'q'),
         [('running', 'In a prompt, q is text: the application keeps running.', scr('running')),
          ('line', 'The q is typed into the filter.', scr('line'))]),
    ]
    quit = ['prompt-q/line']
    return bind(cases('views-quit', 'views', items), {'q': quit, 'ctrl-c': quit, 'calendar-q': quit,
                                                      'projects-q': quit, 'prompt-q/running': ['q/running']})


def episodes():
    return [tabs_episode(), calendar_episode(), calendar_options_episode(), rotate_episode(), help_episode(),
            quit_episode()]

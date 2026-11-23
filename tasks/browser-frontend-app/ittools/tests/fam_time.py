'''Program episodes: crontab generator, date-time converter, ETA calculator and chronometer.'''
from pbuild import bind, case, choose, click, clock, controls, fields, fill, lines, multi, outs, point, switch, toggles, wait, episode

DEFAULT = 'Open the page without typing.'
INPUTS = {'type': 'inputs'}


# -- Crontab generator ----------------------------------------------------------------------------------
CRON_PAGE = '/crontab-generator'
CRON_IN = '* * * * *'
CRON_SEEN = multi(input=fields(CRON_IN), switches=toggles(), text=lines(skip=2, stop='Verbose'))
VERBOSE, HOURS24, DAY0 = 0, 1, 2
COMPANION = ['every-five/text']


def crontab_generator():
    def one(cid, goal, expr, requirement, after=(), requires=()):
        steps = [fill(expr, placeholder=CRON_IN)] + list(after)
        return case(cid, goal, CRON_PAGE, steps, [point('text', requirement, CRON_SEEN, requires)])

    def typed(prefix, items, requirement, requires=()):
        return [one(prefix + cid, 'Type the schedule ' + expr + '.', expr, requirement, (), requires) for cid, expr in items]

    cases = [case('default', DEFAULT, CRON_PAGE, [], [point('text', 'The page opens with an example schedule already described in words.', CRON_SEEN)])]
    cases += typed('', (
        ('every-minute', '* * * * *'), ('every-five', '*/5 * * * *'), ('midnight', '0 0 * * *'),
        ('weekdays-noon', '0 12 * * 1-5'), ('first-of-month', '30 8 1 * *'), ('new-year', '0 0 1 1 *'),
        ('monday-name', '15 10 * * mon'), ('office-hours', '0 9-17 * * *'), ('twice-a-day', '0 0,12 * * *'),
        ('seconds-step', '*/10 * * * * *'), ('seconds-fixed', '0 0 0 * * *'), ('month-names', '0 0 1 jan,jul *'),
        ('range-step', '0-30/10 * * * *'), ('sunday-name', '5 4 * * sun'), ('leap-day', '0 0 29 2 *'),
        ('year-end', '59 23 31 12 *'), ('every-two-days', '0 0 */2 * *'), ('range-with-step', '23 0-20/2 * * *'),
        ('sunday-seven', '0 0 * * 7'), ('weeknights', '0 22 * * 1-5'),
    ), 'The schedule is described in words.')
    cases += typed('alias-', (
        ('yearly', '@yearly'), ('annually', '@annually'), ('monthly', '@monthly'), ('weekly', '@weekly'),
        ('daily', '@daily'), ('midnight', '@midnight'), ('hourly', '@hourly'),
    ), 'An alias is described like the schedule it stands for.')
    cases += typed('bad-', (
        ('minute-60', '60 * * * *'), ('four-fields', '* * * *'), ('word', 'abc'), ('day-32', '* * 32 * *'),
        ('month-13', '* * * 13 *'), ('weekday-8', '* * * * 8'), ('step-zero', '*/0 * * * *'), ('range-70', '1-70 * * * *'),
        ('seven-fields', '* * * * * * *'), ('unknown-alias', '@sometimes'),
    ), 'A schedule that is not valid is flagged with a message and is not described.', COMPANION)
    cases.append(one('bad-empty', 'Clear the schedule.', '', 'An empty schedule is flagged as invalid.', (), COMPANION))
    cases += [
        one('verbose-off', 'Type 0 12 * * 1 and turn off Verbose.', '0 12 * * 1', 'Turning off Verbose gives a shorter description.', [switch(VERBOSE)]),
        one('hours-12', 'Type 0 17 * * * and turn off 24 hour time.', '0 17 * * *', 'Without 24 hour time the hour is written with am or pm.', [switch(HOURS24)]),
        one('days-from-1', 'Type 0 0 * * 1 and turn off Days start at 0.', '0 0 * * 1', 'Without Days start at 0, day 1 is Sunday.', [switch(DAY0)]),
        one('all-off', 'Type 30 18 * * 5 and turn off all three switches.', '30 18 * * 5', 'The three switches apply together.', [switch(VERBOSE), switch(HOURS24), switch(DAY0)]),
        one('seconds-off', 'Type */30 * * * * * and turn off Verbose.', '*/30 * * * * *', 'A schedule with seconds is described shortly without Verbose.', [switch(VERBOSE)]),
    ]
    return episode('crontab-generator', 'generator', cases)


# -- Date-time converter --------------------------------------------------------------------------------
DT_PAGE = '/date-converter'
DT_IN = 'Put your date string here...'
DT_SEEN = multi(input=fields(DT_IN), detected=lines(skip=2, stop='JS locale date string'), formats=outs(labels=True, allow_empty=True))


def date_time_converter():
    def one(cid, goal, text, requirement, before=(), after=(), requires=()):
        steps = list(before) + [fill(text, placeholder=DT_IN)] + list(after)
        return case(cid, goal, DT_PAGE, steps, [point('formats', requirement, DT_SEEN, requires)])

    def typed(items, requirement, requires=()):
        return [one(cid, 'Type ' + text + '.', text, requirement, (), (), requires) for cid, text in items]

    shown = 'The date is shown in every format and the format that matches the typed text is chosen.'
    cases = [case('default', DEFAULT, DT_PAGE, [], [point('formats', 'The page opens with the current time shown in every format.', DT_SEEN)])]
    cases += typed((
        ('iso-z', '2024-02-29T12:30:45Z'), ('iso-offset', '2024-02-29T12:30:45+02:00'), ('iso-date', '2024-02-29'),
        ('iso-week', '2024-W09-4'), ('iso-ordinal', '2024-060'), ('iso-no-zone', '2024-02-29T12:30:45'),
        ('iso9075', '2024-02-29 12:30:45'), ('iso9075-fraction', '2024-02-29 12:30:45.123456'),
        ('iso9075-zone', '2024-02-29 12:30:45+05:30'), ('rfc3339-fraction', '2024-02-29T12:30:45.500-07:00'),
        ('rfc7231', 'Thu, 29 Feb 2024 12:30:45 GMT'), ('unix', '1709209845'), ('unix-zero', '0'),
        ('unix-max', '9999999999'), ('timestamp', '1709209845123'), ('mongo', '65e0a1750000000000000000'),
        ('excel', '45351.52'), ('excel-negative', '-1'), ('js-string', 'Thu Feb 29 2024 12:30:45 GMT+0000'),
        ('year-end', '2024-12-31T23:59:59Z'), ('epoch', '1970-01-01T00:00:00Z'), ('before-epoch', '1969-12-31T23:59:59Z'),
        ('far-future', '2100-01-01T00:00:00Z'), ('spaces', ' 1709209845 '),
    ), shown)
    cases += typed((
        ('bad-words', 'not a date'), ('bad-month', '2024-13-45'), ('bad-day', '2024-02-30T00:00:00Z'), ('bad-long', '12345678901234'),
    ), 'A date that cannot be read is flagged with a message and every format is left empty.', ['iso-z/formats'])
    cases += [
        case('later-hour', 'Let one hour pass.', DT_PAGE, [clock(3600), wait(0.5)], [point('formats', 'The current time shown follows the clock.', DT_SEEN)]),
        case('later-day', 'Let one day pass.', DT_PAGE, [clock(86400), wait(0.5)], [point('formats', 'The current time shown follows the clock.', DT_SEEN)]),
        case('select-only', 'Choose Mongo ObjectID without typing a date.', DT_PAGE, [choose('Timestamp', 'Mongo ObjectID')],
             [point('formats', 'Choosing a format without a date leaves the current time shown in every format.', DT_SEEN)]),
        one('select-unix', 'Choose Unix timestamp and type 1700000000.', '1700000000', 'A number typed after choosing a format is read in that format.', [choose('Timestamp', 'Unix timestamp')]),
        one('cleared', 'Type 1709209845 and then clear the date.', '1709209845', 'Clearing the date goes back to the current time.', (), [fill('', placeholder=DT_IN)]),
    ]
    return episode('date-time-converter', 'converter', bind(cases, {'cleared': 'iso-z/formats'}))


# -- ETA calculator -------------------------------------------------------------------------------------
ETA_PAGE = '/eta-calculator'
NUM = 'Please Input'
ETA_SEEN = multi(inputs=INPUTS, text=lines(start='Total duration'))


def eta_calculator():
    def amounts(count, per, span, unit=None):
        steps = [fill(str(count), placeholder=NUM), fill(str(per), placeholder=NUM, nth=1), fill(str(span), placeholder=NUM, nth=2)]
        if unit:
            steps.append(choose('minutes', unit))
        return steps

    def one(cid, goal, steps, requirement='The total duration and the end time follow the numbers.'):
        return case(cid, goal, ETA_PAGE, steps, [point('result', requirement, ETA_SEEN)])

    return episode('eta-calculator', 'calculator', bind([
        case('default', DEFAULT, ETA_PAGE, [], [point('result', 'The page opens with 186 units at 3 units per 5 minutes and the end time worked out from the current time.', ETA_SEEN)]),
        one('plates', 'Set 500 units at 5 units per 3 minutes.', amounts(500, 5, 3)),
        one('one-minute', 'Set 1 unit at 1 unit per 1 minute.', amounts(1, 1, 1)),
        one('exact-hour', 'Set 60 units at 1 unit per 1 minute.', amounts(60, 1, 1)),
        one('unit-hours', 'Set 100 units at 2 units per 1 hour.', amounts(100, 2, 1, 'hours')),
        one('unit-days', 'Set 10 units at 1 unit per 1 day.', amounts(10, 1, 1, 'days')),
        one('unit-seconds', 'Set 100 units at 1 unit per 10 seconds.', amounts(100, 1, 10, 'seconds')),
        one('unit-ms', 'Set 1000 units at 1 unit per 1 millisecond.', amounts(1000, 1, 1, 'milliseconds')),
        one('with-ms', 'Set 1 unit at 3 units per 1 second.', amounts(1, 3, 1, 'seconds')),
        one('decimal', 'Set 2.5 units at 1 unit per 1 minute.', amounts('2.5', 1, 1)),
        one('today', 'Set 120 units at 1 unit per 1 minute.', amounts(120, 1, 1)),
        one('tomorrow', 'Set 1440 units at 1 unit per 1 minute.', amounts(1440, 1, 1)),
        one('next-week', 'Set 10080 units at 1 unit per 1 minute.', amounts(10080, 1, 1)),
        one('long', 'Set 1000000 units at 1 unit per 1 minute.', amounts(1000000, 1, 1)),
        one('zero-count', 'Set the amount of units to 0.', [fill('0', placeholder=NUM)], 'An amount below the minimum is handled by the field.'),
        one('zero-rate', 'Set the units per time span to 0.', [fill('0', placeholder=NUM, nth=1)], 'A rate below the minimum is handled by the field.'),
        one('past', 'Let one day pass and set 120 units at 1 unit per 1 minute.', [clock(86400), wait(0.5)] + amounts(120, 1, 1), 'The end time is described relative to the current time.'),
    ], {'zero-count': 'plates/result', 'zero-rate': 'plates/result'}))


# -- Chronometer ----------------------------------------------------------------------------------------
CHRONO_PAGE = '/chronometer'
CHRONO_SEEN = multi(display=lines(skip=2, reading='all'))


def chronometer():
    def run(cid, goal, steps, requirement):
        return case(cid, goal, CHRONO_PAGE, steps, [point('display', requirement, CHRONO_SEEN)])

    start = [click('Start'), wait(0.5)]

    def later(seconds):
        return [clock(seconds), wait(0.5)]

    return episode('chronometer', 'timer', [
        run('default', DEFAULT, [], 'The page opens with the timer at zero and a Start button.'),
        run('running', 'Press Start.', start, 'The button changes to Stop while the timer runs.'),
        run('seconds', 'Press Start and let 65 seconds pass.', start + later(65), 'The timer shows minutes, seconds and milliseconds.'),
        run('hour', 'Press Start and let 3665 seconds pass.', start + later(3665), 'Hours appear once an hour has passed.'),
        run('long-day', 'Press Start and let 90000 seconds pass.', start + later(90000), 'Hours keep counting past 24.'),
        run('stop', 'Press Start, let 10 seconds pass, press Stop and let 100 more seconds pass.', start + later(10) + [click('Stop'), wait(0.5)] + later(100), 'Stop freezes the timer.'),
        run('resume', 'Start, let 10 seconds pass, Stop, Start and let 5 seconds pass.', start + later(10) + [click('Stop'), wait(0.5)] + start + later(5), 'Starting again adds to the time already counted.'),
        run('reset-running', 'Start, let 30 seconds pass and press Reset.', start + later(30) + [click('Reset'), wait(0.5)], 'Reset sets the timer to zero and it keeps running.'),
        run('reset-stopped', 'Start, let 30 seconds pass, Stop and press Reset.', start + later(30) + [click('Stop'), wait(0.5), click('Reset')], 'Reset sets a stopped timer to zero and the button says Start.'),
        run('reset-then-run', 'Start, let 30 seconds pass, press Reset and let 20 more seconds pass.', start + later(30) + [click('Reset'), wait(0.5)] + later(20), 'The timer counts again from zero after Reset.'),
        run('instant-stop', 'Press Start and then Stop at once.', start + [click('Stop'), wait(0.5)], 'Stopping at once leaves the timer at zero.'),
    ])


def build():
    return [crontab_generator(), date_time_converter(), eta_calculator(), chronometer()]

"""Recurrence expansion, temporal boundaries, exceptions and public serialization."""
from datetime import datetime, timedelta
from spec_common import *
from fixtures import apt, event


# Rules use calcurse's native D/W/M/Y, w (weekday), m (month), d (month-day) notation.
# These are distinct generation rules, not a Cartesian grid of arbitrary dates.
RULES = [
    ('daily', '2026-03-18', '1D'),
    ('alternate-days', '2026-03-18', '2D'),
    ('daily-until', '2026-03-18', '1D -> 03/23/2026'),
    ('daily-except', '2026-03-18', '1D !03/19/2026 !03/22/2026'),
    ('daily-workdays', '2026-03-18', '1D w1 w2 w3 w4 w5'),
    ('daily-weekend', '2026-03-21', '1D w0 w6'),
    ('daily-months', '2026-03-18', '1D m3 m5'),
    ('daily-monthdays', '2026-03-15', '1D d1 d15 d-1'),
    ('daily-intersection', '2026-03-18', '1D d18 d20 d23 w1 w3 w5 m3'),
    ('weekly', '2026-03-18', '1W'),
    ('fortnight', '2026-03-18', '2W'),
    ('weekly-until', '2026-03-18', '1W -> 04/01/2026'),
    ('weekly-except', '2026-03-18', '1W !03/25/2026'),
    ('weekly-tue-thu', '2026-03-17', '1W w2 w4'),
    ('weekly-sun-tue', '2026-03-17', '2W w0 w2'),
    ('weekly-months', '2026-03-18', '1W w1 w3 m3 m5'),
    ('monthly', '2026-03-18', '1M'),
    ('bimonthly', '2026-03-18', '2M'),
    ('monthly-until', '2026-03-18', '1M -> 06/18/2026'),
    ('monthly-except', '2026-03-18', '1M !04/18/2026'),
    ('monthly-31', '2026-01-31', '1M'),
    ('monthly-30', '2026-01-30', '1M'),
    ('monthly-first-last', '2026-03-01', '1M d1 d-1'),
    ('monthly-penultimate', '2026-01-30', '1M d-2'),
    ('monthly-february', '2026-02-27', '1M d-2 m2'),
    ('monthly-2-15', '2026-03-02', '1M d2 d15'),
    ('monthly-last-monday', '2026-03-30', '1M w-8'),
    ('monthly-first-friday', '2026-03-06', '1M w12'),
    ('monthly-first-last-sunday', '2026-03-01', '1M w7 w-7'),
    ('monthly-all-wednesdays', '2026-03-04', '1M w3'),
    ('monthly-friday-13', '2026-03-13', '1M d13 w5'),
    ('monthly-fifth-monday', '2026-03-30', '1M w36'),
    ('monthly-fifth-last-saturday', '2020-08-01', '1M w-41'),
    ('monthly-quarter', '2026-03-18', '1M m3 m6 m9 m12'),
    ('yearly', '2026-03-18', '1Y'),
    ('biennial', '2026-03-18', '2Y'),
    ('leap-day', '2024-02-29', '1Y'),
    ('leap-four-years', '2024-02-29', '4Y'),
    ('yearly-until', '2026-03-18', '1Y -> 03/18/2028'),
    ('yearly-except', '2026-03-18', '1Y !03/18/2027'),
    ('yearly-june-july', '2026-06-10', '1Y m6 m7'),
    ('yearly-last-sunday-march', '2026-03-29', '1Y w-7 m3'),
    ('yearly-20th-monday', '2026-05-18', '1Y w141'),
    ('yearly-last-thursday', '2026-12-31', '1Y w-11'),
    ('yearly-february-1-29', '2024-02-01', '1Y d1 d29 m2'),
    ('yearly-summer-thursdays', '2026-06-04', '1Y w4 m6 m7 m8'),
    ('yearly-election-rule', '2024-11-05', '4Y d2 d3 d4 d5 d6 d7 d8 w2 m11'),
    ('new-year-crossing', '2025-12-31', '1Y'),
]


def build():
    out = []
    for kind in ['event', 'apt']:
        cases = []
        for name, start, rule in RULES:
            label = 'Series ' + name
            if kind == 'event':
                line = event(start, label, rule)
            else:
                line = apt(start + ' 23:30', 120, label, rule, flagged=True)
            origin = datetime.strptime(start, '%Y-%m-%d')
            first = (origin - timedelta(days=2)).strftime('%m/%d/%Y')
            # Query before origin and across the first repeat/period boundary; then far from origin.
            if 'Y' in rule.split(' ')[0]:
                future = (origin.replace(year=origin.year + 4) - timedelta(days=2)).strftime('%m/%d/%Y')
                span = 370
            else:
                future = (origin + timedelta(days=340)).strftime('%m/%d/%Y')
                span = 75
            checks = [
                ('initial', 'Expansion excludes dates before the origin and handles the initial period boundary.',
                 dict(cli('-Q', '--from', first, '--days', str(span)), success=True)),
                ('future', 'Expansion at a distant date respects interval, until, exception and calendar rules.',
                 dict(cli('-Q', '--from', future, '--days', str(span)), success=True)),
                ('native', 'The recurrence is readable in the native public record format.',
                 dict(cli('-G'), success=True)),
                ('ical-rule', 'iCalendar export preserves the recurrence rule and exception properties.',
                 dict(cli('-xical', part='ical'), summary=label,
                      properties=['RRULE', 'EXDATE;VALUE=DATE', 'EXDATE'], success=True)),
            ]
            cases.append((step(name, 'Expand and export the ' + name + ' ' + kind + ' series.', [], checks),
                          home(apts=[line])))
        out += scenarios('recurrence-' + kind, 'recurrence', cases, chunk=8)

    # Week origin changes a multi-week union of weekdays; it is a real configuration input.
    for firstday in ['monday', 'sunday']:
        out.append(program('recurrence-weekstart-' + firstday, 'recurrence',
            home(apts=[event('2026-03-17', 'Fortnightly', '2W w0 w2')],
                 conf={'general.firstdayofweek': firstday}), [
            step('expand', 'Expand a fortnightly Sunday/Tuesday series with the configured week start.', [],
                 [('dates', 'Week origin determines which Sundays belong to each fortnight.',
                   dict(cli('-Q', '--from', '03/01/2026', '--days', '75'), success=True))])]))
    return out

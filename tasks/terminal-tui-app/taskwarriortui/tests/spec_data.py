"""Fixture task sets of the specification (Taskwarrior JSON, fixed UUIDs, distinct entry dates).

The application's clock stays at 2026-05-13 10:00:00 UTC (a Wednesday). Every fixture task has its own entry date,
so no two tasks tie on urgency and report orders are deterministic.
"""
from spec_core import T

# The main fixture: projects with subprojects, tags, priorities, due dates (overdue, today, tomorrow, later),
# scheduled, waiting, an active task, an annotation, a dependency, completed and deleted tasks.
MAIN = [
    T(1, 'Pay rent', entry='20260501T080000Z', project='Home', tags=['bills'], due='20260515T000000Z', priority='H'),
    T(2, 'Write report', entry='20260420T080000Z', project='Work'),
    T(3, 'Call plumber', entry='20260505T080000Z', project='Home.Repairs', tags=['phone'], due='20260510T120000Z'),
    T(4, 'Review PR', entry='20260512T080000Z', project='Work.Code', tags=['code'], priority='M',
      due='20260513T180000Z', start='20260513T090000Z'),
    T(5, 'Buy groceries', entry='20260511T080000Z', tags=['shop', 'errand'], due='20260514T000000Z', priority='L'),
    T(6, 'Plan trip', entry='20260502T080000Z', project='Travel', scheduled='20260520T000000Z'),
    T(7, 'Renew passport', status='waiting', entry='20260503T080000Z', project='Travel', wait='20260601T000000Z',
      due='20260701T000000Z'),
    T(8, 'Read book', entry='20260301T080000Z', notes=[('20260302T080000Z', 'Chapter 3')]),
    T(9, 'Fix bike', entry='20260506T080000Z', depends=[5]),
    T(10, 'Old chore', status='completed', entry='20260401T080000Z', end='20260512T090000Z'),
    T(11, 'Deleted thing', status='deleted', entry='20260402T080000Z', end='20260511T090000Z'),
    T(12, 'Water plants', entry='20260425T080000Z', tags=['garden'], priority='L', due='20260520T000000Z'),
    T(13, 'Learn piano', entry='20260210T080000Z', project='Music', tags=['hobby'], until='20261231T000000Z'),
    T(14, 'Team lunch', entry='20260508T080000Z', project='Work', tags=['social'], due='20260513T120000Z'),
]
MAIN_NAMES = [t['description'] for t in MAIN]
PENDING = [t['description'] for t in MAIN if t['status'] == 'pending']

# A plain list for navigation and paging: twenty pending tasks whose urgency falls with the list position.
LIST = [T(100 + i, f'Item {chr(65 + i)}{chr(65 + i)}', entry=f'2026{1 + i // 28:02d}{1 + i % 28:02d}T080000Z')
        for i in range(20)]
SHORT = LIST[:6]

# Small sets for actions.
TRIO = [
    T(21, 'Alpha task', entry='20260401T080000Z', project='Alpha'),
    T(22, 'Beta task', entry='20260402T080000Z', project='Beta', tags=['beta']),
    T(23, 'Gamma task', entry='20260403T080000Z', priority='M'),
]

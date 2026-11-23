"""Literal scheduled-transaction documents and independent calendar expectations.

The scenarios distinguish every repeat frequency, finite completion, overdue
catch-up, the due-date boundary, month/leap-year rollover and separate posting
and reminder dates. Each scenario uses ordinary fields of an MMEX document.
"""
import calendar
from datetime import date, timedelta

import fixtures

TODAY = date(2026, 6, 15)
FREQUENCIES = (
    ('once', 0), ('daily', 10), ('weekly', 1), ('fortnightly', 2),
    ('four-weeks', 9), ('monthly', 3), ('two-months', 4),
    ('quarterly', 5), ('four-months', 8), ('half-yearly', 6),
    ('yearly', 7), ('month-end', 15), ('last-business-day', 16),
    ('in-days', 11), ('in-months', 12), ('every-days', 13), ('every-months', 14),
)


def add_months(value, months):
    total = value.year * 12 + value.month - 1 + months
    year, month = total // 12, total % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def following(value, frequency, interval):
    days = {10: 1, 1: 7, 2: 14, 9: 28}
    months = {3: 1, 4: 2, 5: 3, 8: 4, 6: 6, 7: 12}
    if frequency in days:
        return value + timedelta(days=days[frequency])
    if frequency in months:
        return add_months(value, months[frequency])
    if frequency in (11, 13):
        return value + timedelta(days=interval)
    if frequency in (12, 14):
        return add_months(value, interval)
    if frequency in (15, 16):
        result = add_months(value.replace(day=1), 1)
        result = result.replace(day=calendar.monthrange(result.year, result.month)[1])
        if frequency == 16:
            while result.weekday() >= 5:
                result -= timedelta(days=1)
        return result
    raise ValueError(frequency)


def scenarios(group=None):
    result = []
    for fi, (name, frequency) in enumerate(FREQUENCIES):
        family = 'fixed' if fi < 5 else 'calendar' if fi < 13 else 'custom'
        if group and group != family:
            continue
        cases = [
            ('today-final', '2026-06-15', 1, None),
            ('overdue-finite', '2026-05-30', 3, None),
            ('overdue-open', '2026-01-31', -1, None),
            ('future', '2026-06-16', 3, None),
            ('short-month', '2026-02-28', 2, None),
            ('leap-year', '2024-02-29', 2, None),
            ('posting-before-due', '2026-06-10', 3, '2026-06-14'),
            ('posting-after-due', '2026-06-18', 2, '2026-06-15'),
        ]
        if frequency == 0:
            cases = [c for c in cases if c[0] not in ('short-month', 'leap-year')]
        for ci, (boundary, stamp, number, due) in enumerate(cases):
            code = ('Withdrawal', 'Deposit', 'Transfer')[ci % 3]
            interval = (1, 3, 7, 2, 2, 12, 5, 1)[ci] if frequency in (11, 12, 13, 14) else number
            # Long-interval modes still exercise leap-day rollover without
            # generating hundreds of years of irrelevant daily entries.
            if frequency in (11, 13) and boundary == 'leap-year':
                interval = 365
            tag = name + '-' + boundary
            split = code != 'Transfer' and ci in (1, 4, 6)
            amount = (0.01, 125.75, 110.0, 19.99, 42.5, 2500.0, 65.25, 75.0)[ci]
            result.append(dict(
                key=tag, group=family, frequency=frequency, num=interval,
                date=stamp, due=due or stamp, type=code,
                account='Euro Daily' if ci == 4 else 'Main Account',
                to='Euro Daily' if code == 'Transfer' else None,
                amount=amount, to_amount=100.0 if code == 'Transfer' else 0.0,
                payee=None if code == 'Transfer' else ('Employer' if code == 'Deposit' else 'Local Store'),
                category=None if split else ('Transfer' if code == 'Transfer' else 'Income:Salary' if code == 'Deposit' else 'Food:Groceries'),
                status=('', 'R', 'F', '', 'V', 'D', 'R', '')[ci],
                number='INV-' + tag, notes=tag, time='14:25:36' if ci % 2 else '00:00:00',
                tags=('work', 'shared') if ci % 2 else ('household',),
                splits=(('Food:Groceries', amount - 5.0, 'food', ('household',)),
                        ('Bills:Water', 5.0, 'water', ('work', 'shared'))) if split else (),
            ))
    return result


def document(group):
    ledger = fixtures.Ledger(rates={'EUR': 1.1})
    ledger.account('Main Account', balance=1000000)
    ledger.account('Euro Daily', balance=1000000, currency='EUR')
    ledger.payee('Local Store', 'Food:Groceries')
    ledger.payee('Employer', 'Income:Salary')
    for item in scenarios(group):
        ledger.sched(item['account'], item['type'], item['amount'], item['date'],
                     freq=item['frequency'], mode=2, num=item['num'],
                     payee=item['payee'], category=item['category'], status=item['status'],
                     number=item['number'], notes=item['notes'], to=item['to'],
                     to_amount=item['to_amount'], due=item['due'], tags=item['tags'],
                     splits=item['splits'], time=item['time'])
    return ledger.bytes()


def expectation(item):
    frequency = item['frequency']
    interval = item['num']
    remaining = 1 if frequency == 0 else 2 if frequency in (11, 12) else -1 if frequency in (13, 14) else interval
    posted, due = date.fromisoformat(item['date']), date.fromisoformat(item['due'])
    if due > TODAY:
        # Loading a future schedule does not rewrite its stored repeat count,
        # even when the effective execution count of its frequency is one.
        return [], [{'date': item['date'], 'next_date': item['due'],
                     'repeats': float(200 + frequency), 'occurrences': float(interval)}]
    dates = []
    while due <= TODAY:
        dates.append(posted.isoformat())
        if remaining == 1:
            return dates, []
        posted = following(posted, frequency, interval)
        due = following(due, frequency, interval)
        if remaining > 0:
            remaining -= 1
        if frequency in (11, 12):
            frequency = 0
            interval = 1
    return dates, [{'date': posted.isoformat(), 'next_date': due.isoformat(),
                    'repeats': float(200 + frequency),
                    'occurrences': float(interval if frequency in (11, 12, 13, 14) else remaining)}]

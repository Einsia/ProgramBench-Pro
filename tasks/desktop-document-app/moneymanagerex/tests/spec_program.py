"""Product startup processes scheduled transactions without any evaluator actions."""
from spec_common import program, episode, step, inbox, rows, row, count, info
import schedule_cases


def build():
    episodes = []
    for group in ('fixed', 'calendar', 'custom'):
        checks = []
        for case in schedule_cases.scenarios(group):
            dates, remaining = schedule_cases.expectation(case)
            match = {'notes': case['key']}
            if not dates:
                checks += count('trx', match, 0)
                checks += rows('sched', ['date', 'next_date', 'repeats', 'occurrences'], match=match,
                               expect=remaining, slug_text=case['key'] + '-future-preserved')
                checks += row('sched', match, account=case['account'], to_account=case['to'] or '',
                              type=case['type'], amount=case['amount'], to_amount=case['to_amount'],
                              payee=case['payee'] or '', category=case['category'] or '', status=case['status'],
                              number=case['number'], tags=sorted(case['tags']))
                continue
            def aspect(label, fields, values):
                return rows('trx', fields, match=match, sort=['date', 'time'],
                            slug_text=case['key'] + '-' + label,
                            expect=[dict(zip(fields, values(d))) for d in dates])
            checks += aspect('posting-dates', ['date', 'time'], lambda d: [d, case['time']])
            checks += aspect('accounts-and-direction', ['account', 'to_account', 'type'],
                             lambda d: [case['account'], case['to'] or '', case['type']])
            checks += aspect('amounts', ['amount', 'to_amount'], lambda d: [case['amount'], case['to_amount']])
            checks += aspect('payee-and-category', ['payee', 'category'], lambda d: [case['payee'] or '', case['category'] or ''])
            checks += aspect('status', ['status'], lambda d: [case['status']])
            checks += aspect('reference', ['number'], lambda d: [case['number']])
            checks += aspect('tags', ['tags'], lambda d: [sorted(case['tags'])])
            if case['splits']:
                splits = sorted([{'category': s[0], 'amount': s[1], 'notes': s[2], 'tags': sorted(s[3])} for s in case['splits']],
                                key=lambda s: s['category'].casefold())
                checks += aspect('split-details', ['splits'], lambda d: [splits])
            if remaining:
                checks += rows('sched', ['date', 'next_date', 'repeats', 'occurrences'], match=match,
                               expect=remaining, slug_text=case['key'] + '-next-occurrence')
            else:
                checks += count('sched', match, 0, slug_text=case['key'] + '-completed')
        key = 'scheduled-auto-' + group
        episodes.append(program(key, 'scheduled-automatic', [
            {'id': 'execute', 'goal': 'Open the prepared ledger and execute all due automated schedules.',
             'actions': [{'op': 'restart', 'database': 'ledger.mmb'}],
             'settle': {'file': 'ledger.mmb', 'quiet': 4.0, 'timeout': 120.0},
             'checks': checks},
        ], setup=[{'id': 'documents', 'op': 'documents', 'files': ['auto-' + group + '/ledger.mmb']}],
            notes='Opening the prepared ledger executes due automatic schedules, including catch-up. Future schedules are not entered.'))
    upgrade_checks = row('currency', {'symbol': 'HUF'}, prefix='', suffix='Ft')
    upgrade_checks += info('STOCKURL', 'https://finance.yahoo.com/quote/%s')
    upgrade_checks += row('trx', {'notes': 'Legacy groceries'}, account='Forint Reserve', amount=3250, category='Food:Groceries')
    upgrade_checks.append({'kind': 'schema', 'slug': 'updated-file-format', 'description': 'The document uses the current supported database format.', 'expect': 21})
    episodes.append(episode('database-upgrade', 'database', [
        step('upgrade', 'Open the older database ' + inbox('database-upgrade') + '/ledger.mmb and acknowledge the upgrade message.',
             'The upgraded database opens and the dashboard shows Forint Reserve and Dollar Reserve with their balances.',
             [{'op': 'button', 'window': 'Money Manager Ex', 'name': 'Open Existing Database'}, {'op': 'file-dialog', 'path': 'inbox/ledger.mmb'},
              {'op': 'alert', 'button': 'OK'}, {'op': 'wait', 'seconds': 2}], upgrade_checks),
    ], ledger='legacy', opened=False))
    return episodes

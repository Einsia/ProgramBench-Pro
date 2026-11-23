"""Additional offline product interfaces: search, export, keys, recurrence editing and configuration effects."""
from spec_common import *
from fixtures import ui, rich, apt, event, NOTE, AGENDA, DEFAULT_KEYS
from spec_gui import replace, goto, add_event, command, chain, goal
from spec_cli import queries


def export_steps(kind, path):
    return S(KS('x', kind), replace(path))


def keys_menu(index):
    return S(KS('C', 'k'), KS(*(['j'] * index)))


def notify_steps(index, value=None, presses=1):
    return S(KS('C', 'n'), KS(*(['j'] * index)) if index else [], [K('e')] * presses,
             replace(value) if value is not None else [], W(1) if index == 0 else [], K('q'), K('q'))


def edit_rule(period, frequency, until, weekdays='', months='', monthdays='', exceptions=None, item='apt'):
    return S(KS('e', '4' if item == 'apt' else '2', period), replace(frequency), replace(until),
             replace(exceptions) if exceptions is not None else [], replace(weekdays), replace(months),
             replace(monthdays) if period != 'w' else [], SAVE)


def recurrence_checks():
    return [('near', 'The edited recurrence generates the intended dates near its origin.',
             cli('-Q', '--from', '03/18/2026', '--days', '45', success=True)),
            ('far', 'The edited interval and end date apply to later occurrences.',
             cli('-Q', '--from', '05/01/2026', '--days', '90', success=True))]


def build():
    out = queries('search-entrypoints', 'search', rich(), [
        ('appointments', ['-a', '-S', 'Dentist|standup']),
        ('todos', ['-t', '-S', '^Priority [1-3]']),
        ('long-option', ['--todo', '--search', 'report$']),
        ('unicode', ['-a', '--search', '東京']),
        ('range', ['-r7', '-S', 'Weekly|Tomorrow|Friday']),
        ('completed', ['-t0', '-S', '^Closed [24]']),
        ('intersection', ['-t', '-S', 'task', '--filter-priority', '5']),
        ('case-sensitive', ['-t', '-S', 'Report']),
        ('no-match', ['-a', '-S', '^Not present$']),
    ])
    out.append(program('search-invalid', 'validation', rich(), [
        step('regex', 'Reject an invalid search expression.', [], [
            ('error', 'The search entry point rejects an invalid regular expression with a diagnostic.',
             cli('-a', '-S', '[', part='error', failure=True))])]))

    exported = [apt(text='Exported meeting', flagged=True, note=NOTE), event(text='Exported holiday')]
    fx = ui(apts=exported, todo=['[2] Pack bag'], notes=[NOTE], files={'saved.ics': 'Existing file\n'})
    out.append(gui('gui-export-files', 'icalendar', fx, chain([
        step('ical', 'Export the calendar as iCalendar to saved.ics in the home directory, replacing its current content. Leave the export result visible.',
             export_steps('i', 'saved.ics'), [
                 ('document', 'The saved file is a valid calendar retaining appointments, events, notes, alarms and todos.',
                  file('~/saved.ics', 'ical'))], acceptance='The application visibly confirms that the iCalendar export succeeded.',
             requires={'done': ['document']}),
        step('pcal', 'Dismiss the export result, then export the same calendar as pcal to saved.pcal and leave its result visible.',
             S(K('Enter'), export_steps('p', 'saved.pcal')), [
                 ('document', 'The pcal file retains the calendar in pcal syntax.', file('~/saved.pcal', 'pcal'))],
             acceptance='The application visibly confirms that the pcal export succeeded.', requires={'done': ['document']}),
    ])))
    out.append(program('export-replace-cancel', 'icalendar', fx, [
        step('export', 'Export successfully to an existing file.', export_steps('i', 'saved.ics'), [
            ('file', 'Export replaces the existing file with a complete calendar.', file('~/saved.ics', 'ical'))]),
        step('cancel', 'Begin another export to that file but cancel its filename prompt.',
             S(K('Enter'), KS('x', 'i'), K('Escape')), [
                 ('file', 'Cancellation retains the previously successful export.', file('~/saved.ics', 'ical'))],
             depends=['export'], requires={'file': ['export-replace-cancel/export/file']}),
        step('replace', 'Add a new event, then export to the same filename again.',
             S(add_event('Added after export'), export_steps('i', 'saved.ics')), [
                 ('file', 'The second export replaces the first and includes the added event.', file('~/saved.ics', 'ical'))], depends=['cancel']),
        step('readback', 'Import that exported file into an empty calendar through the native importer.',
             S(K('Enter'), {'place': home(apts=[], todo=[])}, CLI('-i', 'saved.ics', '-q')), [
                 ('calendar', 'The export is consumable and its appointments/events survive a round trip.', apts()),
                 ('todos', 'The exported todo survives the round trip.', todos())], depends=['replace']),
    ]))

    out.append(gui('gui-key-configuration', 'keybindings', ui(), chain([
        step('add-alias', 'In key configuration, add the unused key z as an additional binding for generic-save, retaining its current bindings. Leave the key editor, then exit the configuration menu to return to the organizer and save the key configuration. Reopen the key editor and leave that binding visible.',
             S(keys_menu(5), KS('a', 'z', 'q', 'q'), keys_menu(5)), [
                 ('binding', 'generic-save includes z and its existing aliases.', bindings('generic-save'))],
             acceptance='The key configuration has been saved by returning to the organizer, and the reopened key editor shows z assigned to generic-save alongside the existing bindings.', requires={'done': ['binding']}),
        step('use-alias', 'Return to the organizer, create an all-day event today named "Saved with z", and save it using your z binding.',
             S(KS('q', 'q', 'a'), K('Enter'), answer('Saved with z'), K('z')), [
                 ('event', 'The custom binding actually saves the new event.', dict(apts(), nonempty=True))],
             acceptance='Saved with z is visible for today and the application confirms a successful save.', requires={'done': ['event']}),
        step('remove-alias', 'Remove only the uppercase S alias from generic-save, retaining lowercase s, Ctrl+S and z. Leave the key editor, then exit the configuration menu to return to the organizer and save the key configuration. Reopen the key editor and leave its remaining bindings visible.',
             S(keys_menu(5), KS('l', 'd', 'q', 'q'), keys_menu(5)), [
                 ('binding', 'Only the specified alias is removed.', bindings('generic-save'))],
             acceptance='The key configuration has been saved by returning to the organizer, and the reopened key editor shows s and z retained in generic-save with uppercase S removed.', requires={'done': ['binding']}),
        step('restarted', 'The application has already restarted for you with the saved key configuration. Create an all-day event today named "Binding survived" and save it using z.',
             S(K('a'), K('Enter'), answer('Binding survived'), K('z')), [
                 ('event', 'The saved custom key works after a fresh process starts.', apts())],
             acceptance='Binding survived is visible and the save succeeds.', lifecycle='restart', requires={'done': ['event']}),
    ]), budget={'calls': 240, 'tokens': 2400000, 'seconds': 1800}))
    out.append(program('key-binding-conflict', 'keybindings', ui(), [
        step('conflict', 'Try to assign the already-used quit key q to generic-save.', S(keys_menu(5), KS('a', 'q')), [
            ('rejection', 'The key editor explains the conflict and retains the assignment prompt.',
             scr('contains', needles=['already used', 'generic-quit']))]),
        step('resolve', 'Dismiss the conflict and choose an unused key, then save the configuration.',
             S(K('Enter'), KS('z', 'q', 'q')), [
                 ('save', 'The replacement free key is assigned to generic-save.', bindings('generic-save')),
                 ('quit', 'The conflicting q remains assigned to generic-quit.', bindings('generic-quit'))], depends=['conflict']),
        step('old-key', 'Use the retained lowercase s binding to save a new event.', add_event('Original binding'), [
            ('saved', 'A retained alias still performs its action.', apts())], depends=['resolve']),
        step('remove-alias', 'Remove the uppercase S alias, make an unsaved event and press S.',
             S(keys_menu(5), KS('l', 'd', 'q', 'q', 'a'), K('Enter'), answer('Still pending'), K('S')), [
                 ('saved', 'The removed alias no longer saves new data.', apts())], depends=['old-key'],
             requires={'saved': ['key-binding-conflict/old-key/saved']}),
        step('retained-alias', 'Save the pending event using the retained s alias.', SAVE, [
            ('saved', 'The retained alias saves the same pending event.', apts())], depends=['remove-alias']),
    ]))

    # Editing existing rules includes interval, explicit until, exceptions and BYDAY/BYMONTH/BYMONTHDAY.
    cases = [
        ('weekly-interval', ui(apts=[apt(text='Series', rule='1W -> 05/31/2026 !03/25/2026')]),
         edit_rule('w', '2', '05/31/2026', exceptions='')),
        ('weekly-until', ui(apts=[apt(text='Series', rule='1W')]), edit_rule('w', '1', '04/15/2026')),
        ('weekly-days', ui(apts=[apt(text='Series', rule='1W')]), edit_rule('w', '1', '05/31/2026', weekdays='Mon Wed')),
        ('weekly-exception', ui(apts=[apt(text='Series', rule='1W !03/25/2026')]),
         edit_rule('w', '1', '05/31/2026', exceptions='04/01/2026')),
        ('monthly-day', ui(apts=[event(text='Series', rule='1M')]), edit_rule('m', '1', '06/30/2026', monthdays='18 -1', item='event')),
        ('yearly-months', ui(apts=[event(text='Series', rule='1Y')]), edit_rule('y', '1', '03/18/2028', months='3 6', item='event')),
    ]
    out += scenarios('edit-recurrence-rules', 'recurrence', [
        (step(name, 'Edit the existing recurrence: ' + name + '.', steps, recurrence_checks()), fx)
        for name, fx, steps in cases])
    out.append(gui('gui-edit-recurrence-rule', 'recurrence', ui(apts=[apt(text='Editable series', rule='1W -> 05/31/2026 !03/25/2026')]), chain([
        step('interval', 'Change Editable series to repeat every two weeks through May 31, 2026, and remove its exception dates. Save, then display its April 1 occurrence.',
             S(edit_rule('w', '2', '05/31/2026', exceptions=''), goto('04/01/2026')), recurrence_checks(),
             acceptance='April 1 shows Editable series from 10:00 to 11:00 with a repeating indicator.', requires={'done': ['near', 'far']}),
        step('weekdays', 'Edit the series to repeat every week on Monday and Wednesday through May 31, 2026, with no exceptions. Save, then display its April 6 occurrence.',
             S(edit_rule('w', '1', '05/31/2026', weekdays='Mon Wed'), goto('04/06/2026')), recurrence_checks(),
             acceptance='April 6 shows Editable series from 10:00 to 11:00.', requires={'done': ['near', 'far']}),
        step('ending', 'Shorten the series so its last permitted day is April 8, 2026, retaining Monday and Wednesday recurrence. Save and display its April 8 occurrence.',
             S(edit_rule('w', '1', '04/08/2026', weekdays='Mon Wed'), goto('04/08/2026')), recurrence_checks(),
             acceptance='April 8 shows the final Editable series occurrence.', requires={'done': ['near', 'far']}),
    ]), budget={'calls': 240, 'tokens': 2400000, 'seconds': 1800}))

    notify_fx = ui(apts=[apt(text='Ordinary reminder'), apt('2026-03-18 11:00', text='Flagged reminder', flagged=True)])
    out.append(gui('gui-notification-display', 'notifications', notify_fx, chain([
        step('date', 'Set the notification bar date format to "Date:%d/%m/%Y", save the configuration, and return to the organizer.',
             notify_steps(1, 'Date:%d/%m/%Y'), [('setting', 'The notification date format is saved.', conf('format.notifydate'))],
             acceptance='The notification bar displays Date:18/03/2026.', requires={'done': ['setting']}),
        step('time', 'Set the notification bar time format to "Clock:%I:%M %p", save the configuration, and return to the organizer.',
             notify_steps(2, 'Clock:%I:%M %p'), [('setting', 'The notification time format is saved.', conf('format.notifytime'))],
             acceptance='The notification bar displays Clock:09:30 AM.', requires={'done': ['setting']}),
        step('hide', 'Hide the notification bar, save the configuration, and return to the organizer.', notify_steps(0),
             [('setting', 'The notification bar display option is disabled and saved.', conf('appearance.notifybar'))],
             acceptance='The organizer shows its appointment and todo panels with the notification bar hidden.', requires={'done': ['setting']}),
        step('show', 'Show the notification bar again, save the configuration, and return to the organizer.', notify_steps(0),
             [('setting', 'The notification bar display option is enabled and saved.', conf('appearance.notifybar'))],
             acceptance='The notification bar again displays Date:18/03/2026 and Clock:09:30 AM.', requires={'done': ['setting']}),
    ])))
    notify_cases = []
    for name, index, value, count, options, needles in [
        ('date', 1, 'Day:%A', 1, ['format.notifydate'], ['Day:Wednesday']),
        ('time', 2, 'Time:%H:%M', 1, ['format.notifytime'], ['Time:09:30']),
        ('hidden', 0, None, 1, ['appearance.notifybar'], []),
        ('warning', 3, '900', 1, ['notification.warning'], []),
        ('notify-all', 5, None, 2, ['notification.notifyall'], []),
        ('unflagged', 5, None, 1, ['notification.notifyall'], []),
    ]:
        checks = [('config', 'The selected notification option is saved.', conf(*options))]
        if needles:
            checks.append(('display', 'The format affects the live notification bar.', scr('contains', needles=needles)))
        elif name == 'hidden':
            checks.append(('display', 'The appointment remains visible while the notification clock is hidden.',
                           scr('presence', present=['Ordinary reminder'], absent=['09:30:00'])))
        notify_cases.append((step(name, 'Configure ' + name + '.', notify_steps(index, value, count), checks), notify_fx))
    out += scenarios('notification-settings', 'notifications', notify_cases)

    # Configuration effects, with positive data in both branches; no timer or external command needed.
    cases = []
    for enabled in [True, False]:
        value = 'yes' if enabled else 'no'
        fx = ui(apts=[event(text='Keep'), event(text='Target')], conf={'general.confirmdelete': value})
        recipe = S(K('j'), K('d'), K('Escape') if enabled else [], SAVE)
        cases.append((step('delete-' + value, 'Delete Target with confirmdelete=' + value + '.', recipe, [
            ('data', 'Confirmation cancellation or immediate deletion changes only the target.', apts())]), fx))
        fx = ui(apts=[event(text='Persisted')], conf={'general.confirmquit': value})
        cases.append((step('quit-' + value, 'Quit with confirmquit=' + value + '.', [K('q')], [
            ('process', 'The quit confirmation controls whether the application is still running.', scr('process'))]), fx))
        orphan = 'Orphan note\n'
        fx = ui(apts=[apt(note=NOTE)], notes=[NOTE, orphan], conf={'general.autogc': value, 'general.confirmquit': 'no'})
        cases.append((step('gc-' + value, 'Quit with autogc=' + value + '.', [K('q')], [
            ('notes', 'Automatic collection removes only unreferenced notes when enabled.', notes_dir())]), fx))
    out += scenarios('configuration-effects', 'configuration', cases)
    out.append(gui('gui-reload-choice', 'persistence', ui(apts=[event(text='Saved original')]), chain([
        step('retain', 'Rename Saved original to "Unsaved edit" without saving. Invoke reload but cancel it to retain your unsaved edit.',
             S(K('e'), replace('Unsaved edit'), KS('R', 'a')), [
                 ('display', 'Cancelling reload retains the in-memory edit.', scr('contains', needles=['Unsaved edit']))],
             acceptance='Unsaved edit remains visible after cancelling reload.', requires={'done': ['display']}),
        step('discard', 'Reload the saved data, discarding the unsaved edit.', S(KS('R', 'c')), [
            ('display', 'Reload restores the saved description.', scr('contains', needles=['Saved original']))],
            acceptance='Saved original is visible again.', requires={'done': ['display']}),
    ])))
    return out

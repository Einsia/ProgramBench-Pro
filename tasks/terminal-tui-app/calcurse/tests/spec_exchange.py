"""iCalendar imports, exports, native purging and note garbage collection."""
from spec_common import *
from fixtures import *
from ical_semantics import parse_calendar


def import_cases():
    base = 'DTSTART:20260318T100000\nSUMMARY:Imported item'
    events = [
        ('timed-start-only', base),
        ('timed-end', base + '\nDTEND:20260318T113000'),
        ('minute-duration', base + '\nDURATION:PT1M'),
        ('hours-duration', base + '\nDURATION:PT2H15M'),
        ('days-duration', base + '\nDURATION:P2DT3H4M'),
        ('weeks-duration', base + '\nDURATION:P1W'),
        ('utc', 'DTSTART:20260318T100000Z\nDTEND:20260318T113000Z\nSUMMARY:Imported item'),
        ('timezone', 'DTSTART;TZID=Europe/Berlin:20260318T100000\nDTEND;TZID=Europe/Berlin:20260318T110000\nSUMMARY:Imported item'),
        ('midnight-end', 'DTSTART:20260318T230000\nDTEND:20260319T000000\nSUMMARY:Imported item'),
        ('overnight', 'DTSTART:20260318T230000\nDTEND:20260319T010000\nSUMMARY:Imported item'),
        ('leap-day', 'DTSTART:20280229T235900\nDURATION:PT2M\nSUMMARY:Imported item'),
        ('all-day', 'DTSTART;VALUE=DATE:20260318\nSUMMARY:Imported item'),
        ('all-day-end', 'DTSTART;VALUE=DATE:20260318\nDTEND;VALUE=DATE:20260319\nSUMMARY:Imported item'),
        ('all-day-span', 'DTSTART;VALUE=DATE:20260318\nDTEND;VALUE=DATE:20260321\nSUMMARY:Imported item'),
        ('all-day-duration', 'DTSTART;VALUE=DATE:20260318\nDURATION:P3D\nSUMMARY:Imported item'),
        ('description', base + '\nDESCRIPTION:First line\\nSecond line\\, semicolon\\; slash\\\\'),
        ('location', base + '\nLOCATION:Room 4\\, East wing'),
        ('comments', base + '\nCOMMENT:First comment\nCOMMENT:Second comment'),
        ('all-note-fields', base + '\nDESCRIPTION:Agenda\nLOCATION:Room 2\nCOMMENT:Bring water'),
        ('alarm', base + '\nBEGIN:VALARM\nACTION:DISPLAY\nTRIGGER:-PT15M\nDESCRIPTION:Reminder\nEND:VALARM'),
        ('folded-summary', 'DTSTART:20260318T100000\nSUMMARY:A long sum\n mary continued\n\t with a tab'),
        ('unicode', 'DTSTART:20260318T100000\nSUMMARY:Réunion 東京\nDESCRIPTION:Crème brûlée'),
        ('escaped-summary', 'DTSTART:20260318T100000\nSUMMARY:Comma\\, semi\\; slash\\\\'),
        ('property-order', 'SUMMARY:Imported item\nDTEND:20260318T110000\nDTSTART:20260318T100000'),
        ('unknown-property', base + '\nX-CUSTOM:ignored\nTRANSP:TRANSPARENT'),
    ]
    for name, rrule in [
        ('daily', 'FREQ=DAILY'), ('weekly', 'FREQ=WEEKLY;INTERVAL=2'),
        ('monthly', 'FREQ=MONTHLY'), ('yearly', 'FREQ=YEARLY'),
        ('count', 'FREQ=DAILY;COUNT=5'), ('until', 'FREQ=DAILY;UNTIL=20260323T100000'),
        ('weekdays', 'FREQ=WEEKLY;BYDAY=MO,WE,FR'),
        ('monthly-ordinal', 'FREQ=MONTHLY;BYDAY=1MO,-1FR'),
        ('monthly-days', 'FREQ=MONTHLY;BYMONTHDAY=1,15,-1'),
        ('yearly-months', 'FREQ=YEARLY;BYMONTH=3,6,9'),
        ('friday-13', 'FREQ=MONTHLY;BYDAY=FR;BYMONTHDAY=13'),
        ('yearly-ordinal', 'FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU'),
    ]:
        origin = {'monthly-ordinal': '20260302', 'monthly-days': '20260301',
                  'friday-13': '20260313', 'yearly-ordinal': '20260329'}.get(name, '20260318')
        events.append(('rrule-' + name, base.replace('20260318', origin) + '\nRRULE:' + rrule))
    events += [
        ('exdate-time', base + '\nRRULE:FREQ=DAILY;COUNT=5\nEXDATE:20260319T100000,20260321T100000'),
        ('exdate-day', 'DTSTART;VALUE=DATE:20260318\nSUMMARY:Imported item\nRRULE:FREQ=DAILY;COUNT=5\nEXDATE;VALUE=DATE:20260319'),
    ]
    for name, props in events:
        yield name, 'event', ical(vevent(props))
    for priority in range(10):
        yield 'todo-priority-' + str(priority), 'todo', ical(vtodo('SUMMARY:Imported task\nPRIORITY:' + str(priority)))
    for name, props in [
        ('default', 'SUMMARY:Imported task'),
        ('completed', 'SUMMARY:Imported task\nPRIORITY:3\nSTATUS:COMPLETED'),
        ('needs-action', 'SUMMARY:Imported task\nPRIORITY:4\nSTATUS:NEEDS-ACTION'),
        ('note', 'SUMMARY:Imported task\nDESCRIPTION:One\\nTwo'),
        ('location-comment', 'SUMMARY:Imported task\nLOCATION:Home\nCOMMENT:Weekend'),
        ('unicode', 'SUMMARY:Tâche 東京\nPRIORITY:2'),
        ('folded', 'SUMMARY:Task with a long\n  description'),
        ('alarm', 'SUMMARY:Imported task\nBEGIN:VALARM\nACTION:DISPLAY\nTRIGGER:-PT5M\nEND:VALARM'),
    ]:
        yield 'todo-' + name, 'todo', ical(vtodo(props))


def build():
    out, cases = [], []
    for name, kind, content in import_cases():
        args = ['-i', 'exchange.ics', '--dump-imported', '-q']
        checks = [
            ('reported', 'The importer reports the imported native items.', cli(*args, last=True, success=True)),
            ('stored', 'Imported entries persist in the appropriate native data file.', todos() if kind == 'todo' else apts()),
            ('export', 'The imported data can be exported as calendar components.', cli('-xical', part='ical', success=True)),
        ]
        components = parse_calendar(content)['children']
        if any(name in ('DESCRIPTION', 'LOCATION', 'COMMENT') or 'TZID' in params
               for component in components for name, params, value in component['properties']):
            checks.append(('notes', 'Imported text properties are preserved in linked note files.',
                           dict(notes_dir(), nonempty=True)))
        cases.append((step(name, 'Import the supplied iCalendar document and inspect the result.', [CLI(*args)], checks),
                      home(apts=[], todo=[], files={'exchange.ics': content})))
    out += scenarios('import', 'icalendar', cases, chunk=8)

    # Malformed/unsupported items are surrounded by good items, so a parser cannot pass by ignoring the input.
    invalid = [
        ('zero-duration', 'DTSTART:20260318T100000\nDURATION:PT0M\nSUMMARY:Broken'),
        ('missing-start', 'SUMMARY:Broken'), ('missing-summary', 'DTSTART:20260318T100000'),
        ('bad-start', 'DTSTART:bogus\nSUMMARY:Broken'),
        ('end-before-start', 'DTSTART:20260318T100000\nDTEND:20260318T090000\nSUMMARY:Broken'),
        ('negative-duration', 'DTSTART:20260318T100000\nDURATION:-PT1H\nSUMMARY:Broken'),
        ('bad-duration', 'DTSTART:20260318T100000\nDURATION:bad\nSUMMARY:Broken'),
        ('date-time-mismatch', 'DTSTART;VALUE=DATE:20260318\nDTEND:20260319T100000\nSUMMARY:Broken'),
        ('rrule-count-until', 'DTSTART:20260318T100000\nSUMMARY:Broken\nRRULE:FREQ=DAILY;COUNT=3;UNTIL=20260320T100000'),
        ('rrule-unknown-frequency', 'DTSTART:20260318T100000\nSUMMARY:Broken\nRRULE:FREQ=HOURLY'),
        ('rrule-no-frequency', 'DTSTART:20260318T100000\nSUMMARY:Broken\nRRULE:COUNT=3'),
        ('rrule-invalid-weekday', 'DTSTART:20260318T100000\nSUMMARY:Broken\nRRULE:FREQ=WEEKLY;BYDAY=XX'),
        ('rrule-invalid-month', 'DTSTART:20260318T100000\nSUMMARY:Broken\nRRULE:FREQ=YEARLY;BYMONTH=13'),
    ]
    cases=[]
    for name, props in invalid:
        text = ical(vevent('DTSTART;VALUE=DATE:20260318\nSUMMARY:Before') + '\n' + vevent(props) + '\n' +
                    vtodo('SUMMARY:After\nPRIORITY:2'))
        args=['-i','exchange.ics','--dump-imported','-q']
        cases.append((step(name,'Import a mixed document containing an invalid item.',[CLI(*args)],[
            ('reported','Good items are reported even when another component is invalid.',cli(*args,last=True)),
            ('calendar','The calendar reflects the documented handling of the invalid item.',apts()),
            ('todo','The valid following todo is retained.',todos()),
        ]), home(apts=[],todo=[],files={'exchange.ics':text})))
    out += scenarios('import-recovery','validation',cases)

    # Export each property once, with fixtures selected to make it non-default.
    cal=[event(text='One day',note=NOTE),event(text='Repeating day',rule='2M -> 12/18/2026 !05/18/2026',note=AGENDA),
         apt(text='Timed',minutes=95,note=NOTE,flagged=True),
         apt(text='Repeating time',minutes=1500,rule='1W w1 w3',note=AGENDA,flagged=True)]
    todo=['[2]>'+sha1(NOTE)+' Open task','[-4]>'+sha1(AGENDA)+' Closed task']
    cps=[]
    for title, props in [
        ('One day',['DTSTART;VALUE=DATE','SUMMARY','DESCRIPTION']),
        ('Repeating day',['DTSTART;VALUE=DATE','RRULE','EXDATE;VALUE=DATE','SUMMARY','DESCRIPTION']),
        ('Timed',['DTSTART','DURATION','SUMMARY','DESCRIPTION','VALARM']),
        ('Repeating time',['DTSTART','DURATION','RRULE','SUMMARY','DESCRIPTION','VALARM']),
        ('Open task',['PRIORITY','SUMMARY','DESCRIPTION']),
        ('Closed task',['PRIORITY','SUMMARY','DESCRIPTION','STATUS']),
    ]:
        cps.append(step(slug(title),'Export the public fields of '+title+'.',[],[
            (slug(p),'Exported '+p+' for '+title+'.',cli('-xical',part='ical',summary=title,properties=[p],success=True))
            for p in props] + [('uid','The optional export UID is the item hash.',
                              cli('-xical','--export-uid',part='ical',summary=title,properties=['UID'],success=True))]))
    out.append(program('export-properties','icalendar',home(apts=cal,todo=todo,notes=[NOTE,AGENDA]),cps))
    cases=[]
    for kind in ['event','apt','recur-event','recur-apt','todo','cal','recur']:
        cases.append(step('filter-'+kind,'Export only '+kind+' items.',[],[
            ('components','The exported components match the selected types.',
             cli('-xical','--filter-type',kind,part='ical',success=True))]))
    cases.append(step('pcal','Export the calendar in pcal format.',[],[
        ('text','The pcal export describes the calendar in the supported format.',cli('-xpcal',success=True))]))
    out.append(program('export-selection','icalendar',rich(),cases))

    # Purge has inverted selection semantics. Fresh fixtures prevent one case from gating later cases.
    cases=[]
    filters=[['--filter-type',k] for k in ['event','apt','recur-event','recur-apt','todo','cal','recur']]
    filters += [['--filter-pattern','task$'],['--filter-completed'],['--filter-priority','3'],
                ['--filter-type','cal','--filter-start-before','03/18/2026'],
                ['--filter-type','todo','--filter-uncompleted','--filter-priority','5']]
    for i, flt in enumerate(filters):
        cases.append((step('purge-'+str(i+1),'Remove entries matching '+repr(flt)+'.',[CLI('-P',*flt)],[
            ('calendar','Nonmatching calendar entries remain after purge.',apts()),
            ('tasks','Nonmatching todo entries remain after purge.',todos()),
        ]),rich()))
    out += scenarios('purge','persistence',cases)
    out.append(program('filter-writeback','persistence',rich(),[
        step('readonly','Apply purge in read-only mode.',[CLI('--read-only','-P','--filter-type','todo')],[
            ('tasks','Read-only mode prevents purge from changing the saved todos.',todos())]),
        step('retain','Retain only matching calendar entries with the legacy filter operation.',[CLI('-F','--filter-type','cal')],[
            ('calendar','Matching calendar entries are retained.',apts()),
            ('tasks','The legacy filter removes nonmatching todos.',todos())],depends=['readonly']),
    ]))
    orphan='Unreferenced note.\n'
    out.append(program('note-gc','notes',home(apts=[apt(note=NOTE)],todo=['[1]>'+sha1(AGENDA)+' Task'],
                        notes=[NOTE,AGENDA,orphan]),[
        step('collect','Collect unreferenced note files.',[CLI('-g')],[
            ('notes','The garbage collector retains both linked notes and removes the orphan.',notes_dir())]),
        step('purge-task','Remove the todo, then collect notes again.',[CLI('-P','--filter-type','todo'),CLI('-g')],[
            ('notes','The formerly linked todo note is collected while the appointment note remains.',notes_dir())],depends=['collect']),
    ]))
    return out

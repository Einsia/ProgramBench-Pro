"""Small, deliberately varied calendars in the product's public text format."""
from datetime import datetime, timedelta
from spec_common import home, sha1

NOTE = 'Bring the X-rays.\nSecond line: café, tea; water.\n'
AGENDA = 'Agenda:\n- budget\n- hiring\n'
TODOS = ([f'[{p}] Priority {p} task' for p in range(10)] +
         [f'[-{p}] Closed {p} task' for p in range(1, 10)] +
         ['[3] Alpha report', '[3] beta report', '[3] Café 東京',
          '[5] Buy milk, bread; eggs', '[2]>' + sha1(AGENDA) + ' Prepare slides'])
CALENDAR = [
    '03/17/2026 [1] Yesterday event',
    '03/18/2026 [1] Alpha event',
    '03/18/2026 [1] >' + sha1(AGENDA) + ' Board meeting',
    '03/19/2026 [1] Tomorrow event',
    '03/20/2026 [1] Friday event',
    '03/22/2026 [1] Sunday picnic',
    '03/18/2026 @ 00:00 -> 03/18/2026 @ 00:01|Midnight start',
    '03/18/2026 @ 08:00 -> 03/18/2026 @ 09:00|Early standup',
    '03/18/2026 @ 09:30 -> 03/18/2026 @ 10:00|At clock time',
    '03/18/2026 @ 10:00 -> 03/18/2026 @ 11:30>' + sha1(NOTE) + ' |Dentist',
    '03/18/2026 @ 12:00 -> 03/18/2026 @ 12:00!Lunch call',
    '03/18/2026 @ 14:00 -> 03/18/2026 @ 15:00|Café 東京',
    '03/18/2026 @ 23:00 -> 03/19/2026 @ 01:00|Night shift',
    '03/17/2026 @ 23:00 -> 03/18/2026 @ 00:00|Ends at midnight',
    '03/17/2026 @ 23:00 -> 03/18/2026 @ 01:00|From yesterday',
    '03/25/2026 @ 14:00 -> 03/25/2026 @ 15:00|Future review',
    '03/16/2026 @ 09:00 -> 03/16/2026 @ 09:30 {1W} >' + sha1(NOTE) + ' |Weekly sync',
    '03/01/2026 [1] {1M} >' + sha1(AGENDA) + ' Rent due',
    '03/01/2026 [1] {1D -> 03/20/2026 !03/19/2026} Daily journal',
    '03/16/2026 @ 07:00 -> 03/16/2026 @ 07:45 {2D -> 04/01/2026} !Morning run',
]


def rich(**extra):
    return home(apts=CALENDAR, todo=TODOS, notes=[NOTE, AGENDA], **extra)


def apt(start='2026-03-18 10:00', minutes=60, text='Meeting', rule=None, note=None, flagged=False):
    t = datetime.strptime(start, '%Y-%m-%d %H:%M')
    end = t + timedelta(minutes=minutes)
    return (t.strftime('%m/%d/%Y @ %H:%M') + ' -> ' + end.strftime('%m/%d/%Y @ %H:%M') +
            (' {' + rule + '} ' if rule else '') + ('>' + sha1(note) + ' ' if note else '') +
            ('!' if flagged else '|') + text)


def event(date='2026-03-18', text='Holiday', rule=None, note=None):
    return (datetime.strptime(date, '%Y-%m-%d').strftime('%m/%d/%Y') + ' [1] ' +
            ('{' + rule + '} ' if rule else '') + ('>' + sha1(note) + ' ' if note else '') + text)


def ui(apts=(), todo=(), panel='appointments', **kw):
    config = {'appearance.defaultpanel': panel, 'general.multipledays': 'no'}
    config.update(kw.pop('conf', {}))
    return home(apts=apts, todo=todo, conf=config, **kw)


def ical(body):
    return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Calendar fixtures//EN\r\n' + body.replace('\n', '\r\n') + '\r\nEND:VCALENDAR\r\n'


def vevent(properties):
    return 'BEGIN:VEVENT\n' + properties + '\nEND:VEVENT'


def vtodo(properties):
    return 'BEGIN:VTODO\n' + properties + '\nEND:VTODO'

# Default bindings observed through the public files channel.
DEFAULT_KEYS = '#\n# Calcurse keys configuration file\n#\n# In this file the keybindings used by Calcurse are defined.\n# It is generated automatically by Calcurse and is maintained\n# via the key configuration menu of the interactive user\n# interface. It should not be edited directly.\n\ngeneric-cancel  ESC\ngeneric-select  SPC\ngeneric-credits  @\ngeneric-help  ?\ngeneric-quit  q Q\ngeneric-save  s S ^S\ngeneric-reload  R\ngeneric-copy  c\ngeneric-paste  p ^V\ngeneric-change-view  TAB\ngeneric-prev-view  KEY_BTAB\ngeneric-import  i I\ngeneric-export  x X\ngeneric-goto  g G\ngeneric-other-cmd  o O\ngeneric-config-menu  C\ngeneric-redraw  ^R\ngeneric-add-appt  ^A\ngeneric-add-todo  ^T\ngeneric-prev-day  T ^H\ngeneric-next-day  t ^L\ngeneric-prev-week  W ^K\ngeneric-next-week  w\ngeneric-prev-month  M\ngeneric-next-month  m\ngeneric-prev-year  Y\ngeneric-next-year  y\ngeneric-scroll-down  ^N\ngeneric-scroll-up  ^P\ngeneric-goto-today  ^G\ngeneric-command  :\nmove-right  l L RGT\nmove-left  h H LFT\nmove-down  j J DWN\nmove-up  k K UP\nstart-of-week  0\nend-of-week  $\nadd-item  a A\ndel-item  d D\nedit-item  e E\nview-item  v V RET\npipe-item  |\nflag-item  !\nrepeat  r\nedit-note  n N\nview-note  >\nraise-priority  +\nlower-priority  -\n'

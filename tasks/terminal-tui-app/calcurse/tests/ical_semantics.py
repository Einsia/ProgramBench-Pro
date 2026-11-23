"""Semantic projections of calcurse's public iCalendar output (RFC 5545).

Validate the calendar envelope and component nesting before selecting fields.
Do not require UID, DTSTAMP or alarm DESCRIPTION: upstream does not emit them.
Property and component order, explicit defaults and extension metadata do not
change the calendar data. Meaningful standard fields and duplicate items do.
"""
from datetime import datetime, timezone
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def split_quoted(text, delimiter):
    return re.split(delimiter + r'(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', text)


def content_line(line):
    quoted = False
    for index, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ':' and not quoted:
            return line[:index], line[index + 1:]
    raise AssertionError('invalid iCalendar content line')


def parse_calendar(text):
    lines = re.sub(r'\r?\n[ \t]', '', text).replace('\r\n', '\n').splitlines()
    roots, stack = [], []
    for line in lines:
        if not line:
            continue
        head, value = content_line(line)
        fields = split_quoted(head, ';')
        name, params = fields[0].upper(), {}
        if not re.fullmatch('[A-Z0-9-]+', name):
            raise AssertionError('invalid iCalendar property name')
        for field in fields[1:]:
            key, sep, val = field.partition('=')
            if not sep or key.upper() in params:
                raise AssertionError('invalid iCalendar property parameter')
            params[key.upper()] = val.strip('"')
        if name == 'BEGIN':
            kind = value.upper()
            if params:
                raise AssertionError('component boundary has parameters')
            if not stack and kind != 'VCALENDAR':
                raise AssertionError('export must have a VCALENDAR envelope')
            if stack:
                parent = stack[-1]['type']
                if kind in ('VEVENT', 'VTODO', 'VTIMEZONE') and parent != 'VCALENDAR':
                    raise AssertionError('invalid calendar component nesting')
                if kind == 'VALARM' and parent not in ('VEVENT', 'VTODO'):
                    raise AssertionError('alarm outside an event or todo')
                if kind == 'VCALENDAR':
                    raise AssertionError('nested calendar envelope')
            node = {'type': kind, 'properties': [], 'children': []}
            (stack[-1]['children'] if stack else roots).append(node)
            stack.append(node)
        elif name == 'END':
            if params or not stack or stack[-1]['type'] != value.upper():
                raise AssertionError('unmatched iCalendar component boundary')
            stack.pop()
        else:
            if not stack:
                raise AssertionError('property outside calendar envelope')
            stack[-1]['properties'].append((name, params, value))
    if stack or len(roots) != 1 or roots[0]['type'] != 'VCALENDAR':
        raise AssertionError('missing or incomplete VCALENDAR envelope')
    versions = [v for n, p, v in roots[0]['properties'] if n == 'VERSION']
    if versions != ['2.0']:
        raise AssertionError('calendar must declare VERSION:2.0')
    return roots[0]


def text_value(value):
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1].lower() == 'n' else m[1], value)


def duration(value):
    m = re.fullmatch(r'([+-]?)P(?:(\d+)W|(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?)', value.upper())
    if not m or not any(m.groups()[1:]):
        raise AssertionError('invalid calendar duration')
    sign = -1 if m[1] == '-' else 1
    w, d, h, minute, sec = [int(x or 0) for x in m.groups()[1:]]
    return sign * (w * 604800 + d * 86400 + h * 3600 + minute * 60 + sec)


def date_value(value, params):
    value_type = params.get('VALUE', 'DATE-TIME').upper()
    if value_type == 'DATE':
        try:
            # calcurse 4.8.2 exports all-day EXDATE with a midnight suffix even
            # though VALUE=DATE is set. Accept both that upstream form and DATE.
            if re.fullmatch(r'\d{8}T000000', value):
                value = value[:8]
            return datetime.strptime(value, '%Y%m%d').strftime('%Y-%m-%d'), True
        except ValueError as exc:
            raise AssertionError('invalid calendar date') from exc
    if value_type != 'DATE-TIME':
        raise AssertionError('invalid calendar time value type')
    try:
        utc = value.endswith('Z')
        t = datetime.strptime(value.removesuffix('Z'), '%Y%m%dT%H%M%S')
        zone = timezone.utc if utc or not params.get('TZID') else ZoneInfo(params['TZID'])
        return int(t.replace(tzinfo=zone).timestamp()), False
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise AssertionError('invalid calendar time or timezone') from exc


def recurrence(value):
    result = {}
    for field in value.split(';'):
        name, sep, val = field.partition('=')
        name = name.upper()
        if not sep or not val or name in result:
            raise AssertionError('invalid recurrence field')
        if name in ('INTERVAL', 'COUNT'):
            try:
                val = int(val)
            except ValueError as exc:
                raise AssertionError('invalid recurrence count') from exc
            if val <= 0:
                raise AssertionError('nonpositive recurrence count')
        elif name.startswith('BY'):
            items = val.upper().split(',')
            if name == 'BYDAY':
                if any(not re.fullmatch(r'[+-]?\d*(?:MO|TU|WE|TH|FR|SA|SU)', x) for x in items):
                    raise AssertionError('invalid recurrence weekday')
                items = [re.sub(r'^\+?0*(\d+)', lambda m: str(int(m[1])), x) for x in items]
            else:
                try:
                    items = [int(x) for x in items]
                except ValueError as exc:
                    raise AssertionError('invalid recurrence list') from exc
            val = sorted(set(items))
        else:
            val = val.upper()
        result[name] = val
    if result.get('FREQ') not in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY', 'HOURLY', 'MINUTELY', 'SECONDLY'):
        raise AssertionError('missing or invalid recurrence frequency')
    result.setdefault('INTERVAL', 1)
    result.setdefault('WKST', 'MO')
    return result


TEXT_FIELDS = {'SUMMARY', 'DESCRIPTION', 'LOCATION', 'COMMENT', 'CONTACT'}
DATE_FIELDS = {'DTSTART', 'DTEND', 'DUE', 'EXDATE', 'RDATE', 'COMPLETED'}
DATA_FIELDS = TEXT_FIELDS | DATE_FIELDS | {'TYPE', 'DURATION', 'RRULE', 'PRIORITY', 'STATUS', 'VALARM'}
ALARM_FIELDS = {'ACTION', 'TRIGGER', 'REPEAT', 'DURATION', 'DESCRIPTION', 'SUMMARY', 'ATTACH', 'ATTENDEE'}


def property_value(name, params, value):
    if name in TEXT_FIELDS:
        return name, [text_value(value)]
    if name in DATE_FIELDS:
        dates = [date_value(v, params) for v in value.split(',')]
        if len({date for _, date in dates}) != 1:
            raise AssertionError('mixed date types in one calendar property')
        return name + (';VALUE=DATE' if dates[0][1] else ''), [v for v, _ in dates]
    if name == 'RRULE':
        return name, [recurrence(value)]
    if name == 'DURATION':
        return name, [duration(value)]
    if name in ('PRIORITY', 'REPEAT'):
        try:
            return name, [int(value)]
        except ValueError as exc:
            raise AssertionError('invalid integer calendar property') from exc
    if name == 'TRIGGER':
        if params.get('VALUE', 'DURATION').upper() == 'DATE-TIME':
            return name, [{'at': date_value(value, params)[0]}]
        return name, [{'seconds': duration(value), 'related': params.get('RELATED', 'START').upper()}]
    if name in ('STATUS', 'ACTION'):
        return name, [value.upper()]
    return name, [value]


def component(node, *, include_uid=False):
    result = {'TYPE': [node['type']]}
    allowed = ALARM_FIELDS if node['type'] == 'VALARM' else DATA_FIELDS | ({'UID'} if include_uid else set())
    for name, params, value in node['properties']:
        if name not in allowed:
            continue
        key, values = property_value(name, params, value)
        result.setdefault(key, []).extend(values)
    if node['type'] == 'VALARM':
        if len(result.get('ACTION', [])) != 1 or not result['ACTION'][0] or len(result.get('TRIGGER', [])) != 1:
            raise AssertionError('alarm must retain its action and trigger')
    else:
        alarms = [component(c) for c in node['children'] if c['type'] == 'VALARM']
        if alarms:
            result['VALARM'] = sorted(alarms, key=stable)
        # Equivalent event end forms: duration or an absolute DTEND.
        if 'DTEND' in result and 'DTSTART' in result:
            derived = result['DTEND'][0] - result['DTSTART'][0]
            if 'DURATION' in result and result['DURATION'] != [derived]:
                raise AssertionError('inconsistent event end and duration')
            result['DURATION'] = [derived]
            del result['DTEND']
        if 'DTEND;VALUE=DATE' in result and 'DTSTART;VALUE=DATE' in result:
            start = datetime.fromisoformat(result['DTSTART;VALUE=DATE'][0])
            end = datetime.fromisoformat(result['DTEND;VALUE=DATE'][0])
            result['DURATION'] = [int((end - start).total_seconds())]
            del result['DTEND;VALUE=DATE']
        if node['type'] == 'VEVENT':
            result.setdefault('DURATION', [86400 if 'DTSTART;VALUE=DATE' in result else 0])
    for key, values in result.items():
        result[key] = sorted(values, key=stable)
    return result


def project_calendar(text, check):
    root = parse_calendar(text)
    # Validate all alarms, including those outside the selected assertion slice.
    wanted = check.get('properties')
    components = [component(c, include_uid=bool(wanted and 'UID' in wanted))
                  for c in root['children'] if c['type'] in ('VEVENT', 'VTODO')]
    if not components:
        raise AssertionError('export did not contain any calendar components')
    selected = [c for c in components if not check.get('summary') or c.get('SUMMARY') == [check['summary']]]
    if check.get('summary') and len(selected) != 1:
        raise AssertionError('exported item missing or duplicated: ' + check['summary'])
    if wanted:
        selected = [{p: c.get(p) for p in wanted} for c in selected]
    return sorted(selected, key=stable)

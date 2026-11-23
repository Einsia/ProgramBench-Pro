"""Exported documents: CSV, QIF, JSON, XML spreadsheets and HTML pages decoded into comparable values."""
import csv
from html.parser import HTMLParser
import io
import json
import re
import xml.etree.ElementTree as ET


def decode(data):
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', 'replace')


def lines(text):
    return [line.strip() for line in text.replace('\r\n', '\n').split('\n') if line.strip()]


NUMBER = re.compile(r'^[^\d\-(]*(-?)\(?([\d\s., \']*\d)\)?[^\d]*$')


def to_number(token):
    """A displayed amount as a number; None when the token is not one. Currency symbols and group separators are ignored."""
    token = token.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:[T ].*)?', token) or '/' in token:
        return None
    if not token or not re.search(r'\d', token) or re.search(r'[A-Za-z]{2,}', token.replace('USD', '').replace('EUR', '').replace('GBP', '')):
        return None
    negative = '-' in token or (token.startswith('(') and token.endswith(')'))
    digits = re.sub(r'[^\d.,]', '', token)
    if not digits:
        return None
    if ',' in digits and '.' in digits:
        if digits.rfind(',') > digits.rfind('.'):
            digits = digits.replace('.', '').replace(',', '.')
        else:
            digits = digits.replace(',', '')
    elif ',' in digits:
        head, _, tail = digits.rpartition(',')
        digits = head.replace(',', '') + ('.' + tail if len(tail) != 3 else tail)
    try:
        value = float(digits)
    except ValueError:
        return None
    return -value if negative else value


def cell(value):
    """A cell of a delimited file: numbers as numbers, the rest as trimmed text."""
    value = value.strip()
    if re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        return float(value)
    return value


def table(data, delimiter=','):
    text = decode(data)
    return [[cell(item) for item in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in row)]


def qif_records(data):
    """Records of a QIF file: [{'!': section, 'D': date, 'T': amount, ... , 'S': [...]}] in file order."""
    records, record, section = [], {}, ''
    for line in decode(data).replace('\r\n', '\n').split('\n'):
        if not line:
            continue
        if line.startswith('!'):
            section = line[1:].strip()
            continue
        code, value = line[0], line[1:].strip()
        if code == '^':
            if record:
                record['!'] = section
                records.append(record)
            record = {}
        elif code in record:
            record[code] = (record[code] if isinstance(record[code], list) else [record[code]]) + [value]
        else:
            record[code] = value
    if record:
        record['!'] = section
        records.append(record)
    return records


def spreadsheet_rows(data):
    """Rows of an XML Spreadsheet 2003 document or any XML table: lists of cell texts."""
    root = ET.fromstring(decode(data).lstrip())
    rows = []
    for row in root.iter():
        if row.tag.rsplit('}', 1)[-1] == 'Row':
            cells = []
            for item in row:
                if item.tag.rsplit('}', 1)[-1] == 'Cell':
                    cells.append(cell(''.join(item.itertext())))
            rows.append(cells)
    return rows


class _Tokens(HTMLParser):
    SKIP = {'script', 'style', 'head', 'title'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens, self.depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            text = ' '.join(data.split())
            if text:
                self.tokens.append(text)


def html_tokens(data):
    parser = _Tokens()
    parser.feed(decode(data))
    parser.close()
    return parser.tokens


class _Tables(HTMLParser):
    """Visible table cells, without depending on a report's HTML styling."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.parts = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.parts = []

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.row is not None and self.parts is not None:
            self.row.append(' '.join(''.join(self.parts).split()))
            self.parts = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row, self.parts = None, None

    def handle_data(self, value):
        if self.parts is not None:
            self.parts.append(value)


def html_cells(data, label, occurrence=0, columns=None):
    parser = _Tables()
    parser.feed(decode(data))
    found = [(row, i) for row in parser.rows for i, value in enumerate(row) if value.casefold() == label.casefold()]
    if occurrence >= len(found):
        raise AssertionError(f'the report has no table row {label!r} (occurrence {occurrence})')
    row, i = found[occurrence]
    selected = [row[c] for c in columns] if columns else row[i + 1:]
    if not columns:
        while selected and not selected[-1]:
            selected.pop()
    return [to_number(value) if to_number(value) is not None else value for value in selected]


def html_row(tokens, label, occurrence=0, count=None):
    """The amounts that follow a row label in the page's text, in reading order."""
    seen = -1
    folded = label.casefold()
    for index, token in enumerate(tokens):
        if token.casefold() == folded:
            seen += 1
            if seen == occurrence:
                values = []
                for following in tokens[index + 1:]:
                    number = to_number(following)
                    if number is None:
                        break
                    values.append(number)
                    if count is not None and len(values) == count:
                        break
                return values
    return None


def observe(data, check):
    """The part of a document one assertion scores."""
    form = check['form']
    if form.startswith('semantic-'):
        import interchange
        return interchange.observe(data, check)
    if form == 'csv':
        rows = table(data, check.get('delimiter', ','))
        if 'row' in check:
            index = check['row']
            if index >= len(rows):
                raise AssertionError(f'the file has only {len(rows)} rows')
            row = rows[index]
            if 'columns' in check:
                return [row[c] if c < len(row) else None for c in check['columns']]
            return row
        return len(rows)
    if form in ('csv-record', 'csv-records'):
        records = list(csv.DictReader(io.StringIO(decode(data)), delimiter=check.get('delimiter', ',')))
        found = [r for r in records if all(r.get(k, '').strip() == str(v) for k, v in check['match'].items())]
        if form == 'csv-records':
            if not found:
                raise AssertionError('no CSV rows match the requested transaction')
            result = [{key: cell(r.get(key, '')) for key in check['fields']} for r in found]
            return sorted(result, key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
        if len(found) != 1:
            raise AssertionError(f'{len(found)} CSV rows match {check["match"]}')
        return {key: cell(found[0].get(key, '')) for key in check['fields']}
    if form == 'json-record':
        records = json.loads(decode(data))[check['collection']]
        found = [r for r in records if all(r.get(k) == v for k, v in check['match'].items())]
        if len(found) != 1:
            raise AssertionError(f'{len(found)} JSON rows match {check["match"]}')
        return {key: found[0].get(key) for key in check['fields']}
    if form == 'qif-record':
        found = [r for r in qif_records(data) if all(r.get(k) == v for k, v in check['match'].items())]
        if len(found) != 1:
            raise AssertionError(f'{len(found)} QIF records match {check["match"]}')
        def value(key):
            raw = found[0].get(key, '')
            if key in ('T', '$'):
                return [to_number(x) for x in raw] if isinstance(raw, list) else to_number(raw)
            return raw
        return {key: value(key) for key in check['fields']}
    if form == 'lines':
        return lines(decode(data))
    if form == 'qif':
        records = qif_records(data)
        if 'record' in check:
            if check['record'] >= len(records):
                raise AssertionError(f'the file has only {len(records)} records')
            record = records[check['record']]
            return record.get(check['code'], '') if 'code' in check else record
        return len(records)
    if form == 'xml':
        rows = spreadsheet_rows(data)
        if 'row' in check:
            if check['row'] >= len(rows):
                raise AssertionError(f'the document has only {len(rows)} rows')
            selected = rows[check['row']]
            return [selected[i] for i in check['columns']] if check.get('columns') else selected
        return len(rows)
    if form == 'json':
        value = json.loads(decode(data))
        for key in check.get('path', ()):
            if isinstance(value, list):
                if not isinstance(key, int) or key >= len(value):
                    raise AssertionError(f'no element {key} in the JSON document')
                value = value[key]
            else:
                if key not in value:
                    raise AssertionError(f'no key {key} in the JSON document')
                value = value[key]
        return value
    if form == 'html-row':
        values = html_row(html_tokens(data), check['label'], check.get('occurrence', 0), check.get('count'))
        if values is None:
            raise AssertionError(f'the page has no row {check["label"]!r}')
        return values
    if form == 'html-cells':
        return html_cells(data, check['label'], check.get('occurrence', 0), check.get('columns'))
    if form == 'html-number-cells':
        cells=html_cells(data,check['label'],check.get('occurrence',0),check.get('columns'))
        result=[]
        for value in cells:
            if isinstance(value,(int,float)):
                result.append(value)
            else:
                parts=[to_number(part) for part in value.split()]
                if not parts or any(v is None for v in parts):
                    raise AssertionError('report cell does not contain the requested numeric results')
                result.append(parts)
        return result
    if form == 'html-has':
        tokens = html_tokens(data)
        text = ' '.join(tokens).casefold()
        return [item for item in check['texts'] if item.casefold() in text]
    raise ValueError('unknown document form ' + form)

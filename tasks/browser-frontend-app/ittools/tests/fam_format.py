'''Program episodes: JSON, YAML, TOML, XML and CSV converters and formatters.'''
import json

from pbuild import NL, blocks, case, fields, fill, lines, multi, point, reload, switch, toggles, episode

INPUTS = {'type': 'inputs'}
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)
NUM = 'Please Input'


def Q(text):
    '''Samples are written with backticks where a double quote is meant.'''
    return text.replace(chr(96), chr(34))


def rows(*items):
    return Q(NL.join(items))


def converter(key, page, label, samples, refusal, default=None):
    '''samples: (id, goal, requirement, text). The first sample is the companion of the refusal point.'''
    cases = [case(cid, goal, page, [fill(text, label=label)], [point('result', req, blocks())])
             for cid, goal, req, text in samples]
    if default:
        cases.append(case('default', 'Open the page without typing.', page, [],
                          [point('result', default, multi(input=fields(label), output=blocks()))]))
    goal, req, text = refusal
    cases.append(case('refused', goal, page, [fill(text, label=label)],
                      [point('message', req, multi(text=lines(start=label), output=blocks(allow_empty=True)), [samples[0][0] + '/result'])]))
    return episode(key, 'converter', cases)


def yaml_to_json():
    return converter('yaml-to-json-converter', '/yaml-to-json-converter', 'Your YAML', [
        ('mapping', 'Type a YAML mapping with a nested mapping, a boolean, a null and a decimal.',
         'The YAML is shown as JSON indented with three spaces.',
         rows('name: box', 'size:', '  w: 3', '  h: 4.5', 'ok: true', 'none: null')),
        ('sequence', 'Type a YAML list of a scalar, a mapping and an inline list.', 'Lists become JSON arrays.',
         rows('- a', '- b: 1', '- [x, y]')),
        ('alias', 'Type a YAML mapping that reuses an anchor with an alias.',
         'An alias is expanded to a copy of the anchored value.', rows('base: &b', '  k: 1', 'copy: *b')),
        ('block-text', 'Type a YAML mapping with a literal block text and a folded block text.',
         'Block scalars keep their line breaks or fold them.',
         rows('text: |', '  line one', '  line two', 'folded: >', '  joined', '  words')),
        ('quoted', 'Type a YAML mapping with a quoted number, a plain number, a date and a tilde.',
         'Only unquoted numbers become JSON numbers.', rows('a: `1`', 'b: 1', 'c: 2024-01-02', 'd: ~')),
        ('unicode', 'Type a YAML mapping with non-Latin text.', 'Non-Latin characters are kept as they are.',
         'word: ' + UNI),
    ], ('Type a YAML list that is never closed.', 'Invalid YAML is refused with a message and no JSON is shown.',
        'a: [1, 2'))


def json_to_yaml():
    return converter('json-to-yaml-converter', '/json-to-yaml-converter', 'Your JSON', [
        ('object', 'Type a JSON object with nested values.', 'The object is shown as YAML.',
         json.dumps({'name': 'box', 'tags': ['a', 'b'], 'size': {'w': 3, 'h': 4.5}, 'ok': True, 'none': None})),
        ('array', 'Type a JSON array of objects.', 'Arrays become YAML lists.', '[{"id": 1}, {"id": 2, "x": [true]}]'),
        ('json5', 'Type JSON5 with unquoted keys, single quotes, a comment and a trailing comma.',
         'JSON5 syntax is accepted.', rows('{', '  // note', '  key: ' + chr(39) + 'value' + chr(39) + ',', '  list: [1, 2,],', '}')),
        ('scalar', 'Type a JSON string.', 'A top-level string is shown as YAML text.', rows('`plain words`')),
        ('multiline', 'Type a JSON string with a line break.', 'A multi-line string is shown as a block.',
         json.dumps({'text': 'one' + NL + 'two'})),
        ('unicode', 'Type a JSON object with non-Latin text.', 'Non-Latin characters are kept.',
         json.dumps({'word': UNI}, ensure_ascii=False)),
    ], ('Type JSON that is cut off.', 'Invalid JSON is refused with a message and no YAML is shown.', '{a:'))


def json_to_toml():
    return converter('json-to-toml', '/json-to-toml', 'Your JSON', [
        ('flat', 'Type a flat JSON object of text, numbers and a boolean.', 'Each pair becomes a key and a value.',
         json.dumps({'title': 'box', 'count': 3, 'ratio': 1.5, 'ok': True})),
        ('tables', 'Type a JSON object with nested objects.', 'A nested object becomes a table.',
         json.dumps({'owner': {'name': 'Tom', 'age': 30}, 'db': {'ports': [1, 2], 'opts': {'x': 'y'}}})),
        ('array-tables', 'Type a JSON object with an array of objects.', 'An array of objects becomes an array of tables.',
         json.dumps({'items': [{'id': 1}, {'id': 2}]})),
        ('arrays', 'Type a JSON object with arrays of numbers and text.', 'Arrays of scalars stay inline.',
         json.dumps({'n': [1, 2, 3], 's': ['a', 'b']})),
        ('quotes', 'Type a text value with quotes and a backslash.', 'Special characters are escaped.',
         json.dumps({'q': 'say ' + chr(34) + 'hi' + chr(34) + ' ' + chr(92) + ' there'})),
        ('unicode', 'Type a JSON object with non-Latin text.', 'Non-Latin characters are kept.',
         json.dumps({'word': UNI}, ensure_ascii=False)),
    ], ('Type JSON that is cut off.', 'Invalid JSON is refused with a message and no TOML is shown.', '{' + chr(34) + 'a' + chr(34) + ':'))


def toml_to_json():
    return converter('toml-to-json', '/toml-to-json', 'Your TOML', [
        ('tables', 'Type a TOML document with a title and a table.', 'Tables become nested JSON objects.',
         rows('title = `box`', '', '[owner]', 'name = `Tom`', 'age = 30')),
        ('array-tables', 'Type a TOML document with two array-of-tables entries.', 'They become an array of objects.',
         rows('[[items]]', 'id = 1', '', '[[items]]', 'id = 2')),
        ('types', 'Type TOML with a boolean, a float, a hexadecimal number, a list and an inline table.',
         'Values keep their types.',
         rows('flag = true', 'ratio = 1.5', 'hex = 0xff', 'list = [1, 2, 3]', 'inline = { a = 1, b = `x` }')),
        ('date', 'Type a TOML date and time.', 'A date is shown as an ISO text.', 'when = 1979-05-27T07:32:00Z'),
        ('multiline', 'Type a TOML multi-line text.', 'Line breaks are kept.', rows('text = ```', 'one', 'two```')),
        ('unicode', 'Type TOML with non-Latin text.', 'Non-Latin characters are kept.', Q('word = `' + UNI + '`')),
    ], ('Type a TOML key without a value.', 'Invalid TOML is refused with a message and no JSON is shown.', 'a = '))


def toml_to_yaml():
    return converter('toml-to-yaml', '/toml-to-yaml', 'Your TOML', [
        ('tables', 'Type a TOML document with a title and a table.', 'Tables become nested YAML mappings.',
         rows('title = `box`', '', '[owner]', 'name = `Tom`', 'age = 30')),
        ('array-tables', 'Type a TOML document with two array-of-tables entries.', 'They become a YAML list.',
         rows('[[items]]', 'id = 1', '', '[[items]]', 'id = 2')),
        ('types', 'Type TOML with a boolean, a float and a list.', 'Values keep their types.',
         rows('flag = true', 'ratio = 1.5', 'list = [1, 2, 3]')),
        ('date', 'Type a TOML date and time.', 'A date is shown as a YAML timestamp.', 'when = 1979-05-27T07:32:00Z'),
        ('unicode', 'Type TOML with non-Latin text.', 'Non-Latin characters are kept.', Q('word = `' + UNI + '`')),
    ], ('Type a TOML key without a value.', 'Invalid TOML is refused with a message and no YAML is shown.', 'a = '))


def yaml_to_toml():
    return converter('yaml-to-toml', '/yaml-to-toml', 'Your YAML', [
        ('mapping', 'Type a YAML mapping with a nested mapping.', 'A nested mapping becomes a table.',
         rows('name: box', 'size:', '  w: 3', '  h: 4.5', 'ok: true')),
        ('list-of-maps', 'Type a YAML list of mappings.', 'A list of mappings becomes an array of tables.',
         rows('items:', '  - id: 1', '  - id: 2')),
        ('lists', 'Type YAML lists of numbers and text.', 'Lists of scalars stay inline.',
         rows('n: [1, 2, 3]', 's:', '  - a', '  - b')),
        ('unicode', 'Type YAML with non-Latin text.', 'Non-Latin characters are kept.', 'word: ' + UNI),
    ], ('Type a YAML list that is never closed.', 'Invalid YAML is refused with a message and no TOML is shown.', 'a: [1, 2'))


def xml_to_json():
    return converter('xml-to-json', '/xml-to-json', 'Your XML content', [
        ('attributes', 'Type XML with attributes and two child elements of the same name.',
         'Attributes go under _attributes and repeated elements become an array.',
         rows('<root id=`1` name=`box`>', '  <item>one</item>', '  <item>two</item>', '</root>')),
        ('cdata', 'Type XML with a CDATA section followed by text.', 'CDATA is kept apart from the text.',
         '<a><![CDATA[raw <b> text]]> tail</a>'),
        ('nested', 'Type nested XML with an empty element.', 'Nesting follows the elements.', '<a><b><c>deep</c></b><d/></a>'),
        ('declaration', 'Type XML with a declaration, a comment and an attribute.', 'Declaration and comment are kept.',
         rows('<?xml version=`1.0` encoding=`UTF-8`?><!-- note --><r x=`1`>t</r>')),
        ('unicode', 'Type XML with non-Latin text.', 'Non-Latin characters are kept.', '<w>' + UNI + '</w>'),
    ], ('Type XML with a mismatched closing tag.', 'Invalid XML gives no JSON.',
        '<a><b></a>'), default='The page starts with a sample element converted to JSON.')


def json_to_xml():
    return converter('json-to-xml', '/json-to-xml', 'Your JSON content', [
        ('attributes', 'Type JSON with _attributes and _text keys.', 'The keys become attributes and text.',
         '{"a": {"_attributes": {"id": "1"}, "b": {"_text": "hi"}}}'),
        ('repeated', 'Type JSON with an array of values.', 'An array repeats the element.',
         '{"list": {"item": ["x", "y"]}}'),
        ('declaration', 'Type JSON with a _declaration key.', 'The declaration is written first.',
         '{"_declaration": {"_attributes": {"version": "1.0"}}, "r": {}}'),
        ('escapes', 'Type JSON with a text that contains a less-than and an ampersand.', 'Special characters are escaped.',
         json.dumps({'a': {'_text': '1 < 2 & 3'}})),
        ('cdata', 'Type JSON with a _cdata key.', 'The text is written as CDATA.', json.dumps({'a': {'_cdata': 'raw <b>'}})),
        ('plain-values', 'Type JSON with a text, a number and a boolean.', 'Plain values become element text.',
         '{"a": "text", "b": 5, "c": true}'),
    ], ('Type JSON that is cut off.', 'Invalid JSON is refused with a message and no XML is shown.', '{' + chr(34) + 'a' + chr(34) + ':'),
        default='The page starts with a sample object converted to XML.')


def json_minify():
    return converter('json-minify', '/json-minify', 'Your raw JSON', [
        ('pretty', 'Type indented JSON.', 'White space between tokens is removed.', rows('{', '  `a`: [1, 2],', '  `b`: {`c`: null}', '}')),
        ('json5', 'Type JSON5 with unquoted keys and a comment.', 'JSON5 is accepted and written as plain JSON.',
         rows('{', '  // note', '  a: 1,', '  b: [2,],', '}')),
        ('spaces', 'Type JSON with repeated spaces inside a text.', 'Spaces inside texts are kept.', Q('{ `t`: `a  b` }')),
        ('nested', 'Type nested arrays and an empty object.', 'Nesting is kept.', '[[1, [2]], {}]'),
        ('unicode', 'Type JSON with non-Latin text.', 'Non-Latin characters are kept.', json.dumps({'word': UNI}, ensure_ascii=False)),
    ], ('Type JSON that is cut off.', 'Invalid JSON is refused with a message and no output is shown.', '{a:'),
        default='The page starts with a sample document, minified.')


def json_to_csv():
    return converter('json-to-csv', '/json-to-csv', 'Your raw JSON', [
        ('uniform', 'Type an array of objects with the same keys.', 'The first row holds the keys, one row per object.',
         json.dumps([{'a': 1, 'b': 'x'}, {'a': 2, 'b': 'y'}])),
        ('union', 'Type an array of objects with different keys.', 'The header is the union of the keys; missing values are empty.',
         json.dumps([{'a': 1}, {'b': 2, 'c': 3}])),
        ('escapes', 'Type an object whose texts contain a comma, quotes and a line break.', 'Commas quote the value; quotes and breaks are escaped.',
         json.dumps([{'t': 'a,b', 'q': 'say ' + chr(34) + 'hi' + chr(34), 'n': 'l1' + NL + 'l2'}])),
        ('values', 'Type an object with null, boolean, decimal and nested values.', 'Values are written as text.',
         json.dumps([{'a': None, 'b': True, 'c': 1.5, 'd': [1, 2], 'e': {'x': 1}}])),
        ('unicode', 'Type an object with non-Latin text.', 'Non-Latin characters are kept.',
         json.dumps([{'word': UNI}], ensure_ascii=False)),
    ], ('Type JSON that is cut off.', 'Invalid JSON is refused with a message and no CSV is shown.', '[{a:'))


def formatter(key, page, loc, label, sample, variants, refusal, default):
    '''variants: (id, goal, requirement, text, extra steps); the first one is the companion of the other points.'''
    name = loc.get('placeholder') or loc['label']
    first = variants[0][0] + '/result'
    cases = [case(cid, goal, page, [fill(text, **loc)] + list(extra), [point('result', req, blocks())])
             for cid, goal, req, text, extra in variants]
    cases.append(case('default', 'Open the page without typing.', page, [],
                      [point('result', default, multi(input=fields(name), output=blocks()))]))
    cases.append(case('refused', refusal[0], page, [fill(refusal[2], **loc)],
                      [point('message', refusal[1], multi(text=lines(start=label), output=blocks(allow_empty=True)), [first])]))
    cases.append(case('persist-input', 'Type a document and reload the page.', page, [fill(sample, **loc), reload()],
                      [point('state', 'The input is kept in the browser and formatted again after a reload.',
                             multi(input=fields(name), output=blocks()), [first])]))
    cases.append(case('persist-settings', 'Change the switch, set the indent size to 5, type a document and reload.', page,
                      [fill(sample, **loc), switch(0), fill('5', placeholder=NUM), reload()],
                      [point('state', 'The switch and the indent size are kept after a reload.',
                             multi(toggles=toggles(), inputs=INPUTS, output=blocks()), [first])]))
    return episode(key, 'development', cases)


def json_prettify():
    src = '[{b:1,a:[2,3]}]'
    return formatter('json-prettify', '/json-prettify', {'placeholder': 'Paste your raw JSON here...'}, 'Your raw JSON', src, [
        ('sorted', 'Type JSON5 with unsorted keys.', 'Keys are sorted and the output is indented with three spaces.', src, []),
        ('unsorted', 'Turn off Sort keys and type the same text.', 'Keys keep their order.', src, [switch(0)]),
        ('indent-0', 'Set the indent size to 0 and type the same text.', 'With no indentation the output is still split into lines.', src, [fill('0', placeholder=NUM)]),
        ('indent-8', 'Set the indent size to 8 and type the same text.', 'The output is indented with eight spaces.', src, [fill('8', placeholder=NUM)]),
        ('json5', 'Type JSON5 with a comment, single quotes, a trailing comma and a hexadecimal number.', 'JSON5 syntax is accepted.',
         rows('{', '  // note', '  key: ' + chr(39) + 'value' + chr(39) + ',', '  hex: 0x1F,', '  list: [1, 2,],', '}'), []),
        ('unicode', 'Type JSON with non-Latin text, a null and a boolean.', 'Values are kept.',
         json.dumps({'z': UNI, 'a': [None, True, 1.5]}, ensure_ascii=False), []),
        ('deep', 'Type deeply nested JSON with keys that differ only in case.', 'Sorting reaches nested objects.',
         json.dumps({'a': {'b': {'c': [1, [2, [3]]]}}, 'A': 1}), []),
    ], ('Type JSON that is not valid.', 'Invalid JSON is refused with a message.', '{a:'),
        'The page starts with a sample document, sorted and formatted.')


def yaml_prettify():
    src = rows('b: 1', 'a:', '  - x', '  - y: 2')
    return formatter('yaml-prettify', '/yaml-prettify', {'placeholder': 'Paste your raw YAML here...'}, 'Your raw YAML', src, [
        ('plain', 'Type a YAML mapping.', 'The document is written again with two spaces of indentation.', src, []),
        ('sorted', 'Turn on Sort keys and type the same text.', 'Mapping keys are sorted.', src, [switch(0)]),
        ('indent-4', 'Set the indent size to 4 and type the same text.', 'The output is indented with four spaces.', src, [fill('4', placeholder=NUM)]),
        ('alias', 'Type YAML that reuses an anchor.', 'An alias is written out again.', rows('base: &b', '  k: 1', 'copy: *b'), []),
        ('flow', 'Type YAML in flow style.', 'Flow collections are written in block style.', '{a: 1, b: [2, 3]}', []),
        ('unicode', 'Type YAML with non-Latin text.', 'Non-Latin characters are kept.', 'word: ' + UNI, []),
    ], ('Type a YAML list that is never closed.', 'Invalid YAML is refused with a message.', 'a: [1, 2'),
        'With no input the page shows the YAML of nothing.')


def xml_formatter():
    src = rows('<root><item id=`1`><name>A</name></item><item id=`2`/></root>')
    return formatter('xml-formatter', '/xml-formatter', {'label': 'Your XML'}, 'Your XML', src, [
        ('plain', 'Type XML on a single line.', 'Elements are put on lines with two spaces of indentation.', src, []),
        ('expanded', 'Turn off Collapse content and type short XML.', 'Text content is put on its own lines.', '<a><b>text</b></a>', [switch(0)]),
        ('indent-4', 'Set the indent size to 4 and type the same XML.', 'The output is indented with four spaces.', src, [fill('4', placeholder=NUM)]),
        ('indent-0', 'Set the indent size to 0 and type the same XML.', 'Without indentation each element still starts a line.', src, [fill('0', placeholder=NUM)]),
        ('declaration', 'Type XML with a declaration and a comment.', 'Declaration and comment are kept.',
         rows('<?xml version=`1.0`?><!-- note --><r><x>1</x></r>'), []),
        ('unicode', 'Type XML with non-Latin text.', 'Non-Latin characters are kept.', '<w><v>' + UNI + '</v></w>', []),
    ], ('Type XML with a mismatched closing tag.', 'Invalid XML gives no formatted output.', '<a><b></a>'),
        'The page starts with a sample document, formatted.')


def build():
    return [yaml_to_json(), json_to_yaml(), json_to_toml(), toml_to_json(), toml_to_yaml(), yaml_to_toml(), xml_to_json(),
            json_to_xml(), json_minify(), json_to_csv(), json_prettify(), yaml_prettify(), xml_formatter()]

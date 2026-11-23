'''GUI episodes: format converters and the JSON minifier driven by an evaluator.'''
import json

from gbuild import be, cp, episode
from pbuild import blocks, fields, multi

NL = chr(10)
FENCE = chr(96) * 3
QUOTE = chr(34)


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


def fill(value, label):
    return {'do': 'fill', 'value': value, 'label': label}


def seen(label):
    return multi(input=fields(label), output=blocks(allow_empty=True))


def one(cid, goal, acceptance, page, label, text, requirement, requires=()):
    return cp(cid, goal + block(*text.split(NL)), acceptance, [fill(text, label)],
              [be('result', requirement, seen(label), requires)], page=page, requires=requires)


def converters():
    yaml = NL.join(['name: box', 'size:', '  w: 3', '  h: 4'])
    toml = NL.join(['title = ' + QUOTE + 'box' + QUOTE, 'size = 3'])
    pretty = NL.join(['{', '  ' + QUOTE + 'a' + QUOTE + ': [1, 2],', '  ' + QUOTE + 'b' + QUOTE + ': {' + QUOTE + 'c' + QUOTE + ': null}', '}'])
    compact = json.dumps({'a': [1, 2], 'b': {'c': None}}, separators=(',', ':'))
    objects = json.dumps({'name': 'box', 'tags': ['a', 'b']})
    settings = json.dumps({'title': 'box', 'size': 3})
    table = json.dumps([{'a': 1, 'b': 'x'}, {'a': 2, 'b': 'y'}])
    return episode('gui-format', 'converter', [
        one('yaml-json', 'On the YAML to JSON converter, convert this YAML:', 'The JSON shows the key name with the value box and a nested object size with w 3 and h 4.', '/yaml-to-json-converter', 'Your YAML', yaml, 'The YAML is shown as JSON.'),
        one('json-yaml', 'On the JSON to YAML converter, convert this JSON:', 'The YAML shows name: box and a list tags with the items a and b.', '/json-to-yaml-converter', 'Your JSON', objects, 'The JSON is shown as YAML.'),
        one('json-toml', 'On the JSON to TOML converter, convert this JSON:', 'The TOML shows title set to box and size set to 3.', '/json-to-toml', 'Your JSON', settings, 'The JSON is shown as TOML.'),
        one('toml-json', 'On the TOML to JSON converter, convert this TOML:', 'The JSON shows title with the value box and size with the value 3.', '/toml-to-json', 'Your TOML', toml, 'The TOML is shown as JSON.'),
        one('xml-json', 'On the XML to JSON converter, convert this XML:', 'The JSON contains the values 1 and 2 taken from the two b elements.', '/xml-to-json', 'Your XML content', '<a><b>1</b><b>2</b></a>', 'The XML is shown as JSON.'),
        one('minify', 'On the JSON minifier, minify this JSON:', 'The minified JSON is ' + compact + ' on one line.', '/json-minify', 'Your raw JSON', pretty, 'The JSON is shown on one line without spaces.'),
        one('csv', 'On the JSON to CSV converter, convert this JSON:', 'The CSV has a header line with a and b and one line for each of the two objects.', '/json-to-csv', 'Your raw JSON', table, 'The JSON is shown as CSV.'),
        one('minify-invalid', 'On the JSON minifier, minify this text:', 'The page flags the text as invalid JSON and shows no minified output.', '/json-minify', 'Your raw JSON', '{a:', 'The invalid text is flagged and nothing is shown.', ['minify/result']),
    ])


def build():
    return [converters()]

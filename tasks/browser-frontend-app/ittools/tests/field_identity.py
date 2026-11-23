"""Semantic field names for pages whose reference controls expose placeholders.

The roles and order below come from the tool captions and stimuli in fam_*.py
and gui_*.py (not from a submission). `legacy` is the name_of() fallback in the
original record. Repeated fallbacks identify a slot, never an arbitrary label.
Values are not used to identify fields, and units/algorithm names stay distinct.
"""
from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class Field:
    name: str
    legacy: tuple = ()
    aliases: tuple = ()


def key(name):
    # Caption punctuation, case and accents are incidental; unit/base digits are not.
    text = unicodedata.normalize('NFKD', name.casefold().replace('ø', 'o'))
    return ''.join(c for c in text if c.isalnum())


SCHEMAS = {
    '/temperature-converter': {'inputs': tuple(
        Field(name, ('Please Input',), aliases) for name, aliases in (
            ('Kelvin', ('K',)), ('Celsius', ('°C',)), ('Fahrenheit', ('°F',)),
            ('Rankine', ('°R',)), ('Delisle', ('°De',)), ('Newton', ('°N',)),
            ('Réaumur', ('°Ré',)), ('Rømer', ('°Rø',))))},
    '/hash-text': {'outputs': tuple(Field(name, ('Input text',)) for name in
                                  ('MD5', 'SHA1', 'SHA256', 'SHA224', 'SHA512', 'SHA384', 'SHA3', 'RIPEMD160'))},
    '/keycode-info': {'outputs': (
        Field('Key', ('Key name...',), ('Key name',)), Field('Keycode', ('Keycode...',)),
        Field('Code', ('Code...',)), Field('Location', ('Code...',)), Field('Modifiers', ('None',)))},
    '/uuid-generator': {'inputs': (
        Field('Quantity', ('UUID quantity',)), Field('Namespace'), Field('Name'))},
    '/svg-placeholder-generator': {'inputs': (
        Field('Width (in px)', ('SVG width...',), ('Width',)),
        Field('Height (in px)', ('SVG height...',), ('Height',)),
        Field('Font size', ('Font size...',)), Field('Custom text'))},
    '/rsa-key-pair-generator': {'inputs': (Field('Bits', ('Please Input',)),)},
    '/string-obfuscator': {'inputs': (
        Field('String to obfuscate'), Field('Keep first', ('Please Input',)),
        Field('Keep last', ('Please Input',)))},
    '/email-normalizer': {'inputs': (
        Field('Raw emails to normalize', ('Put your emails here (one per line)...',)),)},
    '/base-converter': {'inputs': (
        Field('Input number'), Field('Input base', ('Put your input base here (ex: 10)',)),
        Field('Custom', ('Please Input',)))},
}
for language in ('JSON', 'YAML', 'XML'):
    page = '/xml-formatter' if language == 'XML' else '/%s-prettify' % language.lower()
    caption = 'Your XML' if language == 'XML' else 'Your raw ' + language
    fallback = () if language == 'XML' else ('Paste your raw %s here...' % language,)
    SCHEMAS[page] = {'inputs': (Field('Indent size', ('Please Input',)), Field(caption, fallback))}


def schema(page, group):
    return SCHEMAS.get(page.split('?', 1)[0], {}).get(group)


def resolve(name, roles, position):
    """Prefer a semantic caption; map an ambiguous legacy placeholder by slot."""
    legacy = [i for i, role in enumerate(roles) if name in role.legacy]
    if len(legacy) > 1:
        if position not in legacy:
            raise AssertionError('ambiguous field placeholder %r outside its declared slots' % name)
        return position
    named = [i for i, role in enumerate(roles) if key(name) in {key(role.name), *(key(a) for a in role.aliases)}]
    if len(named) == 1:
        return named[0]
    if len(legacy) == 1:
        return legacy[0]
    raise AssertionError('unrecognized field identity %r' % name)


def project_pairs(pairs, roles, start=0):
    """Keep each exact value attached to its field, ordered by declared identity."""
    identified = []
    for index, pair in enumerate(pairs, start):
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
            raise AssertionError('a field observation must be a [name, value] pair')
        identified.append((resolve(pair[0], roles, index), pair[1]))
    if len({i for i, _ in identified}) != len(identified):
        raise AssertionError('duplicate semantic field identity')
    return [[roles[i].name, value] for i, value in sorted(identified)]


def project_controls(controls, page, group):
    roles = schema(page, group)
    if roles is None:
        return [[c.get('label') or c.get('placeholder') or '', c.get('value', '')] for c in controls]
    pairs = []
    for index, control in enumerate(controls):
        name = control.get('label') or control.get('aria') or control.get('placeholder') or ''
        identity = resolve(name, roles, index)
        # A strong caption must not conceal a conflicting algorithm/scale/unit
        # in another public name. Unknown incidental placeholders are harmless.
        for alternate in (control.get('aria'), control.get('placeholder')):
            if not alternate or alternate == name:
                continue
            try:
                other = resolve(alternate, roles, index)
            except AssertionError:
                continue
            if other != identity:
                raise AssertionError('conflicting semantic field identities')
        pairs.append([roles[identity].name, control.get('value', '')])
    return project_pairs(pairs, roles)


def normalize(observation, page, spec):
    """Read both original records and new projections without altering frozen data."""
    if spec['type'] == 'multi':
        return {name: normalize(value, page, spec['checks'][name]) if name in spec['checks'] else value
                for name, value in observation.items()}
    group = spec['type']
    roles = schema(page, group)
    if roles is None or group == 'outputs' and not spec.get('labels') or group not in observation:
        return observation
    start = spec.get('start', 0) if group == 'outputs' else 0
    return {**observation, group: project_pairs(observation[group], roles, start)}

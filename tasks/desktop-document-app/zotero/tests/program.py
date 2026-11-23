"""Program episodes: the local API's endpoints, parameters, preconditions, errors and output formats.

No evaluator takes part. Setup writes the fixture libraries (library.py)
through the API; each point then sends its own requests and observes the
behavior-only projection of the answers (checks.py). Points that change data
use objects of their own, so that every point is judged on its own.
"""
import json
import library
import schema_types

K = library.key
U = '/api/users/0'


# ---------------------------------------------------------------------------------------------------- builders
def get(path, *views, **extra):
    return dict({'method': 'GET', 'path': path, 'view': list(views)}, **extra)


def send(method, path, payload=None, *views, headers=None, **extra):
    step = {'method': method, 'path': path, 'view': list(views)}
    if payload is not None:
        step['json'] = payload
    if headers:
        step['headers'] = headers
    step.update(extra)
    return step


def post(path, payload, *views, **extra):
    return send('POST', path, payload, *views, **extra)


def point(name, requirement, *steps, requires=()):
    """One backend point; requires names positive points of the same checkpoint (or 'checkpoint/name') that must
    pass too, for points whose own observation is a refusal or an empty answer."""
    entry = {'name': name, 'requirement': requirement, 'check': {'steps': list(steps)}}
    if requires:
        entry['requires'] = list(requires)
    return entry


def checkpoint(name, goal, points, depends=(), lifecycle=None):
    cp = {'id': name, 'goal': goal, 'points': points, 'depends': list(depends)}
    if lifecycle:
        cp['lifecycle'] = lifecycle
    return cp


API = {'id': 'api', 'op': 'api-ready'}
WARM = {'id': 'api', 'op': 'api-ready', 'warm': True}


def library_setup(*names):
    return {'id': 'library', 'op': 'library', 'libraries': list(names)}


def episode(key, feature, checkpoints, setup=(API,), initial=''):
    setup = [dict(item, id=name, libraries=[name]) if item.get('op') == 'library' else item
             for item in setup for name in (item['libraries'] if item.get('op') == 'library' else [None])]
    # Program observations recover at small checkpoint boundaries after a candidate crash.
    point_locations, cp_locations, expanded = {}, {}, []
    for cp in checkpoints:
        chunks = [cp['points'][i:i + 10] for i in range(0, len(cp['points']), 10)]
        cp_locations[cp['id']] = []
        for index, chunk in enumerate(chunks):
            name = cp['id'] if index == 0 else f'{cp["id"]}-{index + 1}'
            cp_locations[cp['id']].append(name)
            expanded.append(dict(cp, id=name, points=chunk))
            for p in chunk:
                point_locations[f'{cp["id"]}/{p["name"]}'] = f'{name}/{p["name"]}'
    original_points = {location: original for original, location in point_locations.items()}
    for cp in expanded:
        for p in cp['points']:
            original_cp = original_points[f'{cp["id"]}/{p["name"]}'].split('/')[0]
            p['requires'] = [point_locations[r if '/' in r else f'{original_cp}/{r}']
                             for r in p.get('requires', [])]
    checkpoints = expanded
    for cp in checkpoints:
        used = json.dumps(cp['points'])
        dependencies = [item for item in setup if item.get('op') != 'library' or
                        sum(x.get('op') == 'library' for x in setup) == 1 or
                        any(obj['key'] in used for part in (
                            {'items': list(library.TYPE_ITEMS.values())} if item['id'] == 'types'
                            else library.query_library()).values() for obj in part)]
        cp['depends_on'] = ['setup:' + item['id'] for item in dependencies] + [
            group for dep in cp.pop('depends') for group in
            ([f'{key}/{point_locations[dep]}'] if '/' in dep else cp_locations[dep])]
        cp['assertions'] = []
        for p in cp.pop('points'):
            entry = {'id': f'{key}/{cp["id"]}/{p["name"]}', 'channel': 'backend', 'method': 'program',
                     'requirement': p['requirement'], 'check': p['check']}
            if p.get('requires'):
                entry['requires'] = [f'{key}/{r}' if '/' in r else f'{key}/{cp["id"]}/{r}' for r in p['requires']]
            cp['assertions'].append(entry)
    return {'id': key, 'feature': feature, 'execution': 'program',
            'initial_state': 'Fresh application process with an empty DATA_DIR and a private desktop session; '
                             'the local HTTP server on PORT.' + (' ' + initial if initial else ''),
            'setup': setup, 'inputs': {}, 'checkpoints': checkpoints}


def item_path(item_key):
    return f'{U}/items/{item_key}'


SAMPLE_TYPES = ['book', 'bookSection', 'journalArticle', 'magazineArticle', 'newspaperArticle', 'thesis', 'report',
                'webpage', 'conferencePaper', 'patent', 'case', 'statute', 'film', 'dataset', 'preprint', 'manuscript',
                'letter', 'presentation', 'computerProgram', 'encyclopediaArticle']
CITE_TYPES = ['book', 'bookSection', 'journalArticle', 'webpage', 'thesis', 'case']
QUERY_SAMPLE = [2, 4, 12, 13, 15, 16, 24, 25]


def type_key(item_type):
    return library.TYPE_ITEMS[item_type]['key']


# -------------------------------------------------------------------------------------------------- schema
def schema_episode():
    types = list(schema_types.TYPES)
    lists = [
        point('item-types', 'GET /api/itemTypes lists every item type with its English name.',
              get('/api/itemTypes', 'status', 'sorted-body')),
        point('item-fields', 'GET /api/itemFields lists every item field with its English name.',
              get('/api/itemFields', 'status', 'sorted-body')),
        point('creator-fields', 'GET /api/creatorFields lists the creator name fields.',
              get('/api/creatorFields', 'status', 'body')),
        point('schema', 'GET /api/schema returns the global schema: its version, item types with fields, '
                        'creator types and base fields.', get('/api/schema', 'status', 'json:version',
                                                              'json:itemTypes')),
        point('schema-csl', 'The global schema maps item types, fields and creator types to CSL.',
              get('/api/schema', 'json:csl')),
    ]
    fields = [point(f'fields-{t}', f'GET /api/itemTypeFields?itemType={t} lists the fields of the {t} type in '
                                   'order with their English names.', get(f'/api/itemTypeFields?itemType={t}',
                                                                          'status', 'body'),
                    requires=['fields-book'] if not schema_types.TYPES[t]['fields'] else ()) for t in types]
    creators = [point(f'creators-{t}', f'GET /api/itemTypeCreatorTypes?itemType={t} lists the creator types of '
                                       f'the {t} type, the primary one first.',
                      get(f'/api/itemTypeCreatorTypes?itemType={t}', 'status', 'body'),
                      requires=['creators-book'] if not schema_types.TYPES[t]['creators'] else ()) for t in types]
    errors = [
        point('fields-missing', 'GET /api/itemTypeFields without itemType answers 400 with the reason.',
              get('/api/itemTypeFields', 'status', 'text')),
        point('fields-unknown', 'GET /api/itemTypeFields for an unknown item type answers 400 with the reason.',
              get('/api/itemTypeFields?itemType=gadget', 'status', 'text')),
        point('creators-unknown', 'GET /api/itemTypeCreatorTypes for an unknown item type answers 400.',
              get('/api/itemTypeCreatorTypes?itemType=gadget', 'status', 'text')),
        point('root', 'GET /api/ answers with its fixed text and the API, schema and server ID headers.',
              get('/api/', 'status', 'text', 'header:zotero-api-version', 'header:zotero-schema-version',
                  'has-header:zotero-server-id')),
        point('ping', 'GET /connector/ping answers that the application is running.',
              get('/connector/ping', 'status', 'text', 'header:content-type')),
    ]
    return episode('api-schema', 'schema', [
        checkpoint('lists', 'Read the item types, fields, creator fields and the global schema.', lists),
        checkpoint('fields', 'Read the fields of every item type.', fields),
        checkpoint('creators', 'Read the creator types of every item type.', creators),
        checkpoint('errors', 'Read the schema endpoints with missing or unknown parameters.', errors),
    ])


# ---------------------------------------------------------------------------------------- one item per type
def types_episode():
    points = []
    for item_type, item in library.TYPE_ITEMS.items():
        points.append(point(f'create-{item_type}', f'POST a {item_type} with every field of the type stores every '
                            'field, creator and tag, and the item reads back with its fixed dates.',
                            post(f'{U}/items', [item], 'write'),
                            get(item_path(item['key']), 'data:dateAdded,dateModified')))
        points.append(point(f'meta-{item_type}', f'The {item_type} item\'s response object carries its creator '
                            'summary, parsed date and child count, and links to itself.',
                            get(item_path(item['key']), 'meta', 'links'), requires=[f'create-{item_type}']))
    return episode('api-type-items', 'items', [
        checkpoint('types', 'Create one complete item of every item type and read each back.', points)])


# --------------------------------------------------------------------------------------------- export formats
FORMATS = ['bibtex', 'biblatex', 'ris', 'csljson', 'mods', 'refer', 'rdf_zotero', 'rdf_bibliontology', 'rdf_dc',
           'tei', 'csv', 'coins', 'wikipedia', 'bookmarks']
FULL_FORMATS = {'bibtex', 'biblatex', 'ris', 'csljson', 'mods', 'refer', 'rdf_zotero', 'rdf_bibliontology', 'tei'}


# Item types a format's translator does not export (the export is empty): left out rather than scored as empty.
UNSUPPORTED = {'rdf_bibliontology': {'dataset', 'preprint', 'standard'}}


def export_episode(fmt):
    item_types = [t for t in (schema_types.REGULAR if fmt in FULL_FORMATS else SAMPLE_TYPES[:12])
                  if t not in UNSUPPORTED.get(fmt, ())]
    collection = 'Reading List' if fmt in UNSUPPORTED else 'Biology'
    if fmt == 'bookmarks':
        item_types = ['webpage', 'computerProgram']
    types = [point(f'type-{t}', f'GET a complete {t} item with format={fmt} exports its fields in that format.',
                   get(f'{item_path(type_key(t))}?format={fmt}', 'status', f'format:{fmt}')) for t in item_types]
    sample = [point(f'item-{n}', f'GET query library item {n} with format={fmt} exports it in that format.',
                    get(f'{item_path(K("QL", n))}?format={fmt}', 'status', f'format:{fmt}'))
              for n in ([8, 18, 20] if fmt == 'bookmarks' else QUERY_SAMPLE[:5])]
    sample.append(point('collection', f'The top-level items of a collection, sorted by title, export with '
                        f'format={fmt} in that order.',
                        get(f'{U}/collections/{library.COLLECTION_KEYS[collection]}/items/top?format={fmt}&sort=title',
                            'status', 'header:content-type', f'format:{fmt}')))
    return episode(f'api-export-{fmt.replace("_", "-")}', 'export', [
        checkpoint('types', f'Export one complete item of each type with format={fmt}.', types),
        checkpoint('library', f'Export query library items and a collection with format={fmt}.', sample),
    ], setup=(WARM, library_setup('types', 'query')), initial='Setup writes one complete item of every type and '
                                                              'the query library.')


def include_episode():
    points = []
    for fmt in ('bibtex', 'ris', 'csljson', 'mods'):
        points.append(point(f'include-{fmt}', f'include={fmt} adds the item exported as {fmt} to the response '
                            'objects and leaves the data out.',
                            get(f'{item_path(K("QL", 2))}?include={fmt}', 'status', f'include:{fmt}/{fmt}',
                                'has-data')))
    points.append(point('include-data-bibtex', 'include=data,bibtex keeps the data next to the export.',
                        get(f'{item_path(K("QL", 3))}?include=data,bibtex', 'data', 'include:bibtex/bibtex')))
    points.append(point('include-list', 'include=citation on a list adds a formatted citation to every item.',
                        get(f'{U}/collections/{library.COLLECTION_KEYS["Algorithms"]}/items/top?include=citation'
                            '&sort=title', 'keys', 'include:citation/citation')))
    points.append(point('format-bib-default', 'format=bib without a style formats the bibliography in the default '
                        'style (Chicago, shortened notes).', get(f'{item_path(K("QL", 1))}?format=bib', 'status',
                                                                  'header:content-type', 'format:bib')))
    points.append(point('format-unknown', 'An unknown format answers 400 with the reason.',
                        get(f'{item_path(K("QL", 1))}?format=bogus', 'status', 'text')))
    points.append(point('format-atom', 'format=atom is not supported locally (501).',
                        get(f'{U}/items?format=atom', 'status', 'text')))
    return episode('api-export-include', 'export', [
        checkpoint('include', 'Request exports and citations through include and format.', points)],
        setup=(WARM, library_setup('query')), initial='Setup writes the query library.')


# ----------------------------------------------------------------------------------------- citation styles
STYLES = ['apa', 'chicago-shortened-notes-bibliography', 'chicago-notes-bibliography', 'chicago-author-date',
          'modern-language-association', 'ieee', 'nature', 'american-medical-association',
          'american-chemical-society', 'american-political-science-association', 'american-sociological-association',
          'elsevier-harvard', 'harvard-cite-them-right', 'mhra-notes', 'nlm-citation-sequence']


def cite_episode(style):
    bib = [point(f'bib-{t}', f'format=bib&style={style} formats the bibliography entry of a complete {t}.',
                 get(f'{item_path(type_key(t))}?format=bib&style={style}', 'status', 'format:bib'))
           for t in SAMPLE_TYPES]
    citations = [point(f'citation-{t}', f'include=citation&style={style} formats the citation of a complete {t}.',
                       get(f'{item_path(type_key(t))}?include=citation&style={style}', 'include:citation/citation'))
                 for t in (CITE_TYPES[:1] if style in {'ieee', 'nature', 'american-medical-association',
                           'american-chemical-society', 'nlm-citation-sequence'} else CITE_TYPES)]
    library_points = [point(f'item-{n}', f'format=bib&style={style} formats query library item {n}.',
                            get(f'{item_path(K("QL", n))}?format=bib&style={style}', 'format:bib'))
                      for n in QUERY_SAMPLE]
    library_points.append(point('collection', f'The items of a collection form one bibliography in {style} order.',
                                get(f'{U}/collections/{library.COLLECTION_KEYS["Reading List"]}/items/top?format=bib'
                                    f'&style={style}', 'format:bib')))
    library_points.append(point('citation-list', f'include=citation&style={style} on several items formats each.',
                                get(f'{U}/items?itemKey={K("QL", 2)},{K("QL", 12)},{K("QL", 13)}&include=citation'
                                    f'&style={style}&sort=title', 'keys', 'include:citation/citation')))
    return episode(f'api-cite-{style}', 'citation', [
        checkpoint('types', f'Format bibliography entries and citations of complete items in {style}.',
                   bib + citations),
        checkpoint('library', f'Format query library items and a collection in {style}.', library_points),
    ], setup=(WARM, library_setup('types', 'query')), initial='Setup writes one complete item of every type and '
                                                              'the query library.')


def cite_options_episode():
    points = []
    for locale in ('de-DE', 'fr-FR', 'es-ES', 'ja-JP'):
        points.append(point(f'locale-{locale}', f'locale={locale} formats an edited book section and an eight-author '
                            'article in the style\'s terms for that locale.',
                            get(f'{U}/items?itemKey={K("QL", 4)},{K("QL", 13)}&format=bib&style=chicago-author-date'
                                f'&locale={locale}', 'format:bib')))
    points.append(point('linkwrap', 'linkwrap=1 turns URLs and DOIs of the bibliography into links.',
                        get(f'{U}/items?itemKey={K("QL", 2)},{K("QL", 8)}&format=bib&style=apa&linkwrap=1',
                            'format:bib')))
    points.append(point('style-uri', 'A style may be named by its full URI.',
                        get(f'{item_path(K("QL", 2))}?format=bib&style=http://www.zotero.org/styles/ieee',
                            'format:bib')))
    points.append(point('style-unknown', 'An unknown style that cannot be installed answers 400.',
                        get(f'{item_path(K("QL", 2))}?format=bib&style=no-such-style', 'status'), requires=['style-uri']))
    points.append(point('bib-notes', 'format=bib leaves notes and attachments out of the bibliography.',
                        get(f'{U}/items?itemKey={K("QL", 2)},{K("QN", 1)},{K("QA", 1)}&format=bib&style=apa',
                            'format:bib')))
    return episode('api-cite-options', 'citation', [
        checkpoint('options', 'Format citations with locales, links and style names.', points)],
        setup=(WARM, library_setup('query')), initial='Setup writes the query library.')


# ----------------------------------------------------------------------------------------- saved searches
def search_point(name, requirement, conditions, extra=None):
    search_key = K('SS', SEARCH_NUMBERS.setdefault(name, len(SEARCH_NUMBERS) + 1))
    body = {'key': search_key, 'version': 0, 'name': name, 'conditions': conditions}
    return point(name, requirement, post(f'{U}/searches', [body], 'write'),
                 get(f'{U}/searches/{search_key}/items', 'status', 'keyset'))


SEARCH_NUMBERS = {}
C = library.COLLECTION_KEYS


def cond(condition, operator, value):
    return {'condition': condition, 'operator': operator, 'value': value}


def searches_episode():
    SEARCH_NUMBERS.clear()
    s = search_point
    fields = [
        s('title-contains', 'A saved search for titles containing a word finds those items.',
          [cond('title', 'contains', 'computable')]),
        s('title-does-not-contain', 'A saved search for titles not containing a word excludes those items '
          '(child notes and attachments are judged on their own).', [cond('title', 'doesNotContain', 'the')]),
        s('title-is', 'A saved search for an exact title finds that item only.', [cond('title', 'is', 'Algorithms')]),
        s('title-is-not', 'A saved search for titles other than one finds the rest.',
          [cond('title', 'isNot', 'Algorithms'), cond('itemType', 'isNot', 'note'), cond('itemType', 'isNot', 'attachment')]),
        s('creator-contains', 'A saved search for creators containing a name finds every item with such a creator.',
          [cond('creator', 'contains', 'dijkstra')]),
        s('creator-is', 'A saved search for an exact creator name (first and last name) finds the matching items.',
          [cond('creator', 'is', 'Tony Hoare')]),
        s('last-name', 'A saved search for a creator last name finds the matching items.',
          [cond('lastName', 'is', 'Hoare')]),
        s('author', 'A saved search for authors leaves out other creator roles.', [cond('author', 'contains', 'Hoare')]),
        s('editor', 'A saved search for editors finds edited items.', [cond('editor', 'contains', 'Randell')]),
        s('date-before', 'A saved search for dates before a year finds older items.', [cond('date', 'isBefore', '1950')]),
        s('date-after', 'A saved search for dates after a day finds newer items.', [cond('date', 'isAfter', '2015-05-14')]),
        s('date-is', 'A saved search for a year matches every date in that year.', [cond('date', 'is', '1959')]),
        s('year', 'A year condition matches the year of the date.', [cond('year', 'is', '1968')]),
        s('item-type', 'A saved search for an item type finds items of that type.', [cond('itemType', 'is', 'book')]),
        s('item-type-not', 'A saved search excluding item types finds the others.',
          [cond('itemType', 'isNot', 'journalArticle'), cond('itemType', 'isNot', 'book'), cond('itemType', 'isNot', 'note'),
           cond('itemType', 'isNot', 'attachment')]),
        s('publication', 'A saved search on the publication title finds the matching articles.',
          [cond('publicationTitle', 'contains', 'Nature')]),
        s('publisher', 'A saved search on the publisher finds the matching items.',
          [cond('publisher', 'is', 'Addison-Wesley')]),
        s('doi', 'A saved search on the DOI finds the matching item.', [cond('DOI', 'contains', '10.1007')]),
        s('language', 'A saved search on the language finds the items in that language.', [cond('language', 'is', 'de')]),
        s('any-field', 'A saved search on all fields matches any field of an item.', [cond('anyField', 'contains', 'London')]),
        s('title-creator-year', 'A title, creator and year condition matches across those fields.',
          [cond('titleCreatorYear', 'contains', 'Turing')]),
    ]
    tags = [
        s('tag-is', 'A saved search for a tag finds the items with it.', [cond('tag', 'is', 'classic')]),
        s('tag-is-not', 'A saved search excluding a tag finds the regular items without it.',
          [cond('tag', 'isNot', 'classic'), cond('itemType', 'isNot', 'note'), cond('itemType', 'isNot', 'attachment')]),
        s('tag-contains', 'A saved search for tags containing text matches every such tag.',
          [cond('tag', 'contains', 'gen')]),
        s('tag-not-contain', 'A saved search for items whose tags do not contain text finds the others.',
          [cond('tag', 'doesNotContain', 's'), cond('itemType', 'isNot', 'note'), cond('itemType', 'isNot', 'attachment')]),
        s('num-tags', 'A saved search for items with more than two tags counts their tags.',
          [cond('numTags', 'isGreaterThan', '2')]),
        s('num-notes', 'A saved search for items with child notes counts their notes.',
          [cond('numNotes', 'isGreaterThan', '0')]),
        s('num-attachments', 'A saved search for items with attachments counts them.',
          [cond('numAttachments', 'isGreaterThan', '0')]),
        s('note', 'A saved search on note text finds the notes containing it.', [cond('note', 'contains', 'helix')]),
    ]
    structure = [
        s('collection', 'A saved search for a collection finds its direct items only.',
          [cond('collection', 'is', C['Computer Science'])]),
        s('collection-recursive', 'With subcollections included, a collection condition also finds the items of '
          'its subcollections.', [cond('collection', 'is', C['Computer Science']), cond('recursive', 'true', '')]),
        s('collection-not', 'A saved search excluding a collection finds the regular items outside it.',
          [cond('collection', 'isNot', C['Biology']), cond('itemType', 'isNot', 'note'), cond('itemType', 'isNot', 'attachment')]),
        s('unfiled', 'A saved search for unfiled items finds items in no collection.', [cond('unfiled', 'true', '')]),
        s('match-any', 'With joinMode any, an item matching either condition is found.',
          [cond('joinMode', 'any', ''), cond('title', 'contains', 'species'), cond('creator', 'is', 'Barbara Liskov')]),
        s('match-all', 'Without joinMode, every condition must match.',
          [cond('tag', 'is', 'classic'), cond('date', 'isBefore', '1950')]),
        s('no-children', 'noChildren leaves child notes and attachments out.',
          [cond('title', 'contains', 'e'), cond('noChildren', 'true', '')]),
        s('parents-and-children', 'includeParentsAndChildren adds the parents and children of matching items.',
          [cond('title', 'contains', 'Computable'), cond('includeParentsAndChildren', 'true', '')]),
        s('date-added', 'dateAdded conditions compare the time items were added.',
          [cond('dateAdded', 'isAfter', '2024-03-01 01:58:00'), cond('noChildren', 'true', '')]),
        s('date-modified', 'dateModified conditions compare the time items were last changed.',
          [cond('dateModified', 'isBefore', '2024-03-01 03:25:00'), cond('noChildren', 'true', '')]),
        s('item-type-attachment', 'A saved search for attachments finds the link attachments.',
          [cond('itemType', 'is', 'attachment')]),
    ]
    nested = K('SS', 900)
    objects = [
        point('object', 'A saved search reads back with its name and conditions.',
              post(f'{U}/searches', [{'key': K('SS', 800), 'version': 0, 'name': 'Classic books',
                                       'conditions': [cond('itemType', 'is', 'book'), cond('tag', 'is', 'classic')]}],
                   'write'), get(f'{U}/searches/{K("SS", 800)}', 'object')),
        point('saved-search-condition', 'A saved search may use another saved search as a condition.',
              post(f'{U}/searches', [{'key': nested, 'version': 0, 'name': 'Classic books before 1900',
                                       'conditions': [cond('savedSearch', 'is', K('SS', 800)),
                                                      cond('date', 'isBefore', '1900')]}], 'write'),
              get(f'{U}/searches/{nested}/items', 'keyset')),
        point('list', 'GET /searches includes the two saved searches created in this checkpoint.',
              get(f'{U}/searches', 'status', f'contains-key:{K("SS", 800)}', f'contains-key:{nested}'),
              requires=['object', 'saved-search-condition']),
        point('unknown', 'The items of an unknown saved search answer 404.',
              get(f'{U}/searches/{K("SS", 999)}/items', 'status'), requires=['object']),
        point('rename', 'PATCH renames a saved search.',
              send('PATCH', f'{U}/searches/{K("SS", 800)}', {'name': 'Classic books (renamed)'}, 'status',
                   headers={'If-Unmodified-Since-Version': '{version}'}),
              get(f'{U}/searches/{K("SS", 800)}', 'data')),
        point('delete', 'DELETE removes a saved search.',
              send('DELETE', f'{U}/searches/{nested}', None, 'status',
                   headers={'If-Unmodified-Since-Version': '{version}'}),
              get(f'{U}/searches/{nested}', 'status')),
        point('invalid-condition', 'A saved search with an unknown condition is refused.',
              post(f'{U}/searches', [{'name': 'Broken', 'conditions': [cond('colour', 'is', 'red')]}], 'write')),
        point('missing-name', 'A saved search without a name is refused.',
              post(f'{U}/searches', [{'conditions': [cond('title', 'contains', 'x')]}], 'write')),
    ]
    return episode('api-searches', 'search', [
        checkpoint('fields', 'Save searches on item fields and run them.', fields),
        checkpoint('tags', 'Save searches on tags, counts and notes and run them.', tags),
        checkpoint('structure', 'Save searches on collections, join modes, children and dates and run them.',
                   structure),
        checkpoint('objects', 'Read, nest, rename and delete saved searches.', objects),
    ], setup=(API, library_setup('query')), initial='Setup writes the query library.')


# --------------------------------------------------------------------------------------------- listing
SORTS = ['dateAdded', 'dateModified', 'title', 'creator', 'itemType', 'date', 'publisher', 'publicationTitle',
         'journalAbbreviation', 'language', 'accessDate', 'libraryCatalog', 'callNumber', 'rights']


def query_episode():
    qs = [('dijkstra', None), ('graphs', None), ('1959', None), ('knuth 1968', None), ('zola', None),
          ('ORIGIN', None), ('comput', None), ('helix', 'everything'), ('Addison', 'everything'),
          ('Brussels', 'everything'), ('helix', 'titleCreatorYear'), ('Addison', 'titleCreatorYear')]
    quick = [point(f'q-{text.replace(" ", "-").lower()}-{mode or "default"}', f'q={text}' + (f'&qmode={mode}' if mode else '')
                   + ' finds the matching items (quick search).',
                   get(f'{U}/items?q={text.replace(" ", "%20")}' + (f'&qmode={mode}' if mode else ''), 'status', 'keyset'),
                   requires=[f'q-{text.lower()}-everything'] if mode == 'titleCreatorYear' else ())
             for text, mode in qs]
    filters = [
        point('tag', 'tag= finds the items with the tag.', get(f'{U}/items?tag=classic', 'keyset')),
        point('tag-not', 'tag=-x finds the items without the tag.', get(f'{U}/items?tag=-classic', 'keyset')),
        point('tag-or', 'tag=a || b finds items with either tag.', get(f'{U}/items?tag=classic%20||%20genetics', 'keyset')),
        point('tag-and', 'Two tag parameters find items with both tags.',
              get(f'{U}/items?tag=classic&tag=genetics', 'keyset')),
        point('tag-space', 'A tag with a space is matched as a whole.', get(f'{U}/items?tag=shortest%20paths', 'keyset')),
        point('tag-none', 'A tag no item has finds nothing.', get(f'{U}/items?tag=nonexistent', 'status', 'keyset'),
              requires=['tag']),
        point('item-type', 'itemType= finds the items of the type.', get(f'{U}/items?itemType=book', 'keyset')),
        point('item-type-not', 'itemType=-x finds the items of other types.',
              get(f'{U}/items?itemType=-journalArticle', 'keyset')),
        point('item-type-or', 'itemType=a || b finds items of either type.',
              get(f'{U}/items?itemType=thesis%20||%20report', 'keyset')),
        point('item-type-note', 'itemType=note finds the notes.', get(f'{U}/items?itemType=note', 'keyset')),
        point('item-key', 'itemKey= finds the listed items.',
              get(f'{U}/items?itemKey={K("QL", 1)},{K("QL", 5)},{K("QN", 3)}', 'keyset')),
        point('top', '/items/top leaves child notes and attachments out.', get(f'{U}/items/top', 'keyset')),
        point('all', '/items includes child notes and attachments.', get(f'{U}/items', 'keyset')),
        point('children', '/items/KEY/children lists an item\'s notes and attachments.',
              get(f'{U}/items/{K("QL", 2)}/children', 'keyset')),
        point('children-none', 'An item without children has an empty children list.',
              get(f'{U}/items/{K("QL", 1)}/children', 'status', 'keyset'), requires=['children']),
        point('collection-items', 'A collection lists its direct items (notes included), not those of '
              'subcollections.', get(f'{U}/collections/{C["Computer Science"]}/items', 'keyset')),
        point('collection-top', 'A collection\'s top items leave out child items.',
              get(f'{U}/collections/{C["Algorithms"]}/items/top', 'keyset')),
        point('collection-empty', 'An empty collection lists no items.',
              get(f'{U}/collections/{C["Empty Collection"]}/items', 'status', 'keyset'), requires=['collection-items']),
        point('collection-q', 'Quick search applies within a collection.',
              get(f'{U}/collections/{C["Reading List"]}/items?q=the', 'keyset')),
        point('collection-tag', 'Tag filters apply within a collection.',
              get(f'{U}/collections/{C["Biology"]}/items?tag=classic', 'keyset')),
        point('item', 'GET /items/KEY returns the item object with its data and meta.',
              get(f'{U}/items/{K("QL", 4)}', 'status', 'object:dateAdded,dateModified')),
        point('item-unknown', 'An unknown item key answers 404.', get(f'{U}/items/{K("QL", 999)}', 'status', 'text')),
        point('note-object', 'A child note reads back with its parent and HTML.',
              get(f'{U}/items/{K("QN", 1)}', 'object')),
    ]
    sorts = []
    for field in SORTS:
        for direction in ('asc', 'desc'):
            sorts.append(point(f'sort-{field}-{direction}', f'sort={field}&direction={direction} orders the top '
                               'items by that field (items with equal values in any order).',
                               get(f'{U}/items/top?sort={field}&direction={direction}', f'order:{field}')))
        sorts.append(point(f'sort-{field}-default', f'sort={field} without a direction uses the field\'s default '
                           'direction.', get(f'{U}/items/top?sort={field}', f'order:{field}')))
    sorts += [
        point('sort-invalid', 'An unknown sort field answers 400.', get(f'{U}/items?sort=colour', 'status', 'text')),
        point('direction-invalid', 'An unknown direction answers 400.',
              get(f'{U}/items?sort=title&direction=up', 'status', 'text')),
        point('sort-default', 'Without sort, items are ordered by modification date, newest first.',
              get(f'{U}/items/top', 'order:dateModified')),
    ]
    paging = [
        point('limit', 'limit= returns the first items and reports the total.',
              get(f'{U}/items/top?sort=title&limit=5', 'keys', 'header:total-results', 'header:link')),
        point('start', 'start= and limit= return a later page with first, prev, next and last links.',
              get(f'{U}/items/top?sort=title&start=5&limit=5', 'keys', 'header:total-results', 'header:link')),
        point('last-page', 'The last page links back to the first page.',
              get(f'{U}/items/top?sort=title&start=25&limit=5', 'keys', 'header:link')),
        point('start-beyond', 'A start beyond the end returns no items.',
              get(f'{U}/items/top?sort=title&start=100', 'status', 'keys', 'header:total-results')),
        point('negative', 'A negative start counts from the first item.',
              get(f'{U}/items/top?sort=title&start=-3&limit=2', 'keys')),
        point('keys', 'format=keys lists the keys, one per line.',
              get(f'{U}/items/top?format=keys&sort=title&limit=7', 'status', 'header:content-type', 'text')),
        point('keys-single', 'format=keys on a single item answers 400.',
              get(f'{U}/items/{K("QL", 1)}?format=keys', 'status', 'text')),
        point('versions', 'format=versions maps every key to its version.',
              get(f'{U}/items/top?format=versions', 'status', 'versions')),
        point('since-zero', 'since=0 returns every item.', get(f'{U}/items/top?since=0', 'keyset')),
        point('since', 'since=V returns the objects changed after version V.',
              get(f'{U}/items/{K("QL", 20)}', capture={'v20': 'body:version'}),
              get(f'{U}/items/top?since={{v20}}', 'keyset')),
        point('since-invalid', 'A non-numeric since answers 400.', get(f'{U}/items?since=abc', 'status', 'text')),
        point('not-modified', 'If-Modified-Since-Version with the current version answers 304.',
              get(f'{U}/items/top', 'status', headers={'If-Modified-Since-Version': '{version}'})),
        point('modified', 'If-Modified-Since-Version with an older version answers the list.',
              get(f'{U}/items/top?limit=1&sort=title', 'status', 'keys',
                  headers={'If-Modified-Since-Version': '{version-1}'})),
        point('user-id', 'A user ID other than 0 answers 400 with the reason.',
              get('/api/users/1/items', 'status', 'text')),
        point('group', 'An unknown group answers 404.', get('/api/groups/1/items', 'status'),
              requires=['filters/item']),
        point('api-version', 'A request for API version 2 answers 501.',
              get(f'{U}/items', 'status', 'text', headers={'Zotero-API-Version': '2'})),
        point('api-version-query', 'v=2 in the query answers 501 as well.', get(f'{U}/items?v=2', 'status'),
              requires=['api-version']),
        point('api-version-root', 'GET /api/ accepts any API version.',
              get('/api/', 'status', 'text', 'header:zotero-api-version', headers={'Zotero-API-Version': '2'})),
        point('unknown-endpoint', 'An unknown endpoint answers 404.', get(f'{U}/gadgets', 'status'),
              requires=['filters/item']),
        point('method', 'An unsupported method on a list answers an error.',
              send('PUT', f'{U}/items/top', [{'itemType': 'book'}], 'status', 'text'), requires=['filters/item']),
    ]
    return episode('api-query', 'query', [
        checkpoint('quick-search', 'Find items with quick search in its modes.', quick),
        checkpoint('filters', 'Filter items by tag, type, key, collection and hierarchy.', filters),
        checkpoint('sort', 'Order items by every sort field in both directions.', sorts),
        checkpoint('paging', 'Page through items, read keys and versions, and check the request preconditions.',
                   paging),
    ], setup=(API, library_setup('query')), initial='Setup writes the query library.')


# ------------------------------------------------------------------------------------------- validation
def validation_episode():
    def created(name, requirement, body, *more):
        item_key = body.get('key')
        steps = []
        if name in ('note-parent', 'regular-parent'):
            parent_key = K('VP', 1 if name == 'note-parent' else 2)
            body = dict(body, parentItem=parent_key)
            steps.append(post(f'{U}/items', [{'key': parent_key, 'version': 0, 'itemType': 'book',
                                              'title': 'Validation parent'}], 'status'))
        steps.append(post(f'{U}/items', [body], 'write'))
        if item_key:
            steps.append(get(item_path(item_key), 'status', 'data?', 'meta?'))
        return point(name, requirement, *steps, *more)
    v = lambda n: K('VA', n)
    base = lambda n, item_type='book', **fields: dict({'key': v(n), 'version': 0, 'itemType': item_type}, **fields)
    points = [
        created('unknown-type', 'An unknown item type fails with code 400 and the reason.', {'itemType': 'gadget', 'title': 'x'}),
        created('missing-type', 'An item without itemType fails with the reason.', {'title': 'No type'}),
        created('unknown-field', 'A field the schema does not know is kept in Extra.', base(1, title='With extra', colour='blue')),
        created('wrong-type-field', 'A known field that is not valid for the item type is handled the product\'s way.',
                base(2, title='Book with a journal', publicationTitle='Some Journal')),
        created('base-field', 'A base field given to a type with a mapped field is stored as the mapped field.',
                base(3, 'bookSection', title='Section', publicationTitle='The Containing Book')),
        created('mapped-title', 'title given to a case is stored as its case name.', base(4, 'case', title='Doe v. Roe')),
        created('creator-type-invalid', 'A creator role unsupported by the item type is normalized to its primary creator role.',
                base(5, title='Directed book', creators=[{'creatorType': 'director', 'firstName': 'A', 'lastName': 'B'}])),
        created('creator-name', 'A single-field creator name is kept as one name.',
                base(6, title='Institutional', creators=[{'creatorType': 'author', 'name': 'Example Consortium'}])),
        created('creator-both', 'A creator with both a single name and first/last names fails with the reason.',
                base(7, title='Mixed creator', creators=[{'creatorType': 'author', 'name': 'X', 'lastName': 'Y'}])),
        created('creator-order', 'Creators keep their order and roles.', base(8, 'bookSection', title='Ordered',
                creators=[{'creatorType': 'editor', 'firstName': 'E', 'lastName': 'One'},
                          {'creatorType': 'author', 'firstName': 'A', 'lastName': 'Two'},
                          {'creatorType': 'bookAuthor', 'firstName': 'B', 'lastName': 'Three'}])),
        created('creators-not-list', 'creators that is not a list fails with the reason.',
                base(9, title='Bad creators', creators='Somebody')),
        created('tags-strings', 'Tags given as plain strings are stored as manual tags.', base(10, title='String tags', tags=['a', 'b'])),
        created('tag-types', 'Manual and automatic tags keep their type.',
                base(11, title='Tag types', tags=[{'tag': 'manual'}, {'tag': 'automatic', 'type': 1}])),
        created('tag-duplicate', 'A repeated tag is stored once.', base(12, title='Repeated tag', tags=[{'tag': 'same'}, {'tag': 'same'}])),
        created('unknown-collection', 'An item in an unknown collection fails with the reason.',
                base(13, title='Lost', collections=[K('CL', 999)])),
        created('relations', 'Relations are stored with their predicates and URIs.',
                base(14, title='Related', relations={'dc:relation': ['http://zotero.org/users/1/items/ABCD2345'],
                                                     'owl:sameAs': 'http://zotero.org/groups/1/items/EFGH6789'})),
        created('relation-predicate', 'An arbitrary relation predicate and its URI are retained.',
                base(15, title='Bad relation', relations={'xx:unknown': ['http://example.org/']})),
        created('date-text', 'A free-text date is kept as written and parsed for sorting.', base(16, title='Dated', date='May 4, 2021')),
        created('date-parts', 'A partial date keeps its precision.', base(17, title='Month', date='March 1999')),
        created('date-invalid', 'An unparseable date is kept as text.', base(18, title='Odd date', date='sometime in spring')),
        created('access-date', 'An access date in SQL form is stored as UTC.', base(19, title='Accessed', accessDate='2021-05-04 10:20:30')),
        created('access-date-invalid', 'An invalid access date is omitted while the item is stored.', base(20, title='Bad access', accessDate='yesterday')),
        created('date-added', 'An explicit dateAdded is kept.', base(21, title='Added', dateAdded='2001-02-03T04:05:06Z'),
                get(item_path(v(21)), 'data:dateAdded')),
        created('date-added-invalid', 'An invalid dateAdded is replaced by the creation time while the item is stored.', base(22, title='Bad added', dateAdded='never')),
        created('extra-lines', 'Extra keeps its line breaks.', base(23, title='Extra', extra='Line one\nLine two\nPMID: 123')),
        created('unicode', 'Unicode text is stored as given.', base(24, title='Zoë’s naïve café — 東京 🙂',
                creators=[{'creatorType': 'author', 'firstName': 'Åsa', 'lastName': 'Øster'}])),
        created('whitespace', 'Surrounding white space of fields is trimmed.', base(25, title='  Spaced title  ', publisher=' Press ')),
        created('empty-fields', 'Empty fields are left out of the data.', base(26, title='Empty', publisher='', place='')),
        created('number-value', 'A number given for a text field is stored as text.', base(27, title='Numbers', volume=7, numPages=320)),
        point('boolean-value', 'A boolean given for a text field is rejected with a validation code.',
              post(f'{U}/items', [base(28, title='Boolean', volume=True)], 'write-codes'), requires=['number-value']),
        created('deleted-flag', 'deleted: 1 puts the new item in the trash.', base(29, title='Deleted on arrival', deleted=1),
                get(f'{U}/items/trash', 'keyset')),
        created('note-parent', 'A note may name a regular item as its parent.',
                {'key': v(30), 'version': 0, 'itemType': 'note', 'note': '<p>child</p>', 'parentItem': K('VA', 1)}),
        created('note-unknown-parent', 'A note whose parent does not exist fails with the reason.',
                {'key': v(31), 'version': 0, 'itemType': 'note', 'note': '<p>orphan</p>', 'parentItem': K('VA', 998)}),
        created('regular-parent', 'A regular item cannot have a parent item.', base(32, title='Child book', parentItem=v(1))),
        created('note-html', 'Note HTML is stored as given.', {'key': v(33), 'version': 0, 'itemType': 'note',
                'note': '<h1>Heading</h1><p>Text with <b>bold</b>, <i>italic</i> and <a href="https://example.org/">a link</a>.</p><ul><li>one</li><li>two</li></ul>'}),
        created('note-title', 'A note with an unsupported title field is rejected.',
                {'key': v(34), 'version': 0, 'itemType': 'note', 'note': '<p>Body</p>', 'title': 'Ignored?'}),
        created('long-title', 'A long title is stored in full.', base(35, title='Very long title ' * 60)),
        created('fields-of-another-type', 'Fields of the old type that the new type lacks move with a type change.',
                base(36, 'journalArticle', title='Changing', publicationTitle='Old Journal', issue='4', pages='1-2'),
                send('PATCH', item_path(v(36)), {'itemType': 'bookSection'}, 'status', headers={'If-Unmodified-Since-Version': '{version}'}),
                get(item_path(v(36)), 'data')),
        created('url-access', 'A URL and its access date are stored for web items.',
                base(38, 'webpage', title='Page', url='https://example.org/page', accessDate='2022-02-02T02:02:02Z')),
        created('isbn-issn', 'ISBN and ISSN text is stored as given.', base(39, title='Numbers', ISBN='0-306-40615-2 978-0-306-40615-7')),
        created('citation-key', 'A citation key is stored as a field.', base(40, title='Keyed', citationKey='knuth1968')),
    ]
    return episode('api-validation', 'items', [
        checkpoint('fields', 'Write items with unusual, invalid or edge-case values and read them back.', points)])


# ------------------------------------------------------------------------------------------ write semantics
def writes_episode():
    w = lambda n: K('WR', n)
    item = lambda n, **fields: dict({'key': w(n), 'version': 0, 'itemType': 'book', 'title': f'Write {n}'}, **fields)
    version = {'If-Unmodified-Since-Version': '{version}'}
    stale = {'If-Unmodified-Since-Version': '{version-1}'}
    points = [
        point('create-generated', 'POST without a key creates an item with a generated key.',
              post(f'{U}/items', [{'itemType': 'book', 'title': 'Generated key'}], 'status', 'write',
                   capture={'new': 'success:0'}),
              get(f'{U}/items/{{new}}', 'data')),
        point('create-keyed', 'POST with a key and version 0 creates the item under that key.',
              post(f'{U}/items', [item(1)], 'status', 'write'), get(item_path(w(1)), 'data')),
        point('create-existing', 'Creating an existing key again with version 0 fails with a version mismatch.',
              post(f'{U}/items', [item(2)], 'status'), post(f'{U}/items', [item(2, title='Again')], 'write')),
        point('update-no-version', 'A keyed update without a version or If-Unmodified-Since-Version fails with 428.',
              post(f'{U}/items', [item(3)], 'status'),
              post(f'{U}/items', [{'key': w(3), 'title': 'Changed'}], 'write')),
        point('update-version', 'A keyed POST update with the current object version merges the given fields.',
              post(f'{U}/items', [item(4, publisher='Kept Press')], 'status'),
              get(item_path(w(4)), capture={'v4': 'body:version'}),
              post(f'{U}/items', [{'key': w(4), 'version': '{v4}', 'title': 'Merged'}], 'write'),
              get(item_path(w(4)), 'data')),
        point('update-stale', 'A keyed POST update with an old object version fails with 412.',
              post(f'{U}/items', [item(5)], 'status'), get(item_path(w(5)), capture={'v5': 'body:version'}),
              post(f'{U}/items', [{'key': w(5), 'version': '{v5}', 'title': 'Once'}], 'status'),
              post(f'{U}/items', [{'key': w(5), 'version': '{v5}', 'title': 'Twice'}], 'write')),
        point('update-unchanged', 'An update that changes nothing is reported as unchanged.',
              post(f'{U}/items', [item(6)], 'status'), get(item_path(w(6)), capture={'v6': 'body:version'}),
              post(f'{U}/items', [{'key': w(6), 'version': '{v6}', 'title': 'Write 6'}], 'write')),
        point('library-precondition', 'POST with If-Unmodified-Since-Version older than the library fails with 412.',
              post(f'{U}/items', [item(7)], 'status'),
              post(f'{U}/items', [{'itemType': 'book', 'title': 'Late'}], 'status', 'text', headers=stale)),
        point('library-precondition-current', 'POST with the current library version as precondition succeeds.',
              post(f'{U}/items', [item(8)], 'status', 'write', headers=version)),
        point('patch', 'PATCH changes only the given fields.',
              post(f'{U}/items', [item(9, publisher='Old Press', place='Old Town')], 'status'),
              send('PATCH', item_path(w(9)), {'publisher': 'New Press'}, 'status', headers=version),
              get(item_path(w(9)), 'data')),
        point('patch-stale', 'PATCH with an old If-Unmodified-Since-Version fails with 412.',
              post(f'{U}/items', [item(10)], 'status'),
              send('PATCH', item_path(w(10)), {'title': 'Never'}, 'status', 'text', headers=stale)),
        point('patch-no-version', 'PATCH without a version fails with 428.',
              post(f'{U}/items', [item(11)], 'status'),
              send('PATCH', item_path(w(11)), {'title': 'Never'}, 'status', 'text')),
        point('patch-body-version', 'PATCH with a wrong version in the body fails with 412.',
              post(f'{U}/items', [item(12)], 'status'),
              send('PATCH', item_path(w(12)), {'title': 'Never', 'version': 999}, 'status', 'text')),
        point('put-replace', 'PUT replaces the item: fields left out are cleared.',
              post(f'{U}/items', [item(13, publisher='Gone Press', place='Gone Town')], 'status'),
              send('PUT', item_path(w(13)), {'itemType': 'book', 'title': 'Replaced'}, 'status', headers=version),
              get(item_path(w(13)), 'data')),
        point('put-create', 'PUT on an unused key with an item type creates the item.',
              send('PUT', item_path(w(14)), {'itemType': 'thesis', 'title': 'Put created'}, 'status'),
              get(item_path(w(14)), 'data')),
        point('put-create-no-type', 'PUT on an unused key without an item type answers 400.',
              send('PUT', item_path(w(15)), {'title': 'No type'}, 'status', 'text')),
        point('put-not-object', 'PUT with a JSON array answers 400.',
              send('PUT', item_path(w(16)), [{'itemType': 'book'}], 'status', 'text')),
        point('put-invalid-key', 'PUT on a malformed key answers 400.',
              send('PUT', f'{U}/items/lowercase', {'itemType': 'book'}, 'status', 'text')),
        point('delete', 'DELETE with the current version removes the item.',
              post(f'{U}/items', [item(17)], 'status'),
              send('DELETE', item_path(w(17)), None, 'status', headers=version), get(item_path(w(17)), 'status')),
        point('delete-no-version', 'DELETE without If-Unmodified-Since-Version answers 428.',
              post(f'{U}/items', [item(18)], 'status'), send('DELETE', item_path(w(18)), None, 'status', 'text')),
        point('delete-stale', 'DELETE with a version older than the item answers 412.',
              post(f'{U}/items', [item(19)], 'status'),
              send('DELETE', item_path(w(19)), None, 'status', 'text', headers={'If-Unmodified-Since-Version': '0'})),
        point('delete-unknown', 'DELETE of an unknown key answers 404.',
              send('DELETE', item_path(w(20)), None, 'status', headers=version), requires=['delete']),
        point('delete-many', 'DELETE ?itemKey= removes the listed items.',
              post(f'{U}/items', [item(21), item(22), item(23)], 'status'),
              send('DELETE', f'{U}/items?itemKey={w(21)},{w(22)}', None, 'status', headers=version),
              get(f'{U}/items?itemKey={w(21)},{w(22)},{w(23)}', 'keyset')),
        point('delete-many-missing', 'DELETE /items without itemKey answers 400.',
              send('DELETE', f'{U}/items', None, 'status', 'text', headers=version)),
        point('delete-many-too-many', 'DELETE of more than 50 keys answers 413.',
              send('DELETE', f'{U}/items?itemKey=' + ','.join(w(100 + i) for i in range(51)), None, 'status', 'text',
                   headers=version)),
        point('delete-many-invalid', 'DELETE with a malformed key answers 400.',
              send('DELETE', f'{U}/items?itemKey=bad-key', None, 'status', 'text', headers=version)),
        point('too-many', 'POST of more than 50 objects answers 413.',
              post(f'{U}/items', [{'itemType': 'book', 'title': f'Bulk {i}'} for i in range(51)], 'status', 'text')),
        point('empty-list', 'POST of an empty list answers 400.', post(f'{U}/items', [], 'status', 'text')),
        point('not-list', 'POST of a single object answers 400.', post(f'{U}/items', {'itemType': 'book'}, 'status', 'text')),
        point('invalid-json', 'POST of invalid JSON answers 400.',
              send('POST', f'{U}/items', None, 'status', body='[{"itemType": ', content_type='application/json'),
              requires=['create-keyed']),
        point('not-object-entry', 'A list entry that is not an object fails on its own.',
              post(f'{U}/items', ['text', {'itemType': 'book', 'title': 'Fine', 'key': w(24), 'version': 0}], 'write')),
        point('partial-failure', 'Valid entries succeed next to failing ones.',
              post(f'{U}/items', [{'itemType': 'gadget'}, item(25), {'itemType': 'book', 'colour': 1, 'key': 'bad'}], 'write')),
        point('write-token', 'A repeated Zotero-Write-Token is refused with 412.',
              post(f'{U}/items', [{'itemType': 'book', 'title': 'Token 1'}], 'status', headers={'Zotero-Write-Token': 'tokenabcdef1'}),
              post(f'{U}/items', [{'itemType': 'book', 'title': 'Token 2'}], 'status', 'text', headers={'Zotero-Write-Token': 'tokenabcdef1'})),
        point('write-token-short', 'A write token shorter than 5 characters answers 400.',
              post(f'{U}/items', [{'itemType': 'book', 'title': 'Short token'}], 'status', 'text', headers={'Zotero-Write-Token': 'abc'})),
        point('version-increments', 'Every write raises the library version; the new item carries it.',
              {'kind': 'version', 'as': 'before'},
              post(f'{U}/items', [item(26)], 'status', capture={'after': 'header:last-modified-version'}),
              get(item_path(w(26)), capture={'object': 'body:version'}),
              {'kind': 'compare', 'view': True, 'relations': [['after', '>', 'before'], ['object', '==', 'after']]}),
        point('versions-format', 'format=versions reports the object version of each item.',
              post(f'{U}/items', [item(27)], 'status'), get(item_path(w(27)), capture={'v27': 'body:version'}),
              get(f'{U}/items?itemKey={w(27)}&format=versions', capture={'listed': f'body:{w(27)}'}),
              {'kind': 'compare', 'view': True, 'relations': [['listed', '==', 'v27']]}),
        point('last-modified-header', 'Write responses report the new library version in Last-Modified-Version.',
              post(f'{U}/items', [item(28)], 'has-header:last-modified-version')),
    ]
    return episode('api-writes', 'items', [
        checkpoint('writes', 'Create, update, replace and delete items with and without preconditions.', points)])


# ---------------------------------------------------------------------------------------------- authorization
def auth_episode():
    a = lambda n: K('AU', n)
    item = lambda n: {'key': a(n), 'version': 0, 'itemType': 'book', 'title': f'Auth {n}'}
    points = [
        point('no-key', 'A write without an API key answers 401 with the reason and a WWW-Authenticate header.',
              post(f'{U}/items', [item(1)], 'status', 'text', 'header:www-authenticate',
                   headers={'Zotero-API-Key': None})),
        point('wrong-key', 'A write with an unknown API key answers 401.',
              post(f'{U}/items', [item(2)], 'status', 'text', headers={'Zotero-API-Key': 'WrongKey0123456789abcdefghijkl'})),
        point('query-key', 'The API key may be given as ?key=.',
              post(f'{U}/items?key={{key}}', [item(3)], 'status', 'write', headers={'Zotero-API-Key': None})),
        point('bearer', 'The API key may be given as a Bearer token.',
              post(f'{U}/items', [item(4)], 'status', 'write',
                   headers={'Zotero-API-Key': None, 'Authorization': 'Bearer {key}'})),
        point('no-server-id', 'A write without Zotero-Server-ID answers 428.',
              post(f'{U}/items', [item(5)], 'status', 'text', headers={'Zotero-Server-ID': None})),
        point('wrong-server-id-write', 'A write with another server ID answers 412.',
              post(f'{U}/items', [item(6)], 'status', 'text', headers={'Zotero-Server-ID': 'notthisserver'})),
        point('wrong-server-id-read', 'A read with another server ID answers 412 as well.',
              get(f'{U}/items', 'status', 'text', headers={'Zotero-Server-ID': 'notthisserver'})),
        point('read-without-key', 'Reads need no API key.',
              post(f'{U}/items', [item(7)], 'status'), get(item_path(a(7)), 'status', 'fields:title')),
        point('response-headers', 'Responses carry the API version, schema version, server ID and product version.',
              get(f'{U}/items', 'header:zotero-api-version', 'header:zotero-schema-version',
                  'has-header:zotero-server-id', 'header:x-zotero-version')),
        point('server-id-stable', 'The server ID is the same in every response.',
              get('/api/', capture={'one': 'header:zotero-server-id'}),
              get(f'{U}/items', capture={'two': 'header:zotero-server-id'}),
              {'kind': 'compare', 'view': True, 'relations': [['one', '==', 'two']]}),
        point('authorize-no-name', 'POST /api/local/authorize without an application name answers 400.',
              post('/api/local/authorize', {}, 'status', 'text', headers={'Zotero-API-Key': None})),
    ]
    return episode('api-auth', 'access', [checkpoint('auth', 'Send requests with and without keys and server IDs.',
                                                      points)])


# ---------------------------------------------------------------------------------------------- collections
def collections_episode():
    c = lambda n: K('CW', n)
    version = {'If-Unmodified-Since-Version': '{version}'}
    reads = [
        point('list', 'GET /collections lists every collection with its data and counts.',
              get(f'{U}/collections', 'status', 'header:total-results', 'object')),
        point('top', 'GET /collections/top lists the top-level collections.', get(f'{U}/collections/top', 'keyset')),
        point('subcollections', 'GET /collections/KEY/collections lists the direct subcollections.',
              get(f'{U}/collections/{C["Computer Science"]}/collections', 'keyset')),
        point('object', 'GET /collections/KEY returns the collection with its parent and counts.',
              get(f'{U}/collections/{C["Algorithms"]}', 'status', 'object')),
        point('unknown', 'An unknown collection answers 404.', get(f'{U}/collections/{K("CL", 998)}', 'status', 'text')),
        point('sorted', 'Collections sort by title.', get(f'{U}/collections?sort=title', 'keys')),
        point('item-collections', 'An item lists the keys of its collections.',
              get(f'{U}/items/{K("QL", 3)}', 'data')),
    ]
    writes = [
        point('create', 'POST creates a collection.', post(f'{U}/collections', [{'key': c(1), 'version': 0, 'name': 'New one'}],
                                                         'write'), get(f'{U}/collections/{c(1)}', 'data', 'meta')),
        point('create-generated', 'POST without a key creates a collection with a generated key.',
              post(f'{U}/collections', [{'name': 'Generated'}], 'write')),
        point('nested', 'A collection with a parent appears among the parent\'s subcollections.',
              post(f'{U}/collections', [{'key': c(2), 'version': 0, 'name': 'Child', 'parentCollection': C['Biology']}], 'write'),
              get(f'{U}/collections/{C["Biology"]}/collections', 'keyset'), get(f'{U}/collections/{C["Biology"]}', 'meta')),
        point('unknown-parent', 'A collection with an unknown parent fails with the reason.',
              post(f'{U}/collections', [{'key': c(3), 'version': 0, 'name': 'Orphan', 'parentCollection': K('CL', 997)}], 'write')),
        point('no-name', 'A collection without a name fails with the reason.',
              post(f'{U}/collections', [{'key': c(4), 'version': 0}], 'write')),
        point('rename', 'PATCH renames a collection.',
              post(f'{U}/collections', [{'key': c(5), 'version': 0, 'name': 'Old name'}], 'status'),
              send('PATCH', f'{U}/collections/{c(5)}', {'name': 'New name'}, 'status', headers=version),
              get(f'{U}/collections/{c(5)}', 'data')),
        point('move', 'Changing parentCollection moves a collection.',
              post(f'{U}/collections', [{'key': c(6), 'version': 0, 'name': 'Mover'}], 'status'),
              send('PATCH', f'{U}/collections/{c(6)}', {'parentCollection': C['Reading List']}, 'status', headers=version),
              get(f'{U}/collections/{C["Reading List"]}/collections', f'contains-key:{c(6)}'),
              get(f'{U}/collections/top', f'contains-key:{c(6)}')),
        point('move-to-top', 'parentCollection false moves a collection to the top level.',
              post(f'{U}/collections', [{'key': c(7), 'version': 0, 'name': 'Riser', 'parentCollection': C['Algorithms']}], 'status'),
              send('PATCH', f'{U}/collections/{c(7)}', {'parentCollection': False}, 'status', headers=version),
              get(f'{U}/collections/{c(7)}', 'data')),
        point('cycle', 'A collection cannot become its own descendant: the change is not applied.',
              post(f'{U}/collections', [{'key': c(8), 'version': 0, 'name': 'Ancestor'}], 'status'),
              post(f'{U}/collections', [{'key': c(9), 'version': 0, 'name': 'Descendant', 'parentCollection': c(8)}], 'status'),
              send('PATCH', f'{U}/collections/{c(8)}', {'parentCollection': c(9)}, headers=version),
              get(f'{U}/collections/{c(8)}', 'fields:name,parentCollection')),
        point('put', 'PUT replaces a collection.',
              post(f'{U}/collections', [{'key': c(10), 'version': 0, 'name': 'Put me', 'parentCollection': C['Biology']}], 'status'),
              send('PUT', f'{U}/collections/{c(10)}', {'name': 'Put done'}, 'status', headers=version),
              get(f'{U}/collections/{c(10)}', 'data')),
        point('add-items', 'Adding a collection key to items puts them in the collection.',
              post(f'{U}/collections', [{'key': c(11), 'version': 0, 'name': 'Holder'}], 'status'),
              post(f'{U}/items', [{'key': K('CI', 1), 'version': 0, 'itemType': 'book', 'title': 'Held', 'collections': [c(11)]},
                                  {'key': K('CI', 2), 'version': 0, 'itemType': 'book', 'title': 'Also held', 'collections': [c(11)]}], 'status'),
              get(f'{U}/collections/{c(11)}/items', 'keyset'), get(f'{U}/collections/{c(11)}', 'meta')),
        point('remove-item', 'Removing the collection key from an item takes it out of the collection.',
              post(f'{U}/collections', [{'key': c(12), 'version': 0, 'name': 'Leaky'}], 'status'),
              post(f'{U}/items', [{'key': K('CI', 3), 'version': 0, 'itemType': 'book', 'title': 'Leaving', 'collections': [c(12)]}], 'status'),
              send('PATCH', item_path(K('CI', 3)), {'collections': []}, 'status', headers=version),
              get(f'{U}/collections/{c(12)}/items', 'keyset')),
        point('delete', 'DELETE removes a collection; its items stay in the library.',
              post(f'{U}/collections', [{'key': c(13), 'version': 0, 'name': 'Doomed'}], 'status'),
              post(f'{U}/items', [{'key': K('CI', 4), 'version': 0, 'itemType': 'book', 'title': 'Survivor', 'collections': [c(13)]}], 'status'),
              send('DELETE', f'{U}/collections/{c(13)}', None, 'status', headers=version),
              get(f'{U}/collections/{c(13)}', 'status'), get(item_path(K('CI', 4)), 'data')),
        point('delete-parent', 'Deleting a collection deletes its subcollections.',
              post(f'{U}/collections', [{'key': c(14), 'version': 0, 'name': 'Parent'}], 'status'),
              post(f'{U}/collections', [{'key': c(15), 'version': 0, 'name': 'Sub', 'parentCollection': c(14)}], 'status'),
              send('DELETE', f'{U}/collections/{c(14)}', None, 'status', headers=version),
              get(f'{U}/collections/{c(15)}', 'status')),
        point('delete-many', 'DELETE ?collectionKey= removes several collections.',
              post(f'{U}/collections', [{'key': c(16), 'version': 0, 'name': 'One'}, {'key': c(17), 'version': 0, 'name': 'Two'}], 'status'),
              send('DELETE', f'{U}/collections?collectionKey={c(16)},{c(17)}', None, 'status', headers=version),
              get(f'{U}/collections/{c(16)}', 'status'), get(f'{U}/collections/{c(17)}', 'status')),
        point('delete-no-version', 'DELETE of a collection without a version answers 428.',
              post(f'{U}/collections', [{'key': c(18), 'version': 0, 'name': 'Kept'}], 'status'),
              send('DELETE', f'{U}/collections/{c(18)}', None, 'status')),
        point('unicode-name', 'Collection names keep Unicode text.',
              post(f'{U}/collections', [{'key': c(19), 'version': 0, 'name': 'Lectures — 東京 2024'}], 'status'),
              get(f'{U}/collections/{c(19)}', 'data')),
    ]
    return episode('api-collections', 'collections', [
        checkpoint('read', 'Read the collection tree and its counts.', reads),
        checkpoint('write', 'Create, rename, move, fill and delete collections.', writes),
    ], setup=(API, library_setup('query')), initial='Setup writes the query library.')


# --------------------------------------------------------------------------------------------------- tags
def tags_episode():
    version = {'If-Unmodified-Since-Version': '{version}'}
    reads = [
        point('all', 'GET /tags lists every tag with its type and item count.', get(f'{U}/tags', 'status', 'tags')),
        point('one', 'GET /tags/NAME returns one tag.', get(f'{U}/tags/classic', 'status', 'tags')),
        point('one-space', 'Tag names with spaces are addressed URL-encoded.', get(f'{U}/tags/shortest%20paths', 'tags')),
        point('items-tags', 'GET /items/tags lists the tags of all items.', get(f'{U}/items/tags', 'tags')),
        point('top-tags', 'GET /items/top/tags lists the tags of top-level items only.', get(f'{U}/items/top/tags', 'tags')),
        point('collection-tags', 'The tags of a collection\'s items.', get(f'{U}/collections/{C["Biology"]}/items/tags', 'tags')),
        point('item-q-tags', 'itemQ restricts the tag list to matching items.', get(f'{U}/items/tags?itemQ=dijkstra', 'tags')),
        point('item-tag-tags', 'itemTag restricts the tag list to items with that tag.',
              get(f'{U}/items/tags?itemTag=classic', 'tags')),
        point('q', 'q filters tag names by substring.', get(f'{U}/tags?q=gen', 'tags')),
        point('q-starts', 'qmode=startsWith filters tag names by prefix.', get(f'{U}/items/tags?q=s&qmode=startsWith', 'tags')),
        point('automatic', 'An automatic tag keeps type 1.', get(f'{U}/tags/conference%20report', 'tags')),
        point('sorted', 'Tags sort by name with sort=title.', get(f'{U}/tags?sort=title&limit=8', 'status', 'tag-order')),
    ]
    writes = [
        point('add', 'Adding a tag to an item makes it appear in the tag list.',
              send('PATCH', item_path(K('QL', 23)), {'tags': [{'tag': 'birds'}, {'tag': 'new tag'}]}, 'status', headers=version),
              get(f'{U}/tags/new%20tag', 'tags')),
        point('delete', 'DELETE /tags?tag= removes the tags from every item.',
              send('DELETE', f'{U}/tags?tag=classic', None, 'status', headers=version),
              get(f'{U}/items?tag=classic', 'keyset'), get(f'{U}/tags?q=classic', 'tag-names'), requires=['read/all']),
        point('delete-many', 'tag=a || b deletes several tags at once.',
              send('DELETE', f'{U}/tags?tag=graphs%20||%20sorting', None, 'status', headers=version),
              get(f'{U}/items?tag=graphs%20||%20sorting', 'keyset'), requires=['read/all']),
        point('delete-no-version', 'DELETE /tags without If-Unmodified-Since-Version answers 428.',
              send('DELETE', f'{U}/tags?tag=law', None, 'status', 'text')),
        point('delete-missing', 'DELETE /tags without tag answers 400.',
              send('DELETE', f'{U}/tags', None, 'status', 'text', headers=version)),
        point('remaining', 'Deleting a tag leaves an unrelated tag on the same item.',
              post(f'{U}/items', [{'key': K('TG', 1), 'version': 0, 'itemType': 'book', 'title': 'Tag independence',
                                   'tags': [{'tag': 'remove only this'}, {'tag': 'retain this'}]}], 'status'),
              send('DELETE', f'{U}/tags?tag=remove%20only%20this', None, 'status', headers=version),
              get(item_path(K('TG', 1)), 'fields:tags')),
    ]
    return episode('api-tags', 'tags', [
        checkpoint('read', 'Read tag lists and single tags with filters.', reads),
        checkpoint('write', 'Add and delete tags.', writes),
    ], setup=(API, library_setup('query')), initial='Setup writes the query library.')


# ----------------------------------------------------------------------------------------- children and files
PDF = ('JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0Nv'
       'dW50IDE+PgplbmRvYmoKMyAwIG9iago8PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94WzAgMCA1OTUgODQyXT4+CmVuZG9iagp0cmFpbGVyCjw8L1Jv'
       'b3QgMSAwIFI+PgolJUVPRgo=')
PDF_MD5 = '43e257097554d889e7d0a095f357fc8e'
PDF_SIZE = '200'


def children_episode():
    h = lambda n: K('CH', n)
    version = {'If-Unmodified-Since-Version': '{version}'}
    parent = lambda n, **fields: dict({'key': h(n), 'version': 0, 'itemType': 'journalArticle', 'title': f'Parent {n}'}, **fields)
    attachment = lambda n, parent_key, **fields: dict({'key': h(n), 'version': 0, 'itemType': 'attachment',
                                                       'parentItem': parent_key}, **fields)
    upload = [post(f'{U}/items', [parent(40), attachment(41, h(40), linkMode='imported_file', title='Full Text',
                                                         contentType='application/pdf', filename='paper.pdf')], 'status')]
    points = [
        point('note-child', 'A child note counts as a child of its parent and lists under it.',
              post(f'{U}/items', [parent(1), {'key': h(2), 'version': 0, 'itemType': 'note', 'parentItem': h(1),
                                              'note': '<p>A child note</p>'}], 'write'),
              get(item_path(h(1)), 'meta'), get(f'{item_path(h(1))}/children', 'data')),
        point('linked-url', 'A link attachment keeps its URL, title and access date.',
              post(f'{U}/items', [parent(3), attachment(4, h(3), linkMode='linked_url', title='Site',
                                                       url='https://example.org/site', accessDate='2023-03-03T03:03:03Z')], 'write'),
              get(item_path(h(4)), 'data')),
        point('linked-url-no-url', 'A link attachment without a URL is handled the product\'s way.',
              post(f'{U}/items', [parent(5), attachment(6, h(5), linkMode='linked_url', title='No URL')], 'write')),
        point('imported-file', 'A stored-file attachment without a file keeps its file name and content type.',
              post(f'{U}/items', [parent(7), attachment(8, h(7), linkMode='imported_file', title='PDF',
                                                       contentType='application/pdf', filename='a.pdf')], 'write'),
              get(item_path(h(8)), 'data')),
        point('linked-file', 'A linked-file attachment in the inbox keeps its path.',
              post(f'{U}/items', [parent(9), attachment(10, h(9), linkMode='linked_file', title='Linked',
                                                        contentType='application/pdf', path='{inbox}/notes.pdf')], 'write')),
        point('invalid-link-mode', 'An unknown link mode fails with the reason.',
              post(f'{U}/items', [parent(11), attachment(12, h(11), linkMode='teleported', title='Odd')], 'write')),
        point('attachment-standalone', 'An attachment may stand alone.',
              post(f'{U}/items', [{'key': h(13), 'version': 0, 'itemType': 'attachment', 'linkMode': 'linked_url',
                                   'title': 'Alone', 'url': 'https://example.org/alone'}], 'write'),
              get(f'{U}/items?itemKey={h(13)}', 'fields:itemType,parentItem,linkMode,title,url')),
        point('child-of-note', 'A note cannot be the parent of another note.',
              post(f'{U}/items', [{'key': h(14), 'version': 0, 'itemType': 'note', 'note': '<p>Top note</p>'},
                                  {'key': h(15), 'version': 0, 'itemType': 'note', 'note': '<p>Nested</p>', 'parentItem': h(14)}],
                   'write')),
        point('reparent', 'Changing parentItem moves a note to another item.',
              post(f'{U}/items', [parent(16), parent(17), {'key': h(18), 'version': 0, 'itemType': 'note', 'note': '<p>Mover</p>',
                                                          'parentItem': h(16)}], 'status'),
              send('PATCH', item_path(h(18)), {'parentItem': h(17)}, 'status', headers=version),
              get(f'{item_path(h(16))}/children', 'keyset'), get(f'{item_path(h(17))}/children', 'keyset')),
        point('orphan', 'parentItem false makes a child note standalone.',
              post(f'{U}/items', [parent(19), {'key': h(20), 'version': 0, 'itemType': 'note', 'note': '<p>Freed</p>',
                                              'parentItem': h(19)}], 'status'),
              send('PATCH', item_path(h(20)), {'parentItem': False}, 'status', headers=version),
              get(item_path(h(20)), 'data')),
        point('delete-parent', 'Deleting a parent deletes its children.',
              post(f'{U}/items', [parent(21), {'key': h(22), 'version': 0, 'itemType': 'note', 'note': '<p>Goes too</p>',
                                              'parentItem': h(21)}], 'status'),
              send('DELETE', item_path(h(21)), None, 'status', headers=version), get(item_path(h(22)), 'status')),
        point('annotation', 'A highlight annotation on a PDF attachment keeps its text, comment, color, page and '
                            'position.',
              post(f'{U}/items', [parent(23), attachment(24, h(23), linkMode='imported_file', title='PDF',
                                                        contentType='application/pdf', filename='p.pdf'),
                                  {'key': h(25), 'version': 0, 'itemType': 'annotation', 'parentItem': h(24),
                                   'annotationType': 'highlight', 'annotationText': 'quoted text',
                                   'annotationComment': 'why it matters', 'annotationColor': '#ffd400',
                                   'annotationPageLabel': '3', 'annotationSortIndex': '00002|000120|00300',
                                   'annotationPosition': '{"pageIndex":2,"rects":[[100,200,300,215]]}'}], 'write'),
              get(item_path(h(25)), 'data'), get(f'{item_path(h(24))}/children', 'keyset')),
        point('annotation-note', 'A note annotation keeps its comment and has no text.',
              post(f'{U}/items', [parent(26), attachment(27, h(26), linkMode='imported_file', title='PDF',
                                                        contentType='application/pdf', filename='q.pdf'),
                                  {'key': h(28), 'version': 0, 'itemType': 'annotation', 'parentItem': h(27),
                                   'annotationType': 'note', 'annotationComment': 'margin note',
                                   'annotationColor': '#5fb236', 'annotationPageLabel': '1',
                                   'annotationSortIndex': '00000|000010|00010',
                                   'annotationPosition': '{"pageIndex":0,"rects":[[50,700,72,722]]}'}], 'write'),
              get(item_path(h(28)), 'data')),
        point('annotation-invalid-type', 'An unknown annotation type fails with the reason.',
              post(f'{U}/items', [parent(29), attachment(30, h(29), linkMode='imported_file', title='PDF',
                                                        contentType='application/pdf', filename='r.pdf'),
                                  {'key': h(31), 'version': 0, 'itemType': 'annotation', 'parentItem': h(30),
                                   'annotationType': 'sparkle', 'annotationColor': '#ffd400', 'annotationPageLabel': '1',
                                   'annotationSortIndex': '00000|000010|00010', 'annotationPosition': '{"pageIndex":0}'}],
                   'write')),
        point('annotation-regular-parent', 'An annotation needs an attachment as its parent.',
              post(f'{U}/items', [parent(32), {'key': h(33), 'version': 0, 'itemType': 'annotation', 'parentItem': h(32),
                                              'annotationType': 'note', 'annotationColor': '#ffd400',
                                              'annotationPageLabel': '1', 'annotationSortIndex': '00000|000010|00010',
                                              'annotationPosition': '{"pageIndex":0}'}], 'write')),
        point('upload', 'The three-step upload stores a file for a stored-file attachment.',
              *upload,
              post(f'{item_path(h(41))}/file', None, 'status', form={'md5': PDF_MD5, 'filename': 'paper.pdf', 'filesize': PDF_SIZE,
                                                                     'mtime': '1704067200000'},
                   headers={'If-None-Match': '*'}, capture={'upload': 'body:uploadKey'}),
              send('POST', '/api/local/uploads/{upload}', None, 'status', body_base64=PDF, content_type='application/pdf',
                   auth=False),
              post(f'{item_path(h(41))}/file', None, 'status', form={'upload': '{upload}'}, headers={'If-None-Match': '*'}),
              get(item_path(h(41)), 'data:md5'), get(f'{item_path(h(41))}/file/view/url', 'status', 'text')),
        point('upload-exists', 'Authorizing an upload of the same file again reports that it exists.',
              post(f'{item_path(h(41))}/file', None, 'status', 'body', form={'md5': PDF_MD5, 'filename': 'paper.pdf',
                                                                             'filesize': PDF_SIZE, 'mtime': '1704067200000'},
                   headers={'If-Match': PDF_MD5})),
        point('upload-no-precondition', 'An upload authorization without If-Match or If-None-Match answers 428.',
              post(f'{item_path(h(41))}/file', None, 'status', 'text', form={'md5': PDF_MD5, 'filename': 'x.pdf',
                                                                            'filesize': '1', 'mtime': '1704067200000'})),
        point('upload-exists-none-match', 'If-None-Match: * on an attachment that has a file answers 412.',
              post(f'{item_path(h(41))}/file', None, 'status', 'text', form={'md5': '0' * 32, 'filename': 'x.pdf', 'filesize': '1',
                                                                            'mtime': '1704067200000'}, headers={'If-None-Match': '*'})),
        point('upload-bad-md5', 'A malformed MD5 answers 400.',
              *[post(f'{U}/items', [parent(42), attachment(43, h(42), linkMode='imported_file', title='T',
                                                          contentType='application/pdf', filename='t.pdf')], 'status')],
              post(f'{item_path(h(43))}/file', None, 'status', 'text', form={'md5': 'xyz', 'filename': 't.pdf', 'filesize': '1',
                                                                            'mtime': '1704067200000'}, headers={'If-None-Match': '*'})),
        point('upload-seconds', 'An mtime in seconds instead of milliseconds answers 400.',
              post(f'{item_path(h(43))}/file', None, 'status', 'text', form={'md5': PDF_MD5, 'filename': 't.pdf', 'filesize': '1',
                                                                            'mtime': '1704067200'}, headers={'If-None-Match': '*'})),
        point('upload-folder-name', 'A file name with a folder answers 400.',
              post(f'{item_path(h(43))}/file', None, 'status', 'text', form={'md5': PDF_MD5, 'filename': 'a/b.pdf',
                                                                            'filesize': '1', 'mtime': '1704067200000'},
                   headers={'If-None-Match': '*'})),
        point('upload-not-attachment', 'File endpoints refuse items that are not file attachments.',
              post(f'{item_path(h(42))}/file', None, 'status', 'text', form={'md5': PDF_MD5, 'filename': 't.pdf', 'filesize': '1',
                                                                            'mtime': '1704067200000'}, headers={'If-None-Match': '*'})),
        point('upload-wrong-md5', 'Uploaded bytes whose MD5 differs from the authorized one are refused.',
              post(f'{item_path(h(43))}/file', None, 'status', form={'md5': '0' * 32, 'filename': 't.pdf', 'filesize': PDF_SIZE,
                                                                     'mtime': '1704067200000'},
                   headers={'If-None-Match': '*'}, capture={'bad': 'body:uploadKey'}),
              send('POST', '/api/local/uploads/{bad}', None, 'status', 'text', body_base64=PDF, content_type='application/pdf',
                   auth=False)),
        point('fulltext', 'Full-text content of a PDF attachment is stored and read back with its statistics.',
              send('PUT', f'{item_path(h(41))}/fulltext', {'content': 'The full text.', 'indexedPages': 1, 'totalPages': 1},
                   'status'),
              get(f'{item_path(h(41))}/fulltext', 'status', 'body')),
        point('fulltext-versions', 'GET /fulltext lists the attachment whose full text was explicitly written.',
              get(f'{U}/fulltext?since=0', 'status', f'has-version:{h(41)}'), requires=['fulltext']),
        point('fulltext-invalid', 'Full-text content that is not a string answers 400.',
              send('PUT', f'{item_path(h(41))}/fulltext', {'content': 5}, 'status', 'text')),
        point('fulltext-not-attachment', 'Full text of a regular item answers 404.',
              get(f'{item_path(h(40))}/fulltext', 'status'), requires=['fulltext']),
        point('upload-unknown', 'Bytes sent to an unknown upload key answer 404 with the reason.',
              send('POST', '/api/local/uploads/unknownuploadkey', None, 'status', 'text', body='x',
                   content_type='text/plain', auth=False), requires=['upload']),
        point('file-not-attachment', 'The file of a regular item answers 400.',
              get(f'{item_path(h(40))}/file', 'status', 'text')),
    ]
    files_at = next(i for i, p in enumerate(points) if p['name'] == 'upload')
    text_at = next(i for i, p in enumerate(points) if p['name'] == 'fulltext')
    for p in points[text_at:]:
        p['requires'] = ['files/upload' if name == 'upload' else name for name in p.get('requires', [])]
    return episode('api-children', 'children', [
        checkpoint('children', 'Write child notes, attachments and annotations.', points[:files_at]),
        checkpoint('files', 'Upload attachment files with metadata and preconditions.', points[files_at:text_at]),
        checkpoint('fulltext', 'Write and retrieve full text of the uploaded attachment.', points[text_at:],
                   depends=['files/upload'])],
        setup=(API, {'id': 'inbox', 'op': 'upload', 'files': ['notes.pdf']}))


# ------------------------------------------------------------------------------------------------ trash
def trash_episode():
    t = lambda n: K('TR', n)
    version = {'If-Unmodified-Since-Version': '{version}'}
    points = [
        point('trash', 'deleted: 1 moves an item to the trash: listed in /items/trash, not in /items.',
              post(f'{U}/items', [{'key': t(1), 'version': 0, 'itemType': 'book', 'title': 'Trashed'}], 'status'),
              send('PATCH', item_path(t(1)), {'deleted': 1}, 'status', headers=version),
              get(f'{U}/items/trash?itemKey={t(1)}', 'keyset'), get(f'{U}/items?itemKey={t(1)}', 'keyset'), get(item_path(t(1)), 'data')),
        point('include-trashed', 'includeTrashed=1 lists trashed items with the others.',
              get(f'{U}/items/top?includeTrashed=1', 'keyset')),
        point('restore', 'deleted: 0 restores an item from the trash.',
              post(f'{U}/items', [{'key': t(2), 'version': 0, 'itemType': 'book', 'title': 'Restored', 'deleted': 1}], 'status'),
              send('PATCH', item_path(t(2)), {'deleted': 0}, 'status', headers=version),
              get(f'{U}/items/trash?itemKey={t(2)}', 'keyset'), get(item_path(t(2)), 'data')),
        point('trash-children', 'A trashed parent\'s child note stays listed under it.',
              post(f'{U}/items', [{'key': t(3), 'version': 0, 'itemType': 'book', 'title': 'Trashed parent', 'deleted': 1},
                                  {'key': t(4), 'version': 0, 'itemType': 'note', 'note': '<p>Child</p>', 'parentItem': t(3)}],
                   'status'),
              get(f'{U}/items/trash?itemKey={t(3)},{t(4)}', 'keyset'), get(f'{item_path(t(3))}/children', 'keyset')),
        point('trash-collection', 'A trashed item leaves its collection\'s item list.',
              post(f'{U}/collections', [{'key': K('TC', 1), 'version': 0, 'name': 'Trash test'}], 'status'),
              post(f'{U}/items', [{'key': t(5), 'version': 0, 'itemType': 'book', 'title': 'In collection',
                                   'collections': [K('TC', 1)], 'deleted': 1},
                                  {'key': t(6), 'version': 0, 'itemType': 'book', 'title': 'Present', 'collections': [K('TC', 1)]}],
                   'status'),
              get(f'{U}/collections/{K("TC", 1)}/items', 'keyset')),
        point('trash-top', '/items/trash/top leaves child items out.',
              post(f'{U}/items', [{'key': t(8), 'version': 0, 'itemType': 'book', 'title': 'Top trash', 'deleted': 1},
                                  {'key': t(9), 'version': 0, 'itemType': 'note', 'note': '<p>Nested trash</p>',
                                   'parentItem': t(8)}], 'status'),
              get(f'{U}/items/trash/top', f'contains-key:{t(8)}', f'contains-key:{t(9)}')),
        point('trash-tags', 'The tags of trashed items.',
              post(f'{U}/items', [{'key': t(7), 'version': 0, 'itemType': 'book', 'title': 'Tagged trash', 'deleted': 1,
                                   'tags': [{'tag': 'discarded'}]}], 'status'),
              get(f'{U}/items/trash/tags?q=discarded', 'tags'), get(f'{U}/tags?q=discarded', 'tags')),
    ]
    return episode('api-trash', 'trash', [checkpoint('trash', 'Move items to the trash, list and restore them.', points)])


# ------------------------------------------------------------------------------------------------- restart
def persistence_episode():
    p = lambda n: K('PE', n)
    before = [
        point('write', 'Items, collections, saved searches and tags written through the API are stored.',
              post(f'{U}/collections', [{'key': K('PC', 1), 'version': 0, 'name': 'Persistent'}], 'status'),
              post(f'{U}/items', [{'key': p(1), 'version': 0, 'itemType': 'book', 'title': 'Persistent book',
                                   'collections': [K('PC', 1)], 'tags': [{'tag': 'kept'}]},
                                  {'key': p(2), 'version': 0, 'itemType': 'note', 'note': '<p>Persistent note</p>',
                                   'parentItem': p(1)}], 'status', 'write'),
              post(f'{U}/searches', [{'key': K('PS', 1), 'version': 0, 'name': 'Persistent search',
                                       'conditions': [{'condition': 'tag', 'operator': 'is', 'value': 'kept'}]}], 'status')),
    ]
    after = [
        point('items', 'After a restart the items and their data are unchanged.', get(f'{U}/items', 'data')),
        point('collections', 'After a restart the collections are unchanged.', get(f'{U}/collections', 'data', 'meta')),
        point('searches', 'After a restart the saved searches still run.', get(f'{U}/searches/{K("PS", 1)}/items', 'keyset')),
        point('tags', 'After a restart the tags are unchanged.', get(f'{U}/tags', 'tags')),
        point('notes', 'After a restart child notes are still attached to their parent.',
              get(f'{item_path(p(1))}/children', 'data')),
        point('write-after', 'After a restart writes work with the new server ID response header.',
              post(f'{U}/items', [{'key': p(3), 'version': 0, 'itemType': 'book', 'title': 'After restart'}], 'write')),
    ]
    return episode('api-persistence', 'persistence', [
        checkpoint('before', 'Write objects through the API.', before),
        checkpoint('after', 'Restart the application with the same data directory and read the objects.', after,
                   depends=['before'], lifecycle='restart'),
    ])


def list_options_episode():
    """Collection/search representations and version filters on non-item endpoints."""
    search = K('LX', 1)
    fixtures = {'searches': [{'key': search, 'version': 0, 'name': 'Local books',
                             'conditions': [cond('itemType', 'is', 'book')]}]}
    collections = [
        point('keys', 'Collections export their keys as lines.', get(f'{U}/collections?format=keys', 'status', 'keylines')),
        point('versions', 'Collections expose a key-to-version map.', get(f'{U}/collections?format=versions', 'status', 'versions')),
        point('since-zero', 'Collection since=0 includes every fixture collection.', get(f'{U}/collections?since=0', 'keyset')),
        point('not-modified', 'Collection lists honor If-Modified-Since-Version.',
              get(f'{U}/collections', 'status', headers={'If-Modified-Since-Version': '{version}'}), requires=['keys']),
        point('modified', 'A collection list with an older version returns its objects.',
              get(f'{U}/collections', 'status', 'keyset', headers={'If-Modified-Since-Version': '0'})),
        point('top-tags', 'Top-level collection item tags exclude child note tags.',
              get(f'{U}/collections/{C["Theory of Computation"]}/items/top/tags', 'tags')),
    ]
    searches = [
        point('keys', 'Saved searches export their keys as lines.', get(f'{U}/searches?format=keys', 'status', 'keylines')),
        point('versions', 'Saved searches expose a key-to-version map.', get(f'{U}/searches?format=versions', 'status', 'versions')),
        point('not-modified', 'Search lists honor If-Modified-Since-Version.',
              get(f'{U}/searches', 'status', headers={'If-Modified-Since-Version': '{version}'}), requires=['keys']),
        point('since', 'The search since filter returns only searches created after the captured version.',
              {'kind': 'version', 'as': 'before'},
              post(f'{U}/searches', [{'key': K('LX', 2), 'version': 0, 'name': 'Recent articles',
                                     'conditions': [cond('itemType', 'is', 'journalArticle')]}], 'status'),
              get(f'{U}/searches?since={{before}}', 'status', 'keyset')),
    ]
    return episode('api-list-options', 'query', [
        checkpoint('collections', 'Read collection representations, versions and item tags.', collections),
        checkpoint('searches', 'Read search representations and version filters.', searches),
    ], setup=(API, library_setup('query'), {'id': 'searches', 'op': 'objects', 'content': fixtures}),
       initial='Setup writes the query library and one saved search.')


def build():
    return ([schema_episode(), types_episode(), validation_episode(), writes_episode(), auth_episode(),
             collections_episode(), searches_episode(), query_episode(), tags_episode(), children_episode(), list_options_episode(),
             trash_episode(), persistence_episode(), include_episode(), cite_options_episode()]
            + [export_episode(f) for f in FORMATS] + [cite_episode(s) for s in STYLES])

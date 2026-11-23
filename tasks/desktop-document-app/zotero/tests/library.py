"""Fixture libraries and input files.

Every object the setup writes carries a fixed key (Zotero keys use the alphabet
23456789ABCDEFGHIJKLMNPQRSTUVWXYZ) and, for regular items, fixed dateAdded and
dateModified values, so that list orders and references are the same in every
run. Files are generated into the episode's private fixture folder and
uploaded into the inbox.
"""
import json
from pathlib import Path

import schema_types

ALPHABET = '23456789ABCDEFGHIJKLMNPQRSTUVWXYZ'
NAMES = [('Ada', 'Lovelace'), ('Grace', 'Hopper'), ('Alan', 'Turing'), ('Edsger', 'Dijkstra'), ('Barbara', 'Liskov'),
         ('Donald', 'Knuth'), ('Frances', 'Allen'), ('John', 'McCarthy'), ('Margaret', 'Hamilton'), ('Tony', 'Hoare'),
         ('Radia', 'Perlman'), ('Niklaus', 'Wirth')]


def key(prefix, number):
    """An 8-character object key: the prefix, then the number in the key alphabet."""
    digits = ''
    for _ in range(8 - len(prefix)):
        digits = ALPHABET[number % len(ALPHABET)] + digits
        number //= len(ALPHABET)
    return prefix + digits


def stamp(minute):
    """dateAdded/dateModified of the n-th fixture item: one minute apart on 2024-03-01."""
    return f'2024-03-01T{minute // 60:02d}:{minute % 60:02d}:00Z'


# ------------------------------------------------------------------------------------------- one item per type
SPECIAL = {
    'title': None, 'abstractNote': None, 'date': '2019-07-21', 'accessDate': '2020-02-03T04:05:06Z',
    'url': None, 'DOI': None, 'ISBN': '978-0-306-40615-7', 'ISSN': '0378-5955', 'pages': '23-45', 'volume': '12',
    'issue': '3', 'numPages': '321', 'numberOfVolumes': '2', 'edition': '2', 'seriesNumber': '4', 'section': '7',
    'partNumber': '2', 'runningTime': '1:32:00', 'scale': '1:50000', 'language': 'en', 'extra': None,
    'shortTitle': None, 'publisher': 'Example Press', 'place': 'Springfield', 'publicationTitle': 'Journal of Examples',
    'journalAbbreviation': 'J. Ex.', 'series': 'Studies in Examples', 'seriesTitle': 'Example Series',
    'seriesText': 'Second series', 'archive': 'Example Archive', 'archiveLocation': 'Box 12, Folder 3',
    'libraryCatalog': 'Example Catalog', 'callNumber': 'QA76.9 .E93', 'rights': 'CC BY 4.0', 'citationKey': None,
    'originalDate': '1901', 'originalPublisher': 'Old Press', 'originalPlace': 'Old Town', 'format': 'Paperback',
    'filingDate': '2018-01-05', 'dateDecided': '2017-11-30', 'dateEnacted': '2016-06-01', 'issueDate': '2019-07-21',
    'priorityDate': '2017-03-02', 'firstPage': '101', 'codePages': '55-60', 'codeVolume': '42', 'reporterVolume': '9',
    'versionNumber': '2.1.0', 'episodeNumber': '17', 'PMID': '12345678', 'PMCID': 'PMC1234567', 'archiveID': 'arXiv:1901.00001',
    'patentNumber': 'US 9,876,543', 'applicationNumber': '15/123,456', 'priorityNumbers': 'US 62/000,001',
    'billNumber': 'H.R. 1234', 'publicLawNumber': 'Pub. L. 115-1', 'docketNumber': 'No. 16-123', 'reportNumber': 'TR-2019-07',
    'documentNumber': 'Doc 88', 'number': '88', 'identifier': 'EX-DS-001', 'session': '115th', 'history': 'Passed House',
    'references': 'Related reference', 'legalStatus': 'Granted', 'status': 'Published', 'programmingLanguage': 'Python',
    'system': 'Linux', 'repository': 'Example Repository', 'repositoryLocation': 'Online', 'genre': 'Documentary',
    'medium': 'Print', 'country': 'United States', 'assignee': 'Example Corp.', 'issuingAuthority': 'Patent Office',
    'court': 'Supreme Court', 'reporter': 'Example Reports', 'code': 'Example Code', 'legislativeBody': 'Example Senate',
    'committee': 'Committee on Examples', 'university': 'Example University', 'institution': 'Example Institute',
    'organization': 'Example Standards Body', 'company': 'Example Software', 'distributor': 'Example Pictures',
    'studio': 'Example Studio', 'network': 'Example Network', 'label': 'Example Records', 'conferenceName':
    'Conference on Examples', 'proceedingsTitle': 'Proceedings of the Conference on Examples',
    'meetingName': 'Annual Meeting', 'eventPlace': 'Example City', 'bookTitle': 'The Book of Examples',
    'encyclopediaTitle': 'Encyclopedia of Examples', 'dictionaryTitle': 'Dictionary of Examples',
    'websiteTitle': 'Example Website', 'blogTitle': 'Example Blog', 'forumTitle': 'Example Forum',
    'programTitle': 'Example Program', 'sessionTitle': 'Session on Examples', 'type': 'Working paper',
}


def type_label(name):
    words, word = [], ''
    for char in name:
        if char.isupper() and word:
            words.append(word)
            word = char.lower()
        else:
            word += char.lower()
    words.append(word)
    return ' '.join(words)


def type_item(item_type, index):
    """One item of the type with every field of the type and one creator per creator type (two of the primary)."""
    spec = schema_types.TYPES[item_type]
    label = type_label(item_type)
    data = {'key': key('TY', index), 'version': 0, 'itemType': item_type}
    for field in spec['fields']:
        value = SPECIAL.get(field, f'{field} sample')
        if field in spec['base'] and field not in SPECIAL:
            value = f'{field} sample'
        if value is None:
            value = {
                'title': f'an inquiry into the {label} of everyday life',
                'abstractNote': f'This abstract describes the {label}.',
                'url': f'https://example.org/{item_type}', 'DOI': f'10.5555/{item_type}.2019',
                'extra': f'Original note for {label}', 'shortTitle': f'The {label}',
                'citationKey': f'{item_type}2019'}[field]
        if field in ('caseName', 'nameOfAct', 'subject'):
            value = f'an inquiry into the {label} of everyday life'
        data[field] = value
    creators = []
    for position, creator_type in enumerate(spec['creators']):
        count = 2 if position == 0 else 1
        for n in range(count):
            first, last = NAMES[(index + len(creators)) % len(NAMES)]
            creators.append({'creatorType': creator_type, 'firstName': first, 'lastName': last})
    data['creators'] = creators
    data['tags'] = [{'tag': item_type}, {'tag': 'fixture'}]
    data['dateAdded'] = data['dateModified'] = stamp(index)
    return data


TYPE_ITEMS = {name: type_item(name, i + 1) for i, name in enumerate(schema_types.REGULAR)}


# ------------------------------------------------------------------------------------------- the query library
def item(number, item_type, title, creators=(), tags=(), collections=(), **fields):
    data = {'key': key('QL', number), 'version': 0, 'itemType': item_type, 'title': title,
            'creators': [dict(zip(('creatorType', 'firstName', 'lastName'), c)) if len(c) == 3
                         else {'creatorType': c[0], 'name': c[1]} for c in creators],
            'tags': [{'tag': t} if isinstance(t, str) else {'tag': t[0], 'type': t[1]} for t in tags],
            'collections': [COLLECTION_KEYS[c] for c in collections],
            'dateAdded': stamp(100 + number), 'dateModified': stamp(200 + (number * 7) % 23)}
    data.update(fields)
    if item_type == 'case':
        data['caseName'] = data.pop('title')
    if item_type == 'statute':
        data['nameOfAct'] = data.pop('title')
    return data


COLLECTIONS = [  # name, key, parent
    ('Computer Science', key('CL', 1), None), ('Algorithms', key('CL', 2), 'Computer Science'),
    ('Theory of Computation', key('CL', 3), 'Computer Science'), ('Graph Algorithms', key('CL', 4), 'Algorithms'),
    ('Biology', key('CL', 5), None), ('Reading List', key('CL', 6), None), ('Empty Collection', key('CL', 7), None),
]
COLLECTION_KEYS = {name: k for name, k, _ in COLLECTIONS}


def collection_objects():
    return [{'key': k, 'version': 0, 'name': name,
             **({'parentCollection': COLLECTION_KEYS[parent]} if parent else {})} for name, k, parent in COLLECTIONS]


QUERY_ITEMS = [
    item(1, 'book', 'The Art of Computer Programming', [('author', 'Donald', 'Knuth')], ['algorithms', 'classic'],
         ['Algorithms'], date='1968', publisher='Addison-Wesley', place='Reading, MA', edition='1',
         numberOfVolumes='4', ISBN='978-0-201-89683-1', language='en'),
    item(2, 'journalArticle', 'On Computable Numbers, with an Application to the Entscheidungsproblem',
         [('author', 'Alan', 'Turing')], ['computability', 'classic'], ['Theory of Computation'], date='1936',
         publicationTitle='Proceedings of the London Mathematical Society', volume='s2-42', issue='1',
         pages='230-265', DOI='10.1112/plms/s2-42.1.230', journalAbbreviation='Proc. Lond. Math. Soc.',
         language='en'),
    item(3, 'journalArticle', 'A Note on Two Problems in Connexion with Graphs', [('author', 'Edsger', 'Dijkstra')],
         ['graphs', 'shortest paths'], ['Graph Algorithms', 'Reading List'], date='1959-12-01',
         publicationTitle='Numerische Mathematik', volume='1', pages='269-271', DOI='10.1007/BF01386390',
         language='en'),
    item(4, 'bookSection', 'Notes on Structured Programming', [('author', 'Edsger', 'Dijkstra'),
         ('editor', 'Ole-Johan', 'Dahl'), ('editor', 'Tony', 'Hoare')], ['programming'], ['Computer Science'],
         date='1972', bookTitle='Structured Programming', publisher='Academic Press', place='London',
         pages='1-82', language='en'),
    item(5, 'conferencePaper', 'Programming with Abstract Data Types', [('author', 'Barbara', 'Liskov'),
         ('author', 'Stephen', 'Zilles')], ['abstraction', 'programming'], ['Computer Science'], date='1974-04',
         proceedingsTitle='Proceedings of the ACM SIGPLAN Symposium on Very High Level Languages',
         conferenceName='Symposium on Very High Level Languages', place='Santa Monica', pages='50-59',
         DOI='10.1145/800233.807045', language='en'),
    item(6, 'thesis', 'Evolutionary Dynamics of Small Populations', [('author', 'Rosalind', 'Franklin')],
         ['genetics'], ['Biology'], date='2015-05-14', university='Example University', thesisType='PhD thesis',
         place='Cambridge', language='en'),
    item(7, 'report', 'Software Engineering: Report of a Conference', [('editor', 'Peter', 'Naur'),
         ('editor', 'Brian', 'Randell')], ['software engineering', ('conference report', 1)], ['Computer Science'],
         date='1969-01', institution='NATO Science Committee', place='Brussels', reportType='Conference report',
         language='en'),
    item(8, 'webpage', 'Garbage Collection Handbook Companion Site', [('author', 'Richard', 'Jones')],
         ['memory management'], [], date='2023-08-15', websiteTitle='GC Handbook', url='https://gchandbook.example.org/',
         accessDate='2024-02-01T10:00:00Z', language='en'),
    item(9, 'newspaperArticle', 'Computer Beats Champion in Chess Rematch', [('author', 'Bruce', 'Weber')],
         ['chess', 'artificial intelligence'], ['Reading List'], date='1997-05-12', publicationTitle='The New York Times',
         section='A', pages='1', place='New York', language='en'),
    item(10, 'magazineArticle', 'As We May Think', [('author', 'Vannevar', 'Bush')], ['hypertext', 'classic'],
         ['Reading List'], date='1945-07', publicationTitle='The Atlantic', volume='176', issue='1', pages='101-108',
         language='en'),
    item(11, 'book', 'The Origin of Species', [('author', 'Charles', 'Darwin')], ['evolution', 'classic'],
         ['Biology'], date='1859-11-24', publisher='John Murray', place='London', edition='1', language='en'),
    item(12, 'journalArticle', 'Molecular Structure of Nucleic Acids', [('author', 'James', 'Watson'),
         ('author', 'Francis', 'Crick')], ['genetics', 'DNA', 'classic'], ['Biology', 'Reading List'],
         date='1953-04-25', publicationTitle='Nature', volume='171', issue='4356', pages='737-738',
         DOI='10.1038/171737a0', language='en'),
    item(13, 'journalArticle', 'A Very Large Collaboration Paper', [('author', f, l) for f, l in
         [('Ann', 'Alpha'), ('Ben', 'Beta'), ('Cy', 'Gamma'), ('Di', 'Delta'), ('Ed', 'Epsilon'), ('Flo', 'Zeta'),
          ('Gus', 'Eta'), ('Hal', 'Theta')]], ['collaboration'], ['Biology'], date='2021-03-03',
         publicationTitle='Journal of Big Science', volume='88', pages='e1001', DOI='10.5555/jbs.2021.88',
         language='en'),
    item(14, 'patent', 'Method for Sorting Records Quickly', [('inventor', 'Tony', 'Hoare')], ['sorting'],
         ['Algorithms'], issueDate='1962-07-01', patentNumber='US 3,000,001', assignee='Elliott Brothers',
         country='United Kingdom', language='en'),
    item(15, 'case', 'Example Corp. v. Sample Inc.', [], ['law'], [], dateDecided='2010-06-28',
         court='Supreme Court', reporter='U.S.', reporterVolume='561', firstPage='593', docketNumber='No. 08-964'),
    item(16, 'statute', 'Example Data Protection Act', [], ['law', 'privacy'], [], dateEnacted='2018-05-25',
         code='Example Code', publicLawNumber='Pub. L. 115-1', section='3'),
    item(17, 'film', 'The Imitation Game', [('director', 'Morten', 'Tyldum')], ['biography'], ['Reading List'],
         date='2014-11-28', distributor='The Weinstein Company', genre='Drama', runningTime='1:54:00', language='en'),
    item(18, 'dataset', 'Global Temperature Anomalies 1880-2020', [('author', 'Climate', 'Lab')], ['climate'],
         ['Biology'], date='2021-01-15', repository='Example Data Repository', identifier='DS-2021-001',
         versionNumber='3', url='https://data.example.org/ds-2021-001', language='en'),
    item(19, 'preprint', 'Attention Is Not All You Need, Probably', [('author', 'Ada', 'Lovelace'),
         ('author', 'Grace', 'Hopper')], ['machine learning'], ['Computer Science'], date='2023-02-02',
         repository='arXiv', archiveID='arXiv:2302.00001', DOI='10.48550/arXiv.2302.00001', language='en'),
    item(20, 'computerProgram', 'Example Sorter', [('programmer', 'Margaret', 'Hamilton')], ['sorting', 'software'],
         ['Algorithms'], date='2022', company='Example Software', versionNumber='1.4.2', programmingLanguage='C',
         system='Linux', url='https://software.example.org/sorter'),
    item(21, 'letter', 'Letter to the Editor on Goto Statements', [('author', 'Edsger', 'Dijkstra'),
         ('recipient', 'Niklaus', 'Wirth')], ['programming', 'classic'], ['Computer Science'], date='1968-03',
         letterType='Letter to the editor', language='en'),
    item(22, 'encyclopediaArticle', 'Quicksort', [('author', 'Tony', 'Hoare')], ['sorting', 'algorithms'],
         ['Algorithms'], date='2009', encyclopediaTitle='Encyclopedia of Algorithms', publisher='Springer',
         pages='1-3', language='en'),
    item(23, 'document', 'Untitled Draft about Garden Birds', [('author', 'Rachel', 'Carson')], ['birds'], [],
         date='1950'),
    item(24, 'book', 'Zebra Patterns and Other Stories', [('author', 'Émile', 'Zola'), ('translator', 'Ada', 'Lovelace')],
         ['zoology', 'fiction'], [], date='2001-02-03', publisher='Ünicode Verlag', place='München', language='de'),
    item(25, 'report', 'Global Health Statistics', [('author', 'World Health Organization')], ['health'], ['Biology'],
         date='2020', institution='World Health Organization', place='Geneva', reportNumber='WHO-2020-1',
         language='en'),
    item(26, 'book', 'Algorithms', [('author', 'Robert', 'Sedgewick'), ('author', 'Kevin', 'Wayne')],
         ['algorithms'], ['Algorithms', 'Reading List'], date='2011', publisher='Addison-Wesley', edition='4',
         place='Upper Saddle River, NJ', ISBN='978-0-321-57351-3', language='en'),
]

# Multiple values, a tie and missing values for less common sortable fields.
for _index, _entry in enumerate(QUERY_ITEMS[:4]):
    _entry.update(libraryCatalog=('Alpha Catalog', 'Zeta Catalog', 'Alpha Catalog', 'Middle Catalog')[_index],
                  callNumber=('QA10', 'QA90', 'QA10', 'QA40')[_index],
                  rights=('CC0', 'CC BY 4.0', 'CC0', 'Public domain')[_index],
                  accessDate=f'2024-02-0{_index + 2}T10:00:00Z')
QUERY_ITEMS[2]['journalAbbreviation'] = 'Numer. Math.'
QUERY_ITEMS[11]['journalAbbreviation'] = 'Nature'

# Child objects and standalone notes of the query library.
QUERY_CHILDREN = [
    {'key': key('QN', 1), 'version': 0, 'itemType': 'note', 'parentItem': key('QL', 2),
     'note': '<p>Turing machine definition on page 231; the halting problem.</p>', 'tags': [{'tag': 'reading note'}]},
    {'key': key('QN', 2), 'version': 0, 'itemType': 'note', 'parentItem': key('QL', 12),
     'note': '<p>Double helix model; compare with Franklin photograph 51.</p>'},
    {'key': key('QN', 3), 'version': 0, 'itemType': 'note', 'note': '<p>Standalone note about sorting networks.</p>',
     'collections': [COLLECTION_KEYS['Algorithms']], 'tags': [{'tag': 'sorting'}]},
    {'key': key('QA', 1), 'version': 0, 'itemType': 'attachment', 'parentItem': key('QL', 8),
     'linkMode': 'linked_url', 'title': 'Companion website', 'url': 'https://gchandbook.example.org/',
     'accessDate': '2024-02-01T10:00:00Z'},
    {'key': key('QA', 2), 'version': 0, 'itemType': 'attachment', 'parentItem': key('QL', 3),
     'linkMode': 'linked_url', 'title': 'Publisher page', 'url': 'https://doi.org/10.1007/BF01386390'},
]


def query_library():
    """Collections, items and children of the query library, in write order. (Relations name library URIs that
    differ between instances; they are created through the interface instead.)"""
    return {'collections': collection_objects(), 'items': [dict(entry) for entry in QUERY_ITEMS],
            'children': [dict(entry) for entry in QUERY_CHILDREN]}


# ----------------------------------------------------------------------------------------------------- files
def write_pdf(path, pages, title='', author=''):
    import pymupdf
    document = pymupdf.open()
    for lines in pages:
        page = document.new_page(width=595, height=842)
        y = 100
        for size, text in lines:
            page.insert_text((72, y), text, fontsize=size)
            y += size * 2.2
    document.set_metadata({'title': title, 'author': author, 'creationDate': 'D:20240101000000Z',
                           'modDate': 'D:20240101000000Z', 'producer': 'program-bench fixtures', 'creator': ''})
    document.save(path, garbage=3, deflate=True, no_new_id=True)
    document.close()


PDFS = {
    'reader.pdf': dict(title='Reader Sample', author='Sample Author', pages=[
        [(20, f'Chapter {n}: Reading Closely'), (12, 'The quick brown fox jumps over the lazy dog.'),
         (12, f'This is page {n} of the sample document.'), (12, 'Highlight this sentence for later reference.')]
        for n in (1, 2, 3)]),
    'paper.pdf': dict(title='Quantum Gardening', author='Ada Lovelace', pages=[
        [(18, 'Quantum Gardening'), (12, 'Ada Lovelace'), (12, 'Abstract: Plants measured in superposition.')],
        [(12, 'Results: The cabbages collapsed into a definite state when observed.')]]),
    'notes.pdf': dict(title='Field Notes', author='Rachel Carson', pages=[
        [(16, 'Field Notes'), (12, 'Robins returned on the twelfth of March.')]]),
}

TEXT_FILES = {
    'references.bib': '''@book{knuth1968art,
  title = {The Art of Computer Programming},
  author = {Knuth, Donald E.},
  year = {1968},
  publisher = {Addison-Wesley},
  address = {Reading, MA},
  volume = {1},
  keywords = {algorithms, classic}
}

@article{shannon1948,
  title = {A Mathematical Theory of Communication},
  author = {Shannon, Claude E.},
  journal = {Bell System Technical Journal},
  volume = {27},
  number = {3},
  pages = {379--423},
  year = {1948},
  month = jul,
  doi = {10.1002/j.1538-7305.1948.tb01338.x}
}

@inproceedings{lamport1978,
  title = {Time, Clocks, and the Ordering of Events in a Distributed System},
  author = {Lamport, Leslie},
  booktitle = {Communications of the ACM},
  pages = {558--565},
  year = {1978},
  publisher = {ACM}
}

@phdthesis{noether1907,
  title = {{\\"U}ber die Bildung des Formensystems der tern{\\"a}ren biquadratischen Form},
  author = {Noether, Emmy},
  school = {Universit{\\"a}t Erlangen},
  year = {1907}
}

@misc{example2020dataset,
  title = {An Example Dataset},
  author = {{Example Consortium}},
  year = {2020},
  howpublished = {\\url{https://data.example.org/1}},
  note = {Version 2}
}
''',
    'references.ris': '''TY  - JOUR
TI  - Cramming More Components onto Integrated Circuits
AU  - Moore, Gordon E.
PY  - 1965/04/19/
JO  - Electronics
VL  - 38
IS  - 8
SP  - 114
EP  - 117
KW  - semiconductors
KW  - scaling
ER  -

TY  - BOOK
TI  - Silent Spring
AU  - Carson, Rachel
PY  - 1962
PB  - Houghton Mifflin
CY  - Boston
SN  - 978-0-618-24906-0
KW  - ecology
ER  -

TY  - CHAP
TI  - The Humble Programmer
AU  - Dijkstra, Edsger W.
A2  - Ashenhurst, Robert
T2  - ACM Turing Award Lectures
PY  - 1987
SP  - 17
EP  - 32
PB  - ACM Press
ER  -
''',
    'references.json': json.dumps([
        {'id': 'item1', 'type': 'article-journal', 'title': 'The Mathematical Theory of Games',
         'author': [{'family': 'Neumann', 'given': 'John', 'non-dropping-particle': 'von'}],
         'container-title': 'Annals of Mathematics', 'volume': '1', 'page': '1-20',
         'issued': {'date-parts': [[1928]]}},
        {'id': 'item2', 'type': 'book', 'title': 'Cybernetics', 'author': [{'family': 'Wiener', 'given': 'Norbert'}],
         'publisher': 'MIT Press', 'publisher-place': 'Cambridge, MA', 'issued': {'date-parts': [[1948, 10]]},
         'ISBN': '978-0-262-73009-9'},
        {'id': 'item3', 'type': 'webpage', 'title': 'Example Domain', 'URL': 'https://example.com/',
         'container-title': 'Example', 'accessed': {'date-parts': [[2024, 1, 2]]}},
    ], indent=2) + '\n',
    'references.txt': '''%0 Journal Article
%T Computing Machinery and Intelligence
%A Turing, A. M.
%J Mind
%V 59
%N 236
%P 433-460
%D 1950

%0 Book
%T The Mythical Man-Month
%A Brooks, Frederick P.
%I Addison-Wesley
%C Reading, MA
%D 1975
''',
    'pubmed.nbib': '''PMID- 10000001
TI  - Example of a MEDLINE record about sleep and memory.
AB  - Sleep supports the consolidation of memory.
FAU - Walker, Matthew
AU  - Walker M
FAU - Stickgold, Robert
AU  - Stickgold R
TA  - Example J Neurosci
JT  - Example Journal of Neuroscience
VI  - 12
IP  - 4
PG  - 101-110
DP  - 2004 Apr
LA  - eng
PT  - Journal Article
''',
    'mods.xml': '''<?xml version="1.0" encoding="UTF-8"?>
<modsCollection xmlns="http://www.loc.gov/mods/v3">
  <mods>
    <titleInfo><title>Weaving the Web</title></titleInfo>
    <name type="personal"><namePart type="given">Tim</namePart><namePart type="family">Berners-Lee</namePart>
      <role><roleTerm type="code" authority="marcrelator">aut</roleTerm></role></name>
    <typeOfResource>text</typeOfResource>
    <genre authority="local">book</genre>
    <originInfo><publisher>HarperCollins</publisher><place><placeTerm type="text">San Francisco</placeTerm></place>
      <dateIssued>1999</dateIssued></originInfo>
    <identifier type="isbn">978-0-06-251587-2</identifier>
  </mods>
</modsCollection>
''',
    'minimal.csl': '''<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="never">
  <info>
    <title>Bench Minimal Author-Year</title>
    <id>http://www.example.org/styles/bench-minimal</id>
    <updated>2024-01-01T00:00:00+00:00</updated>
  </info>
  <citation>
    <layout prefix="[" suffix="]" delimiter="; ">
      <names variable="author"><name form="short" and="text"/></names>
      <date variable="issued" prefix=" "><date-part name="year"/></date>
    </layout>
  </citation>
  <bibliography>
    <sort><key variable="author"/></sort>
    <layout suffix=".">
      <names variable="author"><name name-as-sort-order="all" sort-separator=", " initialize-with=". " delimiter="; "/></names>
      <date variable="issued" prefix=" (" suffix=")"><date-part name="year"/></date>
      <text variable="title" prefix=" " font-style="italic"/>
      <text variable="container-title" prefix=", "/>
      <text variable="publisher" prefix=" / "/>
    </layout>
  </bibliography>
</style>
''',
}

TEXT_FILES.update({'references.rdf': '<rdf:RDF\n xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n xmlns:z="http://www.zotero.org/namespaces/export#"\n xmlns:dc="http://purl.org/dc/elements/1.1/"\n xmlns:foaf="http://xmlns.com/foaf/0.1/"\n xmlns:bib="http://purl.org/net/biblio#"\n xmlns:dcterms="http://purl.org/dc/terms/">\n    <bib:Book rdf:about="#item_1">\n        <z:itemType>book</z:itemType>\n        <dc:publisher>\n            <foaf:Organization>\n               <foaf:name>Example Press</foaf:name>\n            </foaf:Organization>\n        </dc:publisher>\n        <bib:authors>\n            <rdf:Seq>\n                <rdf:li>\n                    <foaf:Person>\n                        <foaf:surname>Hopper</foaf:surname>\n                        <foaf:givenName>Grace</foaf:givenName>\n                    </foaf:Person>\n                </rdf:li>\n            </rdf:Seq>\n        </bib:authors>\n        <dcterms:isReferencedBy rdf:resource="#item_2"/>\n        <dc:title>Archive Studies</dc:title>\n        <dc:date>1952</dc:date>\n    </bib:Book>\n    <bib:Memo rdf:about="#item_2">\n        <rdf:value>&lt;p&gt;A preserved note.&lt;/p&gt;</rdf:value>\n        <rdf:type rdf:resource="http://purl.org/net/biblio#Memo"/>\n        <z:itemType>note</z:itemType>\n        <rdf:value>&lt;p&gt;A preserved note.&lt;/p&gt;</rdf:value>\n    </bib:Memo>\n<z:Collection rdf:about="#collection_1"><dc:title>Source Papers</dc:title><dcterms:hasPart rdf:resource="#item_1"/></z:Collection>\n</rdf:RDF>\n', 'endnote.xml': '<?xml version="1.0" encoding="UTF-8"?>\n<xml><records><record><database name="MyLibrary">MyLibrary</database><source-app name="Zotero">Zotero</source-app><ref-type name="Journal Article">17</ref-type><contributors><authors><author>Turing, Alan</author></authors></contributors><titles><title>Endnote Survey</title><secondary-title>Methods Review</secondary-title></titles><periodical><full-title>Methods Review</full-title></periodical><pages>12-19</pages><volume>3</volume><dates><year>1950</year><pub-dates><date>1950</date></pub-dates></dates></record></records></xml>'})

RTF_FILES = {
    'scan.rtf': (r'{\rtf1\ansi\deff0{\fonttbl{\f0 Times New Roman;}}\f0\fs24 '
                 r'Early machines were programmed by hand \{Knuth, 1968\}. '
                 r'The halting problem was described later \{Turing, 1936\}.\par '
                 r'Bibliography\par }' + '\n'),
}


def write(folder, name):
    """Write one named input file into folder and return its path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    if name in PDFS:
        spec = PDFS[name]
        write_pdf(path, spec['pages'], spec.get('title', ''), spec.get('author', ''))
    elif name in TEXT_FILES:
        path.write_text(TEXT_FILES[name], encoding='utf-8')
    elif name in RTF_FILES:
        path.write_text(RTF_FILES[name], encoding='ascii')
    else:
        raise KeyError('unknown fixture ' + name)
    return path

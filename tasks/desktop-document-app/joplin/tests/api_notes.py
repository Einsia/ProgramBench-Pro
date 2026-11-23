"""Note bodies, metadata, partial updates, projection, clipping, and identity."""
from harness import Ref, Suite, expect, resolve, aspects, checked
from semantics import markdown_structure

FIELDS = ('id', 'parent_id', 'title', 'body', 'is_conflict', 'latitude', 'longitude', 'altitude', 'author',
          'source_url', 'is_todo', 'todo_due', 'todo_completed', 'source', 'source_application', 'application_data',
          'order', 'user_created_time', 'user_updated_time', 'markup_language', 'is_shared', 'share_id',
          'conflict_original_id', 'user_data', 'deleted_time', 'is_locked', 'type_')
BASE = {'title': 'Metadata anchor', 'body': 'Unchanged anchor body.', 'author': 'Ada Lovelace',
        'source_url': 'https://example.invalid/field?x=1&y=2', 'latitude': 51.5014, 'longitude': -0.1419,
        'altitude': 27.5, 'user_created_time': 1704067200000, 'user_updated_time': 1735689600000}


def build():
    s = Suite('protocol-notes', 'notes and metadata')
    def setup(c):
        c.call('POST', '/folders', body={'title': 'Notes laboratory'}, save='book')
        c.call('POST', '/folders', body={'title': 'Destination'}, save='other')
        c.call('POST', '/notes', body={**BASE, 'parent_id': Ref('book')}, save='anchor')
        c.call('PUT', '/notes/{anchor}', body={'order': 12.5, 'user_updated_time': BASE['user_updated_time']})
    s.setup('notes', setup)
    s.request('baseline', 'Load an ordinary note with explicit metadata', 'GET', '/notes/{anchor}',
              query={'fields': ','.join(k for k in FIELDS if k != 'type_')}, fields=FIELDS,
              expected={**BASE, 'parent_id': '@book', 'id': '@anchor', 'is_todo': 0, 'todo_due': 0, 'todo_completed': 0})
    texts = [
        ('empty', '', 'Empty body'),
        ('paragraphs', 'First paragraph.\n\nSecond paragraph.\nThird line.', 'Paragraph boundaries'),
        ('terminal-newline', 'Final line\n', 'A final newline'),
        ('leading-spaces', '    code\n  two spaces\nplain', 'Leading whitespace'),
        ('quotes', '"double" and \'single\' — <literal> & entity', 'Quotation and punctuation'),
        ('unicode', '日本語のノート\n中文笔记\nالعربية\nΚαλημέρα\n🙂', 'Multilingual text'),
        ('combining', 'café cafe\u0301 naïve Å A\u030a', 'Combining and precomposed characters'),
        ('tabs', 'name\tvalue\nalpha\t42\nbeta\t0', 'Tab-separated text'),
        ('markdown', '# Header\n\n**strong** _emphasis_ ~~removed~~\n\n- [ ] pending\n- [x] done', 'Markdown syntax'),
        ('code', '```python\nprint("hello")\n```\n\n`inline code`', 'Fenced and inline code'),
        ('table', '| Plant | Count |\n| :--- | ---: |\n| Oak | 3 |\n| Elm | 7 |', 'Markdown table'),
        ('links', '[Example](https://example.invalid/a?x=1)\n\n<https://example.invalid/>', 'Document links'),
        ('long', 'A long line: ' + 'abΩ中 ' * 2048, 'Large UTF-8 body'),
        ('backslashes', r'C:\Notes\draft.txt and \*literal\* and $price', 'Literal backslashes'),
        ('blank-lines', '\n\nBody\n\n\nTail\n\n', 'Blank lines at both boundaries'),
    ]
    for name, body, description in texts:
        key = 'text-' + name
        title = 'Body: ' + description
        s.request(key, 'Create ' + description.lower(), 'POST', '/notes', save=key,
                  body={'title': title, 'body': body, 'parent_id': Ref('book')}, fields=('title', 'body'),
                  expected={'title': title, 'body': body})
        s.request(key + '-read', 'Read the saved ' + description.lower(), 'GET', '/notes/{' + key + '}',
                  query={'fields': 'body,parent_id'}, fields=('body', 'parent_id'), depends=(key,),
                  expected={'body': body, 'parent_id': '@book'})

    edits = {
        'title': ['Renamed note', '标题 — café', ''],
        'body': ['Replacement\n\nBody', '', 'Restored **body**'],
        'author': ['Grace Hopper', '李明', ''],
        'source_url': ['https://example.invalid/new#section', 'https://example.invalid/文档?q=a%20b', ''],
        'latitude': [-90, 89.12345678, 0], 'longitude': [-180, 179.87654321, 0],
        'altitude': [-430.25, 8848.86, 0],
        'is_todo': [1, 0], 'todo_due': [1768550400000, 0], 'todo_completed': [1768478400000, 0],
        'user_created_time': [946684800000, 1709164800000],
        'user_updated_time': [1735689600123, 1767225600000],
        'source': ['web.clip', 'mobile'], 'source_application': ['local.example', ''],
        'application_data': ['{"editor":{"folded":[1,3]}}', ''],
        'user_data': ['{"priority":"high","unicode":"雪"}', ''],
        'order': [12.5, -3.25, 0], 'markup_language': [2, 1], 'is_conflict': [1, 0],
        'parent_id': [Ref('other'), Ref('book')],
    }
    for field, values in edits.items():
        for index, value in enumerate(values):
            key = f'update-{field}-{index}'
            def change(c, field=field, value=value):
                before = c.call('GET', '/notes/{anchor}', query={'fields': 'title,body,parent_id'})['body']
                c.call('PUT', '/notes/{anchor}', body={field: value})
                fields = list(dict.fromkeys([field, 'title', 'body', 'parent_id']))
                after = c.call('GET', '/notes/{anchor}', query={'fields': ','.join(fields)})['body']
                wanted = resolve(value, c.values)
                if field in ('latitude', 'longitude', 'altitude'):
                    wanted = round(float(wanted), 6)
                def changed():
                    got = after[field]
                    if field in ('latitude', 'longitude', 'altitude'):
                        got = round(float(got), 6)
                    return c.clean(checked(got, wanted))
                def retained():
                    keys = [k for k in ('title', 'body', 'parent_id') if k != field]
                    expect({k: after[k] for k in keys}, {k: before[k] for k in keys})
                    return True
                return aspects(value=changed, retained=retained)
            s.add(key, f'Partially update {field} with boundary value {index + 1}', change,
                  {'value': f'The saved {field} has the supplied value.',
                   'retained': 'A partial update preserves unrelated note content and location.'})
    # Restore an independently seeded object for field selection and read-only fields.
    def projection_setup(c):
        c.call('POST', '/notes', body={**BASE, 'parent_id': Ref('book')}, save='projection')
        c.call('PUT', '/notes/{projection}', body={'order': 5.25, 'user_updated_time': BASE['user_updated_time']})
    s.setup('projection', projection_setup, before='projection-id')
    for field in FIELDS:
        if field == 'type_':
            continue  # A computed API marker, not a selectable database field.
        s.request('projection-' + field, 'Read only the requested note field ' + field, 'GET', '/notes/{projection}',
                  query={'fields': field}, fields=(field,))
    for i, fields in enumerate([['title', 'body'], ['author', 'source_url', 'latitude', 'longitude'],
                                ['is_todo', 'todo_due', 'todo_completed'], ['user_created_time', 'user_updated_time'],
                                ['id', 'parent_id']]):
        s.request('projection-group-' + str(i), 'Read a selected group of note fields', 'GET', '/notes/{projection}',
                  query={'fields': ', '.join(fields)}, fields=fields)
    for field in ('id', 'created_time', 'updated_time', 'encryption_applied', 'encryption_cipher_text'):
        def readonly(c, field=field):
            before = c.call('GET', '/notes/{projection}', query={'fields': field})['body'][field]
            value = 'd' * 32 if field == 'id' else ('untrusted' if field == 'encryption_cipher_text' else 42)
            c.call('PUT', '/notes/{projection}', body={field: value})
            after = c.call('GET', '/notes/{projection}', query={'fields': field})['body'][field]
            if field == 'updated_time':
                assert after >= before and after != 42
            else:
                assert after == before
            return {'protected': True}
        s.add('readonly-' + field, 'A note update does not accept client supplied ' + field, readonly,
              {'protected': 'The read-only identity, timestamp or encryption property is protected.'})
    return s


HTML = [
    ('paragraph', '<p>One paragraph.</p><p>Another paragraph.</p>'),
    ('break', '<p>First<br>Second<br/>Third</p>'),
    ('bold', '<p><strong>Important</strong> and <b>bold</b>.</p>'),
    ('italic', '<p><em>Quiet</em> and <i>soft</i>.</p>'),
    ('strike', '<p><s>Before</s> <del>removed</del> After.</p>'),
    ('heading-1', '<h1>Main heading</h1><p>Text.</p>'),
    ('heading-2', '<h2>Section</h2><h3>Subsection</h3>'),
    ('heading-4', '<h4>Detail</h4><h5>Small detail</h5><h6>Footnote</h6>'),
    ('unordered', '<ul><li>Oak</li><li>Elm</li><li>Fir</li></ul>'),
    ('ordered', '<ol><li>Begin</li><li>Continue</li><li>Finish</li></ol>'),
    ('ordered-start', '<ol start="4"><li>Fourth</li><li>Fifth</li></ol>'),
    ('nested-list', '<ul><li>Parent<ul><li>Child</li></ul></li><li>Sibling</li></ul>'),
    ('blockquote', '<blockquote><p>A quotation.</p><p>Second paragraph.</p></blockquote>'),
    ('nested-quote', '<blockquote>Outer<blockquote>Inner</blockquote></blockquote>'),
    ('code-inline', '<p>Use <code>name &lt; value</code> here.</p>'),
    ('pre', '<pre>one\n  two\nthree</pre>'),
    ('code-block', '<pre><code class="language-python">print("hello")\nprint(2)</code></pre>'),
    ('link', '<p><a href="https://example.invalid/page">Visit page</a></p>'),
    ('link-title', '<a href="https://example.invalid/" title="A title">Named link</a>'),
    ('anchor', '<h2 id="section">Section</h2><a href="#section">Go to section</a>'),
    ('rule', '<p>Before</p><hr><p>After</p>'),
    ('entities', '<p>A &amp; B &lt; C &gt; D &quot;text&quot; &nbsp; &#169; &#x1f642;</p>'),
    ('unicode', '<h2>日本語</h2><p>中文 Café Ελληνικά 🙂</p>'),
    ('table', '<table><thead><tr><th>Plant</th><th>Count</th></tr></thead><tbody><tr><td>Oak</td><td>3</td></tr><tr><td>Elm</td><td>7</td></tr></tbody></table>'),
    ('table-alignment', '<table><tr><th align="left">Name</th><th align="right">Count</th></tr><tr><td>Oak</td><td>3</td></tr></table>'),
    ('empty-tags', '<p></p><p>Text <span></span> continues.</p>'),
    ('whitespace', '<div>  First   phrase. </div>\n<div> Second\n phrase. </div>'),
    ('mixed', '<h2>Journal</h2><p><strong>Trip</strong> to <em>river</em>.</p><ul><li>Map</li><li>Water</li></ul>'),
    ('escaped-markdown', '<p>* literal * [brackets] # heading?</p>'),
    ('definition', '<dl><dt>Term</dt><dd>Definition</dd></dl>'),
]


def clipping():
    s = Suite('protocol-clipping', 'HTML clipping and Markdown conversion')
    s.setup('book', lambda c: c.call('POST', '/folders', body={'title': 'Clipping'}, save='book'))
    for name, html in HTML:
        for convert in ('markdown', 'html'):
            key = convert + '-' + name
            title = name + ' clipping ' + convert
            s.request(key, f'Clip {name} HTML as {convert}', 'POST', '/notes', save=key,
                      body={'parent_id': Ref('book'), 'title': title, 'body_html': html, 'convert_to': convert},
                      fields=('body', 'markup_language'), expected={'markup_language': 1 if convert == 'markdown' else 2},
                      transforms={'body':markdown_structure} if convert=='markdown' else {})
            s.request(key + '-stored', f'Read the saved {convert} clipping of {name}', 'GET', '/notes/{' + key + '}',
                      query={'fields': 'body,title'}, fields=('body', 'title'), depends=(key,), expected={'title': title},
                      transforms={'body':markdown_structure} if convert=='markdown' else {})
    return s

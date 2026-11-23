"""Independent public-interface cases: embedding, Markdown grammar, properties and editing."""
from collections import defaultdict
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def assertion(wid, cid, kind='html', path=None):
    descriptions = {'html': 'The generated document preserves the reference semantics for this input.',
                    'text': 'The edited Markdown source has the reference content.',
                    'properties': 'The supplied file properties are interpreted as in the reference.',
                    'name': 'The embedding interface preserves the document name.'}
    out = {'id': f'{wid}/{cid}/{kind}', 'channel': 'backend', 'method': 'program',
           'requirement': descriptions[kind], 'check': {'type': kind}}
    if path:
        out['check']['path'] = path
    return out


def episode(wid, feature, cases):
    cps = []
    for c in cases:
        checks = c.pop('checks', ['html'])
        cps.append({**c, 'goal': c.get('description') or 'Observe the document after the stated operation.',
                    'assertions': [assertion(wid, c['id'], kind) for kind in checks]})
    return {'id': wid, 'feature': feature, 'execution': 'program', 'initial_state':
            'Each checkpoint starts with a fresh product data directory and browser profile. Its own input is opened through the actual embedding interface.',
            'setup': [], 'inputs': {}, 'checkpoints': cps}


def property_cases():
    specimens = {
        'abbr': 'The HTML standard.\n\n*[HTML]: Hyper Text Markup Language',
        'breaks': 'One line\nA second line',
        'deflist': 'Harbor\n: A sheltered port\n\nSea\n: Open water',
        'del': 'A ~~removed~~ word and &copy; notice.',
        'fence': '```js\nconst value = 7;\n```',
        'footnote': 'A note[^a].\n\n[^a]: Explanation.',
        'imgsize': '![Badge](badge.png =48x32)',
        'linkify': 'https://example.org/path?q=one and mail@example.org',
        'mark': 'A ==highlighted== passage.',
        'sub': 'Water H~2~O.',
        'sup': 'Area x^2^.',
        'table': '| Harbor | Depth |\n|:--|--:|\n| West | 12 |',
        'tasklist': '- [x] Arrived\n- [ ] Departed',
        'typographer': '"Hello" -- (c) ... (tm)',
    }
    cases=[]
    for ext, text in specimens.items():
        cases.append({'id':'disable-'+ext,'text':text,
                      'properties':f'extensions:\n  markdown:\n    {ext}: false\n',
                      'description':f'Interpret a document with the {ext} Markdown option disabled.', 'checks':['html','properties']})
    for name,text in [('emoji',':smile: :heart: :not-an-emoji:'),('katex','$x^2$ and $$y^2$$'),
                      ('mermaid','```mermaid\ngraph LR\nA-->B\n```'),('abc','```abc\nX:1\nT:Tune\nM:4/4\nK:C\nCDEF GABc|\n```')]:
        cases.append({'id':'disable-'+name,'text':text,'properties':f'extensions:\n  {name}:\n    enabled: false\n',
                      'description':f'Disable the {name} extension.', 'checks':['html','properties']})
    cases.append({'id':'emoji-shortcuts','text':':) :-( ;-) :D <3','properties':'extensions:\n  emoji:\n    shortcuts: true\n',
                  'description':'Enable emoticon shortcuts.', 'checks':['html','properties']})
    specimen='# Heading\n\nA ~~deleted~~ ==marked== H~2~O x^2^ :smile: text.\nline two\n\n- [x] Task\n\n| A | B |\n|--|--|\n| 1 | 2 |\n\nhttps://example.org\n\n$z^2$'
    for preset in ['commonmark','gfm','default','zero']:
        cases.append({'id':'preset-'+preset,'text':specimen,'properties':f'extensions:\n  preset: {preset}\n',
                      'description':f'Interpret the {preset} extension preset.', 'checks':['html','properties']})
    values=[('strings','title: Harbor\nauthor: Ada\ntags: [water, maps]\n'),
            ('scalars','count: 7\nratio: 1.5\nenabled: true\nmissing: null\n'),
            ('quoted','title: "001"\nflag: "false"\n'),
            ('unicode','title: "海岸 Café"\nauthor: "Zoë"\n'),
            ('nested','custom:\n  location: West\n  depths: [3, 7, 11]\n'),
            ('multiline','summary: |\n  first line\n  second line\n'),
            ('folded','summary: >\n  first line\n  second line\n'),
            ('anchors','base: &base\n  title: Port\ncopy: *base\n'),
            ('comments','# Comment\ntitle: Harbor # trailing comment\n'),
            ('date','date: 2024-01-02\n'),
            ('invalid','title: [unfinished\n'),
            ('empty',''),('document-marker','---\ntitle: Harbor\n...\n')]
    for name,props in values:
        cases.append({'id':'yaml-'+name,'text':'# Metadata\n\nA document with file properties.','properties':props,
                      'description':'Interpret YAML properties: '+name+'.','checks':['properties']})
    for i,name in enumerate(['Harbor', '海岸 Café', 'Report.md', 'spaces  inside', 'A & B <draft>', '"Quoted"', '🌊 Tide', '']):
        cases.append({'id':f'name-{i+1}','text':'A named document.','name':name,'description':'Embedding file-name handling.', 'checks':['name']})
    return cases


def keyboard_cases():
    cases=[]
    def add(cid,text,start,end,actions,description):
        cases.append(dict(id=cid,text=text,selection=[start,end],actions=actions,description=description,checks=['text']))
    contexts=[('word','Sail home',0,4),('middle','Sail home safely',5,9),('multiline','North\nSouth',0,11),
              ('empty','Harbor',3,3),('unicode','海岸 Café 🌊',3,7),('space','one two three',3,8)]
    formats=[('bold','Control+Shift+B'),('italic','Control+Shift+I'),('strike','Control+Shift+S'),
             ('code','Control+Shift+K'),('quote','Control+Shift+Q'),('unordered','Control+Shift+U'),
             ('ordered','Control+Shift+O'),('checklist','Control+Shift+C'),('heading','Control+Shift+H')]
    for fmt,key in formats:
        for context,text,start,end in contexts:
            add(fmt+'-'+context,text,start,end,[{'op':'press','key':key}],f'Apply {fmt} formatting to the {context} selection using its default shortcut.')
    for fmt,key,source,start,end in [
        ('bold','Control+Shift+B','**Sail** home',2,6),('italic','Control+Shift+I','*Sail* home',1,5),
        ('strike','Control+Shift+S','~~Sail~~ home',2,6),('code','Control+Shift+K','`Sail` home',1,5),
        ('quote','Control+Shift+Q','> Sail home',2,11),('unordered','Control+Shift+U','- Sail home',2,11),
        ('ordered','Control+Shift+O','1. Sail home',3,12),('checklist','Control+Shift+C','- [ ] Sail home',6,15)]:
        add(fmt+'-remove',source,start,end,[{'op':'press','key':key}],f'Toggle existing {fmt} formatting off.')
    operations=[
        ('insert','abcd',2,2,[{'op':'type','value':'XY'}]),
        ('replace','abcdef',2,5,[{'op':'type','value':'XY'}]),
        ('unicode-insert','Café 海岸',5,5,[{'op':'type','value':'🌊 '}]),
        ('backspace','abcd',2,2,[{'op':'press','key':'Backspace'}]),
        ('delete','abcd',2,2,[{'op':'press','key':'Delete'}]),
        ('selection-delete','abcdef',1,4,[{'op':'press','key':'Backspace'}]),
        ('split-line','NorthSouth',5,5,[{'op':'press','key':'Enter'}]),
        ('join-line','North\nSouth',6,6,[{'op':'press','key':'Backspace'}]),
        ('tab','North\nSouth',0,11,[{'op':'press','key':'Tab'}]),
        ('untab','\tNorth\n\tSouth',0,13,[{'op':'press','key':'Shift+Tab'}]),
        ('bullet-continue','- North',7,7,[{'op':'press','key':'Enter'},{'op':'type','value':'South'}]),
        ('number-continue','1. North',8,8,[{'op':'press','key':'Enter'},{'op':'type','value':'South'}]),
        ('checked-continue','- [x] North',11,11,[{'op':'press','key':'Enter'},{'op':'type','value':'South'}]),
        ('quote-continue','> North',7,7,[{'op':'press','key':'Enter'},{'op':'type','value':'South'}]),
        ('bullet-exit','- North\n- ',10,10,[{'op':'press','key':'Enter'}]),
        ('horizontal-rule','North',5,5,[{'op':'press','key':'Control+Shift+R'}]),
        ('undo-type','North',5,5,[{'op':'type','value':' harbor'},{'op':'wait','seconds':.5},{'op':'press','key':'Control+Z'}]),
        ('redo-type','North',5,5,[{'op':'type','value':' harbor'},{'op':'wait','seconds':.5},{'op':'press','key':'Control+Z'},{'op':'press','key':'Control+Y'}]),
        ('undo-bold','North',0,5,[{'op':'press','key':'Control+Shift+B'},{'op':'press','key':'Control+Z'}]),
        ('redo-bold','North',0,5,[{'op':'press','key':'Control+Shift+B'},{'op':'press','key':'Control+Z'},{'op':'press','key':'Control+Y'}]),
        ('copy-paste','North',0,5,[{'op':'press','key':'Control+C'},{'op':'press','key':'End'},{'op':'press','key':'Control+V'}]),
        ('cut-paste','North South',0,5,[{'op':'press','key':'Control+X'},{'op':'press','key':'End'},{'op':'press','key':'Control+V'}]),
        ('select-all-replace','North\nSouth',0,0,[{'op':'press','key':'Control+A'},{'op':'type','value':'East'}]),
    ]
    for cid,text,start,end,actions in operations:add(cid,text,start,end,actions,'Text editing: '+cid+'.')
    return cases


def extra_syntax():
    samples={
        'math-inline':'A $x^2+y^2$ relation.', 'math-display':'$$\n\\frac{a}{b} = c\n$$',
        'math-escaped':r'A \$5 price and $x$ value.', 'math-currency':'Costs $5 and $10 today.',
        'math-unclosed':'Before $x + y and after.', 'math-backslash':r'\(x^2\) and \[y^2\]',
        'mermaid-flow':'```mermaid\ngraph LR\nA[Start] --> B{Choice}\nB -->|yes| C[End]\n```',
        'mermaid-sequence':'```mermaid\nsequenceDiagram\nAlice->>Bob: Hello\nBob-->>Alice: Reply\n```',
        'abc':'```abc\nX:1\nT:Harbor tune\nM:4/4\nL:1/4\nK:C\nCDEF|GABc|\n```',
        'task-nesting':'- [ ] Outer\n  - [x] Inner\n- [X] Uppercase\n- [] Not a task',
        'image-width':'![Tide](tide.png =80x)', 'image-height':'![Tide](tide.png =x40)',
        'image-size':'![Tide](tide.png =80x40)', 'image-title-size':'![Tide](tide.png "Tide" =80x40)',
        'mark-simple':'A ==marked== phrase.', 'mark-multiple':'==one== and ==two==.',
        'mark-space':'== spaced == and ==tight==', 'mark-nested':'==**bold** and *italic*==',
        'mark-escape':r'\==literal== and ==marked==', 'mark-single':'=single= and ====long====',
        'anchor-duplicates':'# Same\n\n# Same\n\n## Same\n\n[First](#same) [Second](#same-1) [Third](#same-2)', 'anchor-unicode':'# Café 海岸\n\n[Jump](#café-海岸)',
        'anchor-markup':'# **Strong** `code` and [link](https://example.org)',
        'toc':'[TOC]\n\n# North\n\n## Harbor\n\n# South',
        'frontmatter-source':'---\ntitle: Harbor\n---\n\n# Body',
    }
    return [dict(id=k,text=v,description='Extension interaction: '+k+'.') for k,v in samples.items()]


def embedding_sequences():
    cases=[]
    for cid,name,text,props in [
      ('different-name','Second note','Second body.','title: Second\n'),
      ('same-name','First note','Replacement body.','status: revised\n'),
      ('empty-body','Empty note','','title: Empty\n'),
      ('cleared-properties','No properties','Plain body.',''),
      ('unicode-name','海岸 Café','Unicode 🌊 body.','title: "海岸"\n'),
      ('multiline-properties','Multiline','A body.','summary: |\n  North\n  South\n'),
    ]:
        cases.append({'id':cid,'text':'First body.','name':'First note','properties':'title: First\n',
            'actions':[{'op':'embed_open','name':name,'text':text,'properties':props}],
            'checks':['name','text','html','properties'],'description':'Reopen the public embedding editor and observe the current document rather than a stale message: '+cid+'.'})
    return cases


def build():
    grouped=defaultdict(list)
    for c in json.loads((FIXTURES/'markdown.json').read_text()):grouped[c['feature']].append(c)
    out=[]
    for feature,cases in grouped.items():
        for i in range(0,len(cases),40):
            wid='program-'+feature.replace('_','-')+('-'+str(i//40+1) if len(cases)>40 else '')
            out.append(episode(wid,feature,cases[i:i+40]))
    out.append(episode('program-properties','file-properties',property_cases()))
    keys=keyboard_cases()
    for i in range(0,len(keys),30):out.append(episode('program-keyboard-'+str(i//30+1),'editing',keys[i:i+30]))
    out.append(episode('program-extensions','extensions',extra_syntax()))
    out.append(episode('program-embedding-reopen','embedding',embedding_sequences()))
    return out

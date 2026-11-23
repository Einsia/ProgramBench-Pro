"""Record-time sanity checks for authored goals; never define frozen truth from an unchecked operation."""


def validate(episode, checkpoint, check, full):
    k,c=episode['id'],checkpoint['id']
    if check['kind']!='document':return
    if k in ('storage-ctz','storage-ctx'):
        assert full['format']=={'storage':k.removeprefix('storage-'),'encrypted':True}, 'wrong protected storage format'
    nodes=full['nodes']
    inbox=nodes.get('Inbox',{})
    text=inbox.get('text','')
    content=check['aspect'].startswith(('content:','node:'))
    if k=='text-clipboard' and content:
        assert 'Call the plumber tomorrow.' in nodes['Archive']['text'], 'the copied sentence was not pasted'
        if c=='cut':assert 'Old receipts and letters.' not in nodes['Archive']['text']
    if k=='text-undo-redo' and content:
        assert text.startswith('Weekly planning\n'), 'the complete replacement heading was not restored'
    if k=='insert-image' and content:
        assert len([w for w in inbox.get('widgets',[]) if w['kind']=='image'])==1, 'image insertion or redo did not occur'
    if k=='insert-codebox' and content and c!='copy':
        boxes=[w for w in inbox.get('widgets',[]) if w['kind']=='codebox']
        if c=='insert':
            assert len(boxes)==1 and boxes[0]['text']=='print("ready")\nprint(2 + 3)' and boxes[0]['line_numbers']
        if c=='keep':
            assert not boxes and 'print("ready")\nprint(2 + 3)' in text
    if k=='insert-table' and content:
        tables=[w for w in inbox.get('widgets',[]) if w['kind']=='table']
        rows=[['Item','Count'],['Apples','3'],['Pears','8']]+([['','']] if c=='row' else [])
        assert len(tables)==1 and tables[0]['rows']==rows
    attributes={
        'font-emphasis':{'bold':('Meeting notes','weight','heavy'), 'italic':('Call the plumber tomorrow.','style','italic'),
                         'underline':('Buy milk and eggs.','underline','single'), 'strike':('Renew the library card.','strikethrough','true')},
        'font-special':{'mono':('Meeting notes','family','monospace'), 'small':('Call the plumber tomorrow.','scale','small'),
                        'sub':('Buy milk and eggs.','scale','sub'), 'super':('Renew the library card.','scale','sup')},
        'text-colors':{'foreground':('Meeting notes','foreground','#e01b24'), 'background':('Buy milk and eggs.','background','#f9f06b')},
    }
    if k in attributes and content:
        value,attr,want=attributes[k][c]
        assert any(value in run and props.get(attr)==want for run,props in inbox.get('runs',[])), f'missing requested {attr}'
    if k.startswith('headings-') and content:
        value={'h1':'Meeting notes','h2':'Call the plumber tomorrow.','h3':'Buy milk and eggs.',
               'h4':'Meeting notes','h5':'Call the plumber tomorrow.','h6':'Buy milk and eggs.'}[c]
        assert any(value in run and props.get('scale')==c for run,props in inbox.get('runs',[])), 'missing heading'
        if k=='headings-small':
            anchors={w['name'] for w in inbox.get('widgets',[]) if w['kind']=='anchor'}
            assert any(run==value and props.get('link','').startswith('node Inbox#')
                       and props['link'].split('#',1)[1] in anchors
                       for run,props in inbox.get('runs',[])), 'missing visible heading TOC link'
    if k.startswith('list-') and content:
        marker={'list-bullets':'• ', 'list-numbers':'1. ', 'list-todo':'☐ '}[k]
        assert marker+'Call the plumber tomorrow.' in text
        if c=='append':assert 'Wash the car.' in text
    if k=='search-current' and content:
        assert ('electrician' if c=='replace' else 'Buy bread.') in text
        if c=='regex':assert text.count('Buy bread.')==2 and 'Buy milk\tand\teggs.' in text and 'Keep milk and eggplant.' in text
    if k.startswith('import-') and check['aspect']=='imported':
        names={n['props']['name'] for p,n in nodes.items() if p.split('/')[0] not in {'Inbox','Projects','Archive','Script'}}
        if k.endswith('-folder') and not k.startswith('import-native'):
            assert {'First','Second'}<=names, 'folder import did not include both root and nested files'
        if k in ('import-leo','import-mempad','import-treepad','import-indented'):
            assert {'Imported Parent','Imported Child'}<=names
        if k.startswith('import-native'):
            assert {'Overview','Tasks','Script','Media','Ünïcødé'}<=names
        if k=='import-rednotebook':assert {'2024-01-01','2024-01-02'}<=names
        if k=='import-markdown':
            page=nodes['page']
            assert 'First' in page['text'] and 'Second' in page['text'] and 'Example' in page['text']
            assert any(w['kind']=='codebox' and 'print(42)' in w['text'] for w in page.get('widgets',[]))
    if k=='nodes-shared' and c=='edit' and content:
        assert 'Shared update.' in nodes['Archive']['text'] and nodes['Archive']['text']==nodes['Archive#2']['text']

    if k=='image-transform' and content:
        image=nodes['Image']['widgets'][0]
        size=(100,160) if c=='rotate' else (80,50) if c=='scale' else (160,100)
        assert (image['width'],image['height'])==size
        if c in ('rotate','flip'):
            import io,fixtures,artifacts
            from PIL import Image
            source=Image.open(io.BytesIO(fixtures.pattern_png())).convert('RGBA')
            transformed=source.transpose(Image.Transpose.ROTATE_270 if c=='rotate' else Image.Transpose.FLIP_LEFT_RIGHT)
            out=io.BytesIO();transformed.save(out,format='PNG')
            assert image['sha256']==artifacts.png_info(out.getvalue())['sha256']
    if k=='table-columns' and content:
        rows=nodes['Table']['widgets'][0]['rows']
        expected={'move':[['Count','Item','Note'],['2','Zebra','z'],['5','Apple',''],['3','Mango','sweet']],
                  'add':[['Item','Count','','Note'],['Zebra','2','','z'],['Apple','5','',''],['Mango','3','','sweet']],
                  'delete':[['Item','Count'],['Zebra','2'],['Apple','5'],['Mango','3']]}[c]
        assert rows==expected
    if k=='table-rows' and content:
        rows=nodes['Table']['widgets'][0]['rows']
        order={'sort':['Apple','Mango','Zebra'],'copy':['Zebra','Apple','Mango','Apple'],
               'cut':['Apple','Mango','Zebra'],'up':['Zebra','Mango','Apple']}[c]
        assert [row[0] for row in rows[1:]]==order
        values={'Apple':['5',''],'Mango':['3','sweet'],'Zebra':['2','z']}
        assert all(row[1:]==values[row[0]] for row in rows[1:])
    if k=='table-properties' and content:
        widget=nodes['Table']['widgets'][0]
        assert widget['light'] and widget['default_width']==90
    if k=='codebox-files' and content:
        box=nodes['Code']['widgets'][0]
        if c=='load':assert box['text']=='def greet(name):\n    return "Hello " + name\n\nprint(greet("Ada"))\n'
        if c=='properties':assert box['width']==320 and box['height']==160 and box['line_numbers'] and box['syntax']=='python3'
    if k=='rich-object-clipboard' and content:
        dest=nodes['Destination']
        assert dest['text'].startswith('Destination start.\nBold title\nBody link\n')
        assert [w['kind'] for w in dest['widgets']]==['image','codebox','table']
        if c=='cut':assert nodes['Rich']['text']=='' and nodes['Rich']['widgets']==[]
    if k=='text-cleanup':
        expected='alpha\n\tbeta\tgamma\n' if c=='strip' else 'alpha   \n    beta    gamma  \n'
        assert nodes['Cleanup']['text']==expected
    if k=='readonly-effects' and content:
        assert 'SHOULD NOT APPEAR' not in text
        if c=='unlock':assert 'Writable again.' in text
    if k=='search-multiple':
        if c=='whole':assert nodes['Alpha']['text']=='fox catapult CAT\n' and nodes['Excluded']['text']=='cat secret\n'
        if c=='subtree':assert nodes['Alpha']['text']=='pet catapult CAT\n' and nodes['Other']['text']=='dog cat\n'
        if c=='override':assert nodes['Excluded']['text']=='dog secret\n' and nodes['Other']['text']=='dog dog\n'
    if k=='format-reuse' and content:
        for phrase in (['Source phrase','Target phrase'] if c=='clone' else ['Source phrase','Target phrase','Latest phrase']):
            assert any(phrase==t and at.get('weight')=='heavy' and at.get('style')=='italic' for t,at in nodes['Format']['runs'])
    if k=='format-occurrence' and content:
        assert nodes['Repeated']['spans']==[{'start':14,'end':25,'attributes':{'weight':'heavy'}}]
    if k=='tree-reparent-paste' and c=='paste':
        assert 'Projects#2/Garden' in nodes and 'Projects#2/Kitchen' in nodes and 'Projects/Garden' in nodes
    if k=='node-syntax-inherit':
        assert all(nodes[p]['props']['syntax']=='plain-text' for p in ('Projects','Projects/Garden','Projects/Kitchen'))
    if k=='quit-discard' and c=='restart':assert 'Discard this edit.' not in text

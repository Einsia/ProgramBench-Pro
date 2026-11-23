"""Small independent source documents for each native import adapter."""
HTML = '<!DOCTYPE html><html><body><h1>Imported heading</h1><p>A <b>bold</b> word &amp; a <i>slanted</i> word.</p><ul><li>First</li><li>Second</li></ul><p><a href="https://example.com">Example</a></p></body></html>'
MD = '# Imported heading\n\nA **bold** word and an _italic_ word.\n\n- First\n- Second\n\n```python\nprint(42)\n```\n\n[Example](https://example.com)\n'
TEXT = 'Imported plain note\nSecond line: café, 東京.\n'
TOMBOY = '''<?xml version="1.0"?><note version="0.3" xmlns="http://beatniksoftware.com/tomboy"><title>Imported Note</title><text xml:space="preserve"><note-content version="0.1">Imported Note\nA <bold>bold</bold> and <italic>italic</italic> note.\n<list><list-item>First</list-item><list-item>Second</list-item></list></note-content></text><tags/></note>'''
LEO = '''<?xml version="1.0"?><leo_file><leo_header file_format="2"/><globals/><preferences/><find_panel_settings/><vnodes><v t="a"><vh>Imported Parent</vh><v t="b"><vh>Imported Child</vh></v></v></vnodes><tnodes><t tx="a">Parent body.</t><t tx="b">Child body.</t></tnodes></leo_file>'''
TREEPAD = '<Treepad version 3.0>\n<node>\nNotebook\n0\nDocument root.\n<end node> 5P9i0s8y19Z\n<node>\nImported Parent\n1\nParent body.\n<end node> 5P9i0s8y19Z\n<node>\nImported Child\n2\nChild body.\n<end node> 5P9i0s8y19Z\n'
MEM = b'MeMpAd.1\0\0\x01Imported Parent\0Parent body.\0\x02Imported Child\0Child body.\0'
NOTECASE = '<html><body><DL><DT style="font-weight: bold;"><A name="abcdefghijklmnopqrstuv"></A>Imported Note</DT><DD><p>NoteCase <b>bold</b> content.</p></DD></DL></body></html>'
RED = '<html><body><p>\n<span id="2024-01-01"></span>\n</p><h1>2024-01-01</h1><p>First day <b>bold</b> text.</p><p>\n<span id="2024-01-02"></span>\n</p><h1>2024-01-02</h1><p>Second day text.</p></body></html>'
ZIM = 'Content-Type: text/x-zim-wiki\nWiki-Format: zim 0.6\nCreation-Date: 2024-01-01T00:00:00+00:00\n\n====== Imported heading ======\nA **bold** word and //italic// word.\n* First\n* Second\n'

# key, menu label, selected path, files, visible result
CASES = [
 ('plain','From Plain Text File','plain.txt',{'plain.txt':TEXT},'A new plain node shows Imported plain note and the Unicode second line.'),
 ('html','From HTML File','page.html',{'page.html':HTML},'The imported page shows a heading, styled text and a two-item list.'),
 ('markdown','From Markdown File','page.md',{'page.md':MD},'The imported Markdown shows a heading, styled text, a list and a code block.'),
 ('indented','From Indented List File','outline.txt',{'outline.txt':'Imported Parent\n Imported Child\nImported Other\n'},'The imported outline has Imported Child beneath Imported Parent, with Imported Other as another root.'),
 ('plain-folder','From Folder of Plain Text Files','texts',{'texts/First.txt':TEXT,'texts/sub/Second.txt':'Nested note.'},'The imported folder contains First and a nested Second note.'),
 ('html-folder','From Folder of HTML Files','pages',{'pages/First.html':HTML,'pages/sub/Second.html':'<p>Nested <b>HTML</b>.</p>'},'The imported folder contains First and a nested Second HTML note.'),
 ('markdown-folder','From Folder of Markdown Files','markdown',{'markdown/First.md':MD,'markdown/sub/Second.md':'## Nested heading\n\nSecond note.'},'The imported folder contains First and a nested Second Markdown note.'),
 ('gnote','From Gnote Folder','gnote',{'gnote/note.note':TOMBOY},'The imported Gnote note is named Imported Note and contains styled text and a list.'),
 ('tomboy','From Tomboy Folder','tomboy',{'tomboy/note.note':TOMBOY},'The imported Tomboy note is named Imported Note and contains styled text and a list.'),
 ('keepnote','From KeepNote Folder','keepnote',{'keepnote/Imported Note/page.html':HTML},'The imported KeepNote folder contains Imported Note with formatted page content.'),
 ('leo','From Leo File','outline.leo',{'outline.leo':LEO},'The Leo import shows Imported Parent with an Imported Child beneath it; the selected parent displays Parent body.'),
 ('mempad','From Mempad File','notes.lst',{'notes.lst':MEM},'The Mempad import shows Imported Parent with Imported Child beneath it; the selected parent displays Parent body.'),
 ('treepad','From Treepad Lite File','notes.hjt',{'notes.hjt':TREEPAD},'The Treepad import shows Imported Parent with Imported Child beneath it; the selected parent displays Parent body.'),
 ('notecase','From NoteCase HTML File','notes.html',{'notes.html':NOTECASE},'The NoteCase import contains Imported Note with bold content.'),
 ('rednotebook','From RedNotebook HTML File','journal.html',{'journal.html':RED},'The RedNotebook import contains separate daily notes for the two dates.'),
 ('zim','From Zim Folder','zim',{'zim/Imported.txt':ZIM},'The Zim import contains Imported with a heading, emphasis and list items.'),
]


def files(key):
    return [(name, value.encode('utf-8') if isinstance(value,str) else value)
            for k,label,path,entries,description in CASES if k==key for name,value in entries.items()]


def episodes():
    from specification import action as A, menu as M, saved as D, step as C, episode as W, inbox
    result=[]
    for key,label,path,entries,visible in CASES:
        k='import-'+key
        selected = {'plain':'plain', 'html':'page', 'markdown':'page', 'indented':'Imported Parent',
                    'plain-folder':'First', 'html-folder':'First', 'markdown-folder':'First',
                    'gnote':'Imported Note', 'tomboy':'Imported Note', 'keepnote':'Imported Note',
                    'leo':'Imported Parent', 'mempad':'Imported Parent', 'treepad':'Imported Parent',
                    'notecase':'Imported Note', 'rednotebook':'2024-01-01', 'zim':'Imported'}[key]
        checks=D(('tree','imported'))
        episode = W(k,'imports',[
            C('import',f'Import {inbox(k)}/{path} with the {label} command at the tree root. '
              f'Expand the imported branches, select {selected}, and save the document.',visible,
              [A('import',path='inputs/'+path,label=label),M('Tree','Expand All Nodes'),A('node',name=selected),A('save')],checks,depends=('setup:inputs',))
        ],inputs=[{'import':key}])
        if key == 'html-folder':
            episode['budget'].update(calls=200, tokens=3_000_000, seconds=3000)
        result.append(episode)
    for fmt,label in [('ctd','From CherryTree File'),('folder','From CherryTree Folder')]:
        k='import-native-'+fmt
        result.append(W(k,'imports',[
            C('import',f'Import {inbox(k)}/other'+('.ctd' if fmt=='ctd' else '')+
              ' at the tree root. Expand the imported branch and save.',
              'The original notes remain, and the imported Overview, Media and Unicode notes are present.',
              [A('import',path='inputs/other'+('.ctd' if fmt=='ctd' else ''),label=label),M('Tree','Expand All Nodes'),A('save')],
              D(('tree','imported')),depends=('setup:inputs',))
        ],inputs=[{'document':'kitchen','format':fmt,'as':'other'}]))
    return result

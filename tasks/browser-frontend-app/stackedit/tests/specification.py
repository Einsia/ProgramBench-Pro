"""Functional GUI goals and reference-only routes, independent of candidate widget design."""
import re

def fenced(value,language='text'):
    fence='`'*max(3,1+max((len(m.group()) for m in re.finditer(r'`+',value)),default=0))
    return fence+language+'\n'+value+'\n'+fence

def T(value):return {'do':'title','value':value}
def X(value):return {'do':'text','value':value}
def M(value):return {'do':'menu','value':value}
def F(value,**kw):return {'do':'field','value':value,**kw}
def S(value):return {'do':'source','value':value}
def P(key):return {'op':'press','key':key}
def C(value):return {'do':'code-field','value':value}
def W():return {'op':'wait','seconds':1}
def R(value):return {'do':'rename','value':value}

def cp(cid,goal,acceptance,recipe,text='Harbor notes\n\nA short document.',selection=None,prepare=(),checks=(),**kw):
    return dict(id=cid,goal=goal,acceptance=acceptance,recipe=recipe,text=text,selection=selection,prepare=list(prepare),checks=list(checks),**kw)


def episode(wid,feature,points,files=()):
    cps=[]
    for point in points:
        c=dict(point);acceptance=c.pop('acceptance');checks=c.pop('checks')
        aa=[{'id':wid+'/'+c['id']+'/visible','channel':'frontend','method':'agent','requirement':acceptance}]
        for i,check in enumerate(checks):
            aa.append({'id':wid+'/'+c['id']+'/output'+str(i+1),'channel':'backend','method':'program',
                       'requirement':'The user-visible operation produces the reference document content or file.', 'check':check})
        c['assertions']=aa;cps.append(c)
    n=len(cps)
    return {'id':wid,'feature':feature,'execution':'gui','initial_state':'A fresh local workspace for each checkpoint. The stated source and selection are prepared through the public editor surface.',
            'setup':[],'inputs':{'files':list(files)},'session':'Each goal starts from its own prepared state. Use visible application controls, pointer and keyboard. Enter exact supplied text. A goal about formatting commands must use the application formatting operation; other goals may enter Markdown directly. Imported files are available in the listed inputs.',
            'allowed_equivalents':['Any visible route that achieves the same functional outcome is valid.','Labels, layout, colors and widget types may differ.'],
            'forbidden_bypasses':['Do not recreate a missing formatting or management command by editing source unless the goal explicitly asks to enter Markdown.'],
            'budget':{'calls':min(400,40+35*n),'tokens':min(8000000,600000+600000*n),'seconds':400+300*n},'checkpoints':cps}


SOURCE={'type':'source'}
RENDER={'type':'render-source'}

def rendering():
    rows=[
      ('inline','strong','A **bold** word.','The preview shows the word bold with strong emphasis.'),
      ('inline','emphasis','A *slanted* word.','The preview shows slanted with italic emphasis.'),
      ('inline','combined','A ***combined*** word.','The preview shows combined with both strong and italic emphasis.'),
      ('inline','strike','Keep ~~remove~~ this.','The preview shows remove struck through.'),
      ('inline','mark','A ==highlighted== phrase.','The preview shows highlighted with a visible highlight.'),
      ('inline','subscript','Water is H~2~O.','The preview shows the 2 as a subscript.'),
      ('inline','superscript','Area is x^2^.','The preview shows the 2 as a superscript.'),
      ('inline','code','Run `a < b && c` now.','The preview shows the exact expression as inline code.'),
      ('inline','escape',r'Write \*literal stars\* and \# hash.','The preview shows literal asterisks and a hash without formatting them.'),
      ('inline','entities','Fish &amp; chips &copy; 2024.','The preview shows an ampersand and copyright symbol.'),
      ('inline','emoji',':smile: :heart: :rocket:','The preview shows a smile, heart and rocket emoji.'),
      ('inline','smartquotes','"Harbor" -- \'tide\' ...','The preview displays typographic quotation marks, a dash and an ellipsis.'),
      ('blocks','h1','# Harbor','The preview shows Harbor as a top-level heading.'),
      ('blocks','h2','## Harbor','The preview shows Harbor as a second-level heading.'),
      ('blocks','h3','### Harbor','The preview shows Harbor as a third-level heading.'),
      ('blocks','h4','#### Harbor','The preview shows Harbor as a fourth-level heading.'),
      ('blocks','h5','##### Harbor','The preview shows Harbor as a fifth-level heading.'),
      ('blocks','h6','###### Harbor','The preview shows Harbor as a sixth-level heading.'),
      ('blocks','setext','Harbor\n======\n\nTide\n----','The preview shows two headings at different levels.'),
      ('blocks','paragraphs','North harbor.\n\nSouth harbor.','The preview shows two separate paragraphs.'),
      ('blocks','break','North\nSouth','The preview shows North and South on separate lines within a paragraph.'),
      ('blocks','rule','North\n\n---\n\nSouth','The preview shows a horizontal separator between North and South.'),
      ('blocks','quote','> A sheltered harbor.\n> Safe in storms.','The preview presents both lines as a block quotation.'),
      ('blocks','nested-quote','> Outer\n>\n> > Inner','The preview shows Inner nested inside the Outer quotation.'),
      ('lists','unordered','- North\n- South\n- East','The preview shows a three-item bulleted list.'),
      ('lists','ordered','1. North\n2. South\n3. East','The preview shows a three-item numbered list.'),
      ('lists','start','7. North\n8. South','The preview shows a numbered list beginning at 7.'),
      ('lists','nested','- Harbor\n  - Dock\n  - Pier\n- Sea','The preview shows Dock and Pier as children of Harbor.'),
      ('lists','mixed','1. Harbor\n   - Dock\n   - Pier\n2. Sea','The preview shows a bulleted sublist inside the numbered list.'),
      ('lists','task','- [x] Arrived\n- [ ] Departed','The preview shows Arrived checked and Departed unchecked.'),
      ('lists','loose','- First paragraph.\n\n  A continuation.\n\n- Second item.','The preview keeps the continuation paragraph inside the first list item.'),
      ('lists','definition','Harbor\n: A sheltered port.\n\nTide\n: Rise and fall of the sea.','The preview shows terms paired with their definitions.'),
      ('tables','basic','| Place | Depth |\n|---|---|\n| North | 7 |\n| South | 12 |','The preview shows a two-column table with two data rows.'),
      ('tables','alignment','| Left alignment example | Center alignment example | Right alignment example |\n|:---|:---:|---:|\n| one | two | three |','The preview table visibly uses left, centered and right-aligned columns.'),
      ('tables','inline','| Style | Example |\n|---|---|\n| Strong | **bold** |\n| Code | `x` |','The preview table keeps strong emphasis and inline code in its cells.'),
      ('tables','escaped-pipe',r'| Place | Note |'+'\n|---|---|\n'+r'| North | A \| B |','The preview keeps A | B in a single table cell.'),
      ('tables','empty','| A | B |\n|---|---|\n| filled | |','The preview shows a table with an empty second data cell.'),
      ('tables','no-edge','A | B\n---|---\none | two','The preview renders a table without requiring leading and trailing pipes.'),
      ('tables','code-pipe','| Code | Note |\n|---|---|\n| `a\\|b` | expression |','The preview displays a pipe inside a code cell without splitting the cell.'),
      ('links','inline','Visit [the harbor](https://example.org/harbor).','The preview shows the harbor as a link.'),
      ('links','reference','Visit [the harbor][port].\n\n[port]: https://example.org/harbor "Port"','The preview resolves the named reference to a link.'),
      ('links','auto','<https://example.org/harbor>','The preview shows the address as a clickable link.'),
      ('links','linkify','Visit https://example.org/harbor today.','The preview makes the plain URL a link.'),
      ('links','email','Contact <dock@example.org>.','The preview shows the email address as a link.'),
      ('links','formatted','[**Harbor** guide](https://example.org/guide)','The preview link contains strongly emphasized Harbor.'),
      ('links','anchor','# Harbor\n\n[Jump to Harbor](#harbor)','The preview shows the heading and an internal link to it.'),
      ('links','image','![Blue badge](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAAAoCAYAAABpYH0BAAAAg0lEQVR4nO3OMQ0AIBAAsVeHfwF4AREMlyYM3Tuz9vke5AFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAdwFsMueB6QlqDwAAAAASUVORK5CYII=)','The preview displays a blue rectangular badge image.'),
      ('code','fence','```\nNorth < South\nA & B\n```','The preview displays both lines literally in a code block.'),
      ('code','javascript','```javascript\nconst tide = 7;\nconsole.log(tide);\n```','The preview displays a JavaScript code block with visible syntax highlighting.'),
      ('code','python','```python\ndef tide(level):\n    return level + 1\n```','The preview displays the Python code with indentation and syntax highlighting.'),
      ('code','html','```html\n<strong>Harbor</strong>\n```','The preview displays HTML markup literally as highlighted code.'),
      ('code','css','```css\n.harbor { color: blue; }\n```','The preview shows a highlighted CSS code block.'),
      ('code','json','```json\n{"harbor": "North", "depth": 7}\n```','The preview shows a highlighted JSON code block.'),
      ('code','indented','    North\n    South\n','The preview shows an indented code block preserving its two lines.'),
      ('code','nested-list','- Code:\n\n  ```python\n  print("Harbor")\n  ```','The preview places the code block inside the list item.'),
      ('advanced','footnote','A harbor note[^a].\n\n[^a]: Sheltered water.','The preview shows a footnote reference and its note text.'),
      ('advanced','two-footnotes','North[^n] and South[^s].\n\n[^n]: Northern port.\n[^s]: Southern port.','The preview shows two distinct numbered footnotes and their texts.'),
      ('advanced','inline-note','Harbor^[A sheltered port.]','The preview shows an inline footnote rendered as a note below.'),
      ('advanced','abbreviation','HTML describes a page.\n\n*[HTML]: Hyper Text Markup Language','The preview preserves HTML as an abbreviation with its expansion available.'),
      ('advanced','unicode','# 海岸 Café\n\n你好，海港。🌊','The preview preserves the accented, Chinese and emoji content.'),
      ('advanced','html','<details open><summary>Harbor</summary><p>Port details.</p></details>','The preview shows Harbor and Port details as readable text.'),
      ('math','inline','Area $x^2+y^2$ is known.','The preview renders the inline expression with superscripts.'),
      ('math','fraction','$$\\frac{a+b}{c+d}$$','The preview shows a displayed mathematical fraction.'),
      ('math','sqrt','$$\\sqrt{x^2+y^2}$$','The preview shows a square root over the expression.'),
      ('math','sum','$$\\sum_{i=1}^{n} i$$','The preview renders a summation with lower and upper limits.'),
      ('math','integral','$$\\int_0^1 x^2\\,dx$$','The preview renders an integral with limits and the integrand.'),
      ('math','matrix','$$\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}$$','The preview shows a two-by-two matrix with parentheses.'),
      ('math','greek','$\\alpha + \\beta = \\gamma$','The preview shows Greek alpha, beta and gamma in the formula.'),
      ('math','aligned','$$\\begin{aligned}a&=b+c\\\\d&=e+f\\end{aligned}$$','The preview shows two aligned equations.'),
      ('diagrams','flow','```mermaid\ngraph LR\nA[Start] --> B[End]\n```','The preview shows Start connected by an arrow to End.'),
      ('diagrams','decision','```mermaid\ngraph TD\nA[Start] --> B{Ready?}\nB -->|Yes| C[Go]\nB -->|No| D[Wait]\n```','The preview shows a decision with labeled Yes and No branches.'),
      ('diagrams','sequence','```mermaid\nsequenceDiagram\nAlice->>Bob: Hello\nBob-->>Alice: Reply\n```','The preview shows Alice and Bob exchanging Hello and Reply messages.'),
      ('diagrams','class','```mermaid\nclassDiagram\nBoat <|-- Sailboat\nBoat : +name\n```','The preview shows the Boat and Sailboat classes linked by inheritance.'),
      ('diagrams','state','```mermaid\nstateDiagram-v2\n[*] --> Docked\nDocked --> Sailing\nSailing --> [*]\n```','The preview shows Docked and Sailing states connected in order.'),
      ('diagrams','music','```abc\nX:1\nT:Harbor tune\nM:4/4\nL:1/4\nK:C\nCDEF|GABc|\n```','The preview shows musical staff notation for Harbor tune.'),
    ]
    grouped={}
    for family,cid,source,acceptance in rows:
        goal='Replace the document with exactly the text inside the following outer fence and leave its rendered preview visible:\n'+fenced(source)
        grouped.setdefault(family,[]).append(cp(cid,goal,acceptance,[S(source)],text='Replace this passage.',checks=[SOURCE],exact_source=source))
    return [episode('gui-render-'+family,'rendering-'+family,points) for family,points in grouped.items()]


def formatting():
    formats=[('bold','Bold – Ctrl+Shift+B','bold'),('italic','Italic – Ctrl+Shift+I','italic'),
             ('strike','Strikethrough – Ctrl+Shift+S','struck through'),('quote','Blockquote – Ctrl+Shift+Q','a block quotation'),
             ('ulist','Unordered list – Ctrl+Shift+U','a bulleted list'),('olist','Ordered list – Ctrl+Shift+O','a numbered list'),
             ('clist','Check list – Ctrl+Shift+C','a checklist'),('code','Code – Ctrl+Shift+K','code'),('heading','Heading – Ctrl+Shift+H','a heading')]
    cps=[]
    for cid,title,what in formats:
        text='Harbor' if cid not in ('ulist','olist','clist','code','quote') else 'North\nSouth'
        cps.append(cp(cid,'The document text is selected. Apply the editor’s '+what+' formatting command.',
                      'The selected content is now rendered as '+what+'.',[T(title)],text=text,selection=[0,len(text)],checks=[RENDER]))
    cps.append(cp('rule','Insert a horizontal rule after Harbor using the editor’s horizontal-rule command.','The preview shows a horizontal separator after Harbor.',[P('Control+Shift+R')],text='Harbor',selection=[6,6],checks=[RENDER]))
    second=[]
    for cid,title,what,source,sel in [
        ('unbold','Bold – Ctrl+Shift+B','strong emphasis','**Harbor**',[2,8]),
        ('unitalic','Italic – Ctrl+Shift+I','italic emphasis','*Harbor*',[1,7]),
        ('unstrike','Strikethrough – Ctrl+Shift+S','strikethrough','~~Harbor~~',[2,8]),
        ('unquote','Blockquote – Ctrl+Shift+Q','quotation','> Harbor',[2,8]),
        ('unlist','Unordered list – Ctrl+Shift+U','bulleted-list formatting','- Harbor',[2,8]),
        ('uncode','Code – Ctrl+Shift+K','inline-code formatting','`Harbor`',[1,7]),
    ]:
        second.append(cp(cid,'Harbor is selected inside '+what+'. Toggle that formatting off with its formatting command.',
                         'Harbor is rendered as ordinary text without '+what+'.',[T(title)],text=source,selection=sel,checks=[RENDER]))
    links=[cp('link','Harbor is selected. Use the link command to link it to https://example.org/harbor.',
              'Harbor is rendered as a link.',[T('Link – Ctrl+Shift+L'),F('https://example.org/harbor',label='URL'),X('Ok')],text='Harbor',selection=[0,6],checks=[RENDER]),
           cp('image','Insert an image using the image command, address https://example.org/badge.png, with the selected text Badge as its description.',
              'The source contains an image reference to the supplied address with Badge as its description.',[T('Image – Ctrl+Shift+G'),F('https://example.org/badge.png',label='URL'),X('Ok')],text='Badge',selection=[0,5],checks=[RENDER]),
           cp('table','Use the table insertion command on the selected word Harbor.','The document gains a Markdown table containing Harbor.',[T('Table – Ctrl+Shift+T')],text='Harbor',selection=[0,6],checks=[RENDER]),
           cp('bold-middle','Apply bold formatting to the selected word south.','Only south gains strong emphasis.',[T('Bold – Ctrl+Shift+B')],text='North south east',selection=[6,11],checks=[RENDER]),
           cp('italic-unicode','Apply italic formatting to the selected text 海岸.','海岸 gains italic emphasis while the surrounding text remains.',[T('Italic – Ctrl+Shift+I')],text='North 海岸 south',selection=[6,8],checks=[RENDER]),
           cp('nested-bold','The italic word Harbor is selected. Add strong emphasis with the bold command.','Harbor now has both italic and strong emphasis.',[T('Bold – Ctrl+Shift+B')],text='*Harbor*',selection=[1,7],checks=[RENDER])]
    return [episode('gui-format','formatting',cps),episode('gui-format-remove','formatting',second),episode('gui-format-insert','formatting',links)]


def editing():
    cps=[
        cp('replace-selection','Replace the selected word South with East.','The document reads North East.',[{'op':'type','value':'East'}],text='North South',selection=[6,11],checks=[SOURCE]),
        cp('insert','Insert sheltered at the caret, including a trailing space.','The document reads North sheltered harbor.',[{'op':'type','value':'sheltered '}],text='North harbor',selection=[6,6],checks=[SOURCE]),
        cp('delete-word','Delete the selected word South and the preceding space.','The document reads North.',[P('Backspace')],text='North South',selection=[5,11],checks=[SOURCE]),
        cp('split','Split NorthSouth into two lines at the caret.','North and South appear on separate lines.',[P('Enter')],text='NorthSouth',selection=[5,5],checks=[SOURCE]),
        cp('join','Join the second line to the first at the caret.','The source reads NorthSouth on one line.',[P('Backspace')],text='North\nSouth',selection=[6,6],checks=[SOURCE]),
        cp('undo','Undo the just-applied bold formatting with the undo command.','Harbor returns to ordinary text.',[T('Undo')],text='Harbor',selection=[0,6],prepare=[T('Bold – Ctrl+Shift+B')],checks=[RENDER],exact_source='Harbor'),
        cp('redo','Redo the bold formatting that was just undone.','Harbor has strong emphasis again.',[T('Redo')],text='Harbor',selection=[0,6],prepare=[T('Bold – Ctrl+Shift+B'),T('Undo')],checks=[RENDER]),
        cp('continue-bullet','Continue the list with a new item South.','The list contains North followed by South.',[P('End'),P('Enter'),{'op':'type','value':'South'}],text='- North',selection=[7,7],checks=[RENDER]),
        cp('continue-number','Continue the numbered list with a new item South.','The numbered list contains North followed by South.',[P('End'),P('Enter'),{'op':'type','value':'South'}],text='1. North',selection=[8,8],checks=[RENDER]),
        cp('indent-list','Indent the selected second list item to become a child of North.','South appears as a nested list item under North.',[P('Tab')],text='- North\n- South',selection=[8,15],checks=[RENDER]),
        cp('outdent-list','Outdent the selected South item to the same level as North.','North and South appear at the same list level.',[P('Shift+Tab')],text='- North\n\t- South',selection=[8,16],checks=[RENDER]),
    ]
    return [episode('gui-editing-'+str(i//6+1),'editing',cps[i:i+6]) for i in range(0,len(cps),6)]


def search():
    cps=[];text='Harbor north. harbor south. HARBOR east.\nPort 12, Port 24.'
    for cid,find,repl,flags,all_ in [('replace-one','Harbor','Dock',[],False),('replace-all','harbor','Dock',[],True),
        ('case-sensitive','Harbor','Dock',['Case sensitive'],True),('regex-digits',r'\d+','N',['Regular expression'],True),
        ('regex-capture',r'Port (\d+)','Dock $1',['Regular expression'],True),('literal-dot','north.','west',[],False)]:
        recipe=[P('Control+Alt+F'),F(find,tag='input',nth=1),F(repl,tag='input',nth=2)]+[T(f) for f in flags]+([] if all_ else [X('Next')])+[X('All' if all_ else 'Replace'),T('Close')]
        goal=f'Use find and replace to replace {"all occurrences" if all_ else "the first occurrence"} of `{find}` with `{repl}`'+(' using '+', '.join(flags)+'.' if flags else ' using ordinary case-insensitive text matching.')
        expected={'replace-one':'Dock north. harbor south. HARBOR east.\nPort 12, Port 24.','replace-all':'Dock north. Dock south. Dock east.\nPort 12, Port 24.','case-sensitive':'Dock north. harbor south. HARBOR east.\nPort 12, Port 24.','regex-digits':'Harbor north. harbor south. HARBOR east.\nPort N, Port N.','regex-capture':'Harbor north. harbor south. HARBOR east.\nDock 12, Dock 24.','literal-dot':'Harbor west harbor south. HARBOR east.\nPort 12, Port 24.'}[cid]
        cps.append(cp(cid,goal,'The requested replacement is visible in the document.',recipe,text=text,checks=[SOURCE],exact_source=expected))
    for cid,term,flags in [('find','Harbor',[]),('case','Harbor',['Case sensitive']),('regexp',r'Port \d+',['Regular expression'])]:
        cps.append(cp(cid,'Find '+repr(term)+(' using '+', '.join(flags) if flags else '')+' and leave the matching results visible.',
                      'The search interface identifies matching occurrences in the document.',[P('Control+F'),F(term,tag='input',nth=1)]+[T(f) for f in flags],text=text))
    return [episode('gui-replace','search',cps[:6]),episode('gui-find','search',cps[6:])]


def layout():
    doc='# Harbor\n\nA **bold** word.\n\n## North\n\nNotes.'
    cps=[
      cp('reader','Switch to reader mode.','The rendered document occupies the reading view and the source editor is hidden.',[T('Reader mode')],text=doc),
      cp('editor','Hide the side preview.','The source editor remains visible and the rendered side preview is hidden.',[T('Toggle side preview')],text=doc),
      cp('restore-preview','Restore the side preview from the prepared editor-only view.','Both source and rendered preview are visible.',[T('Toggle side preview')],text=doc,prepare=[T('Toggle side preview')]),
      cp('hide-navigation','Hide the navigation bar.','The document remains visible with the main navigation bar hidden.',[T('Toggle navigation bar')],text=doc),
      cp('restore-navigation','Show the navigation bar again.','The main navigation and formatting controls are visible.',[T('Toggle navigation bar')],text=doc,prepare=[T('Toggle navigation bar')]),
      cp('show-explorer','Show the file explorer.','The current document is listed in the workspace tree.',[T('Toggle explorer')],text=doc),
      cp('close-explorer','Close the file explorer.','The document editing view expands after the explorer closes.',[T('Close explorer')],text=doc,prepare=[T('Toggle explorer')]),
      cp('toc','Open the table of contents.','Harbor and North appear as navigable headings in the contents panel.',[M('Table of contents')],text=doc),
      cp('cheatsheet','Open the Markdown cheat sheet.','The application displays its Markdown syntax reference.',[M('Markdown cheat sheet')],text=doc),
      cp('status','Show the status bar after it was hidden.','Document word or character statistics are visible.',[T('Toggle status bar')],text=doc,prepare=[T('Toggle status bar')]),
    ]
    return [episode('gui-layout-'+str(i//5+1),'view',cps[i:i+5]) for i in range(0,len(cps),5)]


def properties():
    cps=[]
    metadata=[('title','Title','Tide report'),('author','Author','Ada Lovelace'),('tags','Tags — comma-separated','harbor, tide'),
              ('categories','Categories — comma-separated','travel, sea'),('excerpt','Excerpt','A short harbor report.'),('image','Featured image','https://example.org/tide.png')]
    for cid,label,value in metadata:
        cps.append(cp(cid,f'Set the file metadata {label.split(" —")[0]} to `{value}`, save it, and reopen file properties.',
                      f'The reopened metadata shows {value}.',[M('File properties'),F(value,label=label),P('Enter'),M('File properties')]+([{'op':'wheel','x':820,'y':690,'delta_y':400}] if cid=='image' else [])))
    for preset in ['commonmark','gfm','zero']:
        cps.append(cp('preset-'+preset,'Set the file’s Markdown preset to '+preset+' and leave the preview visible.',
            'The rendered document follows the selected preset, as shown by the reference.',[M('File properties'),{'op':'select','target':{'label':'Preset'},'value':preset},{'do':'modal-ok'},T('Close side bar')],
            text='# Preset\n\n**bold** ~~deleted~~ ==marked== :smile:\n\n- [x] Task\n\n| A | B |\n|---|---|\n| 1 | 2 |'))
    extensions=[('breaks','One line\nSecond line'),('table','| A | B |\n|---|---|\n| 1 | 2 |'),('mark','==highlighted=='),('sub','H~2~O'),('sup','x^2^'),('footnote','Note[^a]\n\n[^a]: Explanation.'),('deflist','Harbor\n: Port'),('abbr','HTML\n\n*[HTML]: Hyper Text Markup Language'),('linkify','https://example.org'),('typographer','"Harbor" -- ...'),('tasklist','- [x] Done'),('fence','```js\nconst n = 1;\n```')]
    opts=[]
    for ext,source in extensions:
        yaml=f'extensions:\n  markdown:\n    {ext}: false\n'
        opts.append(cp(ext,'In file properties, use this YAML to disable the '+ext+' extension, then close the settings panels:\n```yaml\n'+yaml+'```',
                       'The preview changes according to the disabled extension.',[M('File properties'),X('YAML properties'),C(yaml),{'do':'modal-ok'},T('Close side bar')],text=source))
    opts += [cp('emoji-shortcuts','Enable emoji shortcuts with these file properties:\n```yaml\nextensions:\n  emoji:\n    shortcuts: true\n```',
                'The preview converts the typed emoticons to emoji.',[M('File properties'),X('YAML properties'),C('extensions:\n  emoji:\n    shortcuts: true\n'),{'do':'modal-ok'},T('Close side bar')],text=':) :-( ;-) :D'),
             cp('invalid-yaml','Enter `title: [unfinished` in YAML file properties and attempt to save.',
                'A YAML parsing error is visibly reported and the invalid properties are not accepted.',[M('File properties'),X('YAML properties'),C('title: [unfinished'),{'do':'modal-ok'}])]
    return [episode('gui-metadata','file-properties',cps[:6]),episode('gui-presets','file-properties',cps[6:])]+[episode('gui-properties-'+str(i//7+1),'file-properties',opts[i:i+7]) for i in range(0,len(opts),7)]


def settings():
    cps=[]
    rows=[('dark','colorTheme: dark','The application uses a dark theme.'),('font-large','fontSizeFactor: 1.5','Editor and preview text are visibly enlarged.'),
          ('width','maxWidthFactor: 0.3','The editor and preview use a narrower text measure.'),('monospace','editor:\n  monospacedFontOnly: true','The source editor uses a monospaced face.'),
          ('inline-images','editor:\n  inlineImages: false','The source editor displays image syntax rather than an inline picture; the preview still shows the image.')]
    for cid,yaml,acceptance in rows:
        text='# Harbor\n\nA **bold** paragraph with several words. This longer passage describes a sheltered harbor, its northern pier, the boats at anchor and the tide coming in across the bay.'
        if cid=='inline-images':text='![Badge](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAAAoCAYAAABpYH0BAAAAg0lEQVR4nO3OMQ0AIBAAsVeHfwF4AREMlyYM3Tuz9vke5AFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAV0e0OUBXR7Q5QFdHtDlAdwFsMueB6QlqDwAAAAASUVORK5CYII=)'
        cps.append(cp(cid,'Apply these custom application settings and close the panels'+(' and reload the application' if cid=='inline-images' else '')+':\n```yaml\n'+yaml+'\n```',acceptance,[M('Settings'),C(yaml),X('Ok'),T('Close side bar')]+([{'op':'reload'}] if cid=='inline-images' else []),text=text))
    cps += [cp('persistent-dark','Set the application theme to dark, then reload.','The dark theme remains after the reload.',[M('Settings'),C('colorTheme: dark'),X('Ok'),{'op':'reload'}]),
            cp('new-content','Set the default new-file content to `# New note`, then create a file named Draft.','Draft starts with the heading New note.',[M('Settings'),C('newFileContent: "# New note"'),X('Ok'),T('Close side bar'),{'do':'new-file','name':'Draft'}]),
            cp('shortcut','Set the bold shortcut to Alt+B, then use it on the selected word Harbor.','Harbor gains strong emphasis from the configured shortcut.',[M('Settings'),C('shortcuts:\n  alt+b: bold'),X('Ok'),T('Close side bar'),{'do':'selection','start':0,'end':6},P('Alt+b')],text='Harbor',checks=[RENDER]),
            cp('invalid','Enter invalid YAML `editor: [unfinished` as custom settings and attempt to save.','The application visibly reports the invalid settings.',[M('Settings'),C('editor: [unfinished'),X('Ok')]),
            cp('defaults','Open the default-settings reference in settings.','The application shows its default settings and shortcut definitions.',[M('Settings'),X('Default settings')])]
    return [episode('gui-settings-'+str(i//5+1),'settings',cps[i:i+5]) for i in range(0,len(cps),5)]


def files():
    cps=[cp('create','Create a new file named Tide notes.','Tide notes appears as the current file in the workspace.',[{'do':'new-file','name':'Tide notes'}]),
         cp('rename','Rename the current file to Harbor report.','Harbor report is the current document name.',[R('Harbor report')]),
         cp('unicode-name','Rename the current file to 海岸 Café.','The document name preserves 海岸 Café.',[R('海岸 Café')]),
         cp('switch','Switch back to the prepared file First note.','The file First note is current and its First text content is visible.',[X('First note')],prepare=[R('First note'),S('First text'),{'do':'new-file','name':'Second note'},S('Second text')]),
         cp('delete','Delete the current file Tide notes.','Tide notes is removed from the active file list and is recoverable in Trash.',[T('Delete'),X('Trash')],prepare=[{'do':'new-file','name':'Tide notes'},S('Save this tide note')]),
         cp('recover','Move the prepared Tide notes file from Trash back to the main workspace.','Tide notes is restored in the workspace with its content.',[{'do':'drag-text','text':'Tide notes','to':'Welcome file'},X('Tide notes')],prepare=[{'do':'new-file','name':'Tide notes'},S('Recover this text'),T('Delete'),X('Trash')]),
         cp('folder','Create a folder named Reports.','Reports appears in the explorer.',[{'do':'new-folder','name':'Reports'}]),
         cp('rename-folder','Rename the prepared Reports folder to Archives.','Archives replaces Reports in the explorer.',[X('Reports'),T('Rename'),F('Archives',tag='input',nth=0),P('Enter')],prepare=[{'do':'new-folder','name':'Reports'}]),
         cp('nested-file','Create a file named Tide inside the prepared Reports folder.','Reports contains Tide.',[X('Reports'),{'do':'new-file','name':'Tide'}],prepare=[{'do':'new-folder','name':'Reports'}]),
         cp('nested-folder','Create a folder named Spring inside the prepared Reports folder.','Reports contains Spring as a nested folder.',[X('Reports'),{'do':'new-folder','name':'Spring'}],prepare=[{'do':'new-folder','name':'Reports'}]),
         cp('move-file','Move the prepared Tide file into Reports.','Tide is shown inside Reports.',[{'do':'drag-text','text':'Tide','to':'Reports'},{'do':'tree-child','parent':'Reports','child':'Tide'}],prepare=[{'do':'new-folder','name':'Reports'},X('Welcome file'),{'do':'new-file','name':'Tide'}]),
         cp('remove-folder','Delete the prepared Reports folder and its nested Tide file.','Reports and its child Tide are removed from the active workspace.',[X('Reports'),T('Delete'),X('Yes, delete')],prepare=[{'do':'new-folder','name':'Reports'},X('Reports'),{'do':'new-file','name':'Tide'}]),
         cp('persist-content','Replace the document with `Persistent harbor note`, then reload.','The exact text survives the reload.',[S('Persistent harbor note'),W(),{'op':'reload'}],checks=[SOURCE]),
         cp('persist-name','Rename the file to Tide diary, then reload.','Tide diary remains the document name.',[R('Tide diary'),W(),{'op':'reload'}]),
         cp('persist-folder','Create a Reports folder and reload the application.','Reports is still in the explorer after the reload.',[{'do':'new-folder','name':'Reports'},W(),{'op':'reload'}]),
         cp('duplicate-name','Create two separate files named Tide.','The explorer contains two distinct files named Tide.',[{'do':'new-file','name':'Tide'},{'do':'new-file','name':'Tide'}]),
    ]
    return [episode('gui-files-'+str(i//4+1),'workspace',cps[i:i+4]) for i in range(0,len(cps),4)]


def exports():
    doc='# Harbor\n\nA **bold** note.\n\n## Tide\n\n- North\n- South'
    cps=[cp('markdown','Export the current document as Markdown.','A Markdown document is downloaded.',[M('Import/export'),X('Export as Markdown'),{'do':'download','suffix':'.md'}],text=doc,checks=[{'type':'download','suffix':'.md'}])]
    for template in ['plainText','plainHtml','styledHtml','styledHtmlWithToc','jekyllSite']:
        labels={'plainText':'Plain text','plainHtml':'Plain HTML','styledHtml':'Styled HTML','styledHtmlWithToc':'Styled HTML with TOC','jekyllSite':'Jekyll site'}
        props='title: Harbor report\nauthor: Ada\ntags: [harbor, tide]\nstatus: draft\n'
        prefix=[M('File properties'),X('YAML properties'),C(props),{'do':'modal-ok'}] if template=='jekyllSite' else []
        goal=('Set file properties to:\n'+fenced(props,'yaml')+'\nThen ' if prefix else '')+'Export the document as HTML using the '+labels[template]+' template.'
        cps.append(cp(template,goal,'An export is downloaded using the chosen template.',prefix+[M('Import/export'),X('Export as HTML'),{'op':'select','target':{'label':'Template'},'value':template},X('Ok'),{'do':'download','suffix':'.html'}],text=doc,checks=[{'type':'download','suffix':'.html','format':template}]))
    cps.append(cp('named','Rename the document to Tide report and export it as Markdown.','The download is named for Tide report.',[R('Tide report'),M('Import/export'),X('Export as Markdown'),{'do':'download','suffix':'.md'}],text=doc,checks=[{'type':'download','suffix':'.md','name':True}]))
    return [episode('gui-exports','exports',cps)]


def imports():
    names=['harbor.md','unicode.md','frontmatter.md','lists.md','code.md','empty.md']
    cps=[]
    for name in names:
        cps.append(cp(name[:-3],'Import '+name+' from the supplied inputs as Markdown.','A new document shows the imported file’s content.',[M('Import/export'),X('Import Markdown'),{'do':'upload','file':name},T('Close side bar')],checks=[SOURCE]))
    html=['paragraphs.html','formatting.html','table.html','list.html','code.html','links.html']
    for name in html:
        cps.append(cp(name[:-5]+'-html','Import '+name+' from the supplied inputs as HTML.','The imported HTML becomes an editable Markdown document with corresponding content.',[M('Import/export'),X('Import HTML'),{'do':'upload','file':name,'mime':'text/html'},T('Close side bar')],checks=[RENDER]))
    return [episode('gui-import-markdown','imports',cps[:6],names),episode('gui-import-html','imports',cps[6:],html)]


def management():
    start=[M('Templates'),T('New template'),F('Harbor template',label='Template'),P('Enter')]
    temps=[
      cp('create','Create and save a custom template named Harbor template, then reopen the template list.',
         'Harbor template is available in the template list.',start+[{'do':'modal-ok'},M('Templates')]),
      cp('rename','Rename the prepared Harbor template to Tide template and save it.',
         'Tide template replaces Harbor template in the list.',[T('Rename template'),F('Tide template',label='Template'),P('Enter'),{'do':'modal-ok'},M('Templates'),{'op':'select','target':{'label':'Template'},'value':'Tide template'}],prepare=start),
      cp('copy','Make a copy of the Plain HTML built-in template named Harbor copy and save it.',
         'Harbor copy is available alongside the built-in templates.',[M('Templates'),{'op':'select','target':{'label':'Template'},'value':'plainHtml'},T('Copy template'),F('Harbor copy',label='Template'),P('Enter'),{'do':'modal-ok'},M('Templates')]),
      cp('edit','Replace the prepared Harbor template body with `<h1>{{files.0.name}}</h1>` and save it, then reopen it.',
         'The saved template body contains the supplied heading template.',[C('<h1>{{files.0.name}}</h1>'),{'do':'modal-ok'},M('Templates'),{'op':'select','target':{'label':'Template'},'value':'Harbor template'}],prepare=start),
      cp('remove','Remove the prepared Harbor template and save the template list.',
         'Harbor template is absent while built-in templates remain.',[T('Remove template'),{'do':'modal-ok'},M('Templates')],prepare=start),
      cp('persist','Save the prepared Harbor template, reload the application, and reopen templates.',
         'Harbor template survives the reload.',[{'do':'modal-ok'},{'op':'reload'},M('Templates'),{'op':'select','target':{'label':'Template'},'value':'Harbor template'}],prepare=start),
    ]
    ws=[M('Workspaces'),{'do':'text-contains','value':'Manage workspaces'}]
    work=[cp('rename','Rename the local Main workspace to Harbor workspace.',
             'The workspace list shows Harbor workspace.',ws+[T('Edit name'),F('Harbor workspace',tag='input',nth=1),P('Enter')]),
          cp('persist-name','Rename the local workspace to Tide workspace, reload, then reopen the workspace list.',
             'The name Tide workspace persists.',ws+[T('Edit name'),F('Tide workspace',tag='input',nth=1),P('Enter'),X('Close'),{'op':'reload'}]+ws),
          cp('cannot-remove-main','Rename the local main workspace to Protected harbor, attempt to remove it, and verify it remains usable by replacing the document with `Still editable.`. Leave the workspace list open.',
             'Protected harbor remains in the workspace list after the removal attempt, and the document contains Still editable.',ws+[T('Edit name'),F('Protected harbor',tag='input',nth=1),P('Enter'),T('Remove'),{'op':'wait','seconds':3},{'op':'wait','seconds':3},X('Close'),T('Close side bar'),S('Still editable.')]+ws,checks=[SOURCE],exact_source='Still editable.')]
    backups=[cp('export','Rename the current document to Harbor and export a workspace backup.',
                'A workspace backup file is downloaded.',[R('Harbor'),W(),M('Workspace backups'),X('Export workspace backup'),{'do':'download','suffix':'.json'}],text='Backup this harbor note.',checks=[{'type':'backup'}],carry_download='roundtrip-backup.json'),
             cp('roundtrip','Import roundtrip-backup.json, the unchanged backup exported in the preceding checkpoint, into this fresh workspace. Open the restored Harbor document.',
                'Harbor is restored with its Backup this harbor note. content.',[M('Workspace backups'),X('Import workspace backup'),{'do':'upload','file':'roundtrip-backup.json'},T('Close side bar'),T('Toggle explorer'),X('Harbor')],checks=[SOURCE],depends_on=['export']),
             cp('legacy-backup','Import legacy-backup.json as a workspace backup and open Legacy note.',
                'Legacy note appears with its imported heading and paragraph.',[M('Workspace backups'),X('Import workspace backup'),{'do':'upload','file':'legacy-backup.json'},T('Close side bar'),T('Toggle explorer'),X('Legacy note')],checks=[SOURCE])]
    return [episode('gui-templates','templates',temps),episode('gui-workspaces','workspace',work),episode('gui-backups','backup',backups,['legacy-backup.json'])]


def information_and_search_navigation():
    return [episode('gui-search-navigation','search',[
      cp('next','Find the word harbor, then move to the next occurrence.',
         'The next occurrence is selected and the search position advances.',[P('Control+F'),F('harbor',tag='input',nth=1),X('Next')],text='harbor north\nharbor south\nharbor east'),
      cp('previous','Find the word harbor, move forward once, then move back to the preceding occurrence.',
         'The previous occurrence becomes selected.',[P('Control+F'),F('harbor',tag='input',nth=1),X('Next'),X('Previous')],text='harbor north\nharbor south\nharbor east'),
    ]),episode('gui-help','help',[
      cp('badges','Open the application feature badges.',
         'The application shows the feature families and the available badges.',[M('Badges')]),
      cp('about','Open the application’s About dialog.',
         'The application identifies StackEdit and provides product information.',[M('About StackEdit')]),
    ])]


def promote_preparations(episodes):
    # GUI-created preconditions are separately scored user goals. The next
    # point continues that state, so an equivalent candidate chooses its own
    # controls and reference before/after still show a meaningful transition.
    preparations={
      'gui-editing-1/undo':('Apply bold formatting to the selected Harbor text.','Harbor has strong emphasis.'),
      'gui-editing-2/redo':('Apply bold formatting to the selected Harbor text.','Harbor has strong emphasis.'),
      'gui-layout-1/restore-preview':('Hide the side preview.','The source remains visible with the side preview hidden.'),
      'gui-layout-1/restore-navigation':('Hide the navigation bar.','The document is visible without the main navigation bar.'),
      'gui-layout-2/close-explorer':('Open the file explorer.','The explorer lists the current document.'),
      'gui-layout-2/status':('Hide the status bar.','The document remains visible with its status bar hidden.'),
      'gui-files-1/switch':('Rename the current file First note and replace its source with `First text`. Create Second note with source `Second text` and leave it open.','First note and Second note are listed, and Second note is current with Second text.'),
      'gui-files-2/delete':('Create Tide notes with source `Save this tide note`.','Tide notes is in the workspace with Save this tide note.'),
      'gui-files-2/recover':('Create Tide notes with source `Recover this text`, then delete it and open Trash.','Trash contains Tide notes, ready for recovery.'),
      'gui-files-2/rename-folder':('Create a folder Reports.','Reports is visible in the workspace.'),
      'gui-files-3/nested-file':('Create a folder Reports.','Reports is visible in the workspace.'),
      'gui-files-3/nested-folder':('Create a folder Reports.','Reports is visible in the workspace.'),
      'gui-files-3/move-file':('Create a root folder Reports and a separate root file Tide.','The workspace shows Reports and Tide at the root.'),
      'gui-files-3/remove-folder':('Create a folder Reports containing a file Tide, and leave Reports expanded.','Reports visibly contains Tide.'),
    }
    for wid in ['rename','edit','remove','persist']:
        preparations['gui-templates/'+wid]=('Start a new custom template named Harbor template and leave it open for editing.','Harbor template is selected and its body is editable.')
    for w in episodes:
        expanded=[]
        def point(cid,goal,acceptance,recipe,**kwargs):
            return dict(id=cid,goal=goal,recipe=recipe,assertions=[{'id':w['id']+'/'+cid+'/visible','channel':'frontend','method':'agent','requirement':acceptance}],**kwargs)
        for c in w['checkpoints']:
            preparation=c.pop('prepare',[])
            if preparation:
                goal,acceptance=preparations[w['id']+'/'+c['id']]
                prior=c['id']+'-start'
                is_redo=w['id']=='gui-editing-2' and c['id']=='redo'
                expanded.append(point(prior,goal,acceptance,preparation[:1] if is_redo else preparation,text=c['text'],selection=c['selection']))
                if is_redo:
                    expanded.append(point('redo-undo','Continue the preceding document: undo its bold formatting.','Harbor returns to ordinary text.',[T('Undo')],continues=True,depends_on=[prior]))
                    prior='redo-undo'
                c['goal']='Continue the preceding checkpoint. '+c['goal']
                c['continues']=True;c['depends_on']=[prior]
            expanded.append(c)
        w['checkpoints']=expanded
        n=len(expanded)
        w['budget']={'calls':min(400,40+35*n),'tokens':min(8000000,600000+600000*n),'seconds':400+300*n}
        if w['id']=='gui-backups':w['budget'].update(calls=250,tokens=4000000)
        if w['id']=='gui-render-diagrams':w['budget']['seconds']=7200
        w['session']='Each checkpoint starts from fresh stated source unless its goal explicitly continues the preceding checkpoint. In a continuing goal, keep the preceding application state. Use any visible route that achieves the functional result; formatting commands must be used when requested. Input files include any explicitly carried download from a preceding goal.'
    return episodes


def build():
    return promote_preparations(rendering()+formatting()+editing()+search()+layout()+properties()+settings()+files()+exports()+imports()+management()+information_and_search_navigation())

'''Program episodes: HTTP status codes, keycode info and PDF signature checker.'''
from pbuild import bind, case, click, fields, fill, lines, multi, outs, point, press, upload, wait, episode

DEFAULT = 'Open the page without typing.'
FILES = {'files': ['memo.txt', 'sheet.pdf', 'tile.png']}


# -- HTTP status codes ----------------------------------------------------------------------------------
HTTP_PAGE = '/http-status-codes'
SEARCH = 'Search http status...'
HTTP_SEEN = multi(input=fields(SEARCH), list=lines(skip=2))


def http_status_codes():
    def find(cid, goal, steps, requirement):
        return case(cid, goal, HTTP_PAGE, steps, [point('list', requirement, HTTP_SEEN)])

    shown = 'Only the status codes that match the search are listed, under a Search results heading.'
    cases = [find('default', DEFAULT, [], 'The page opens with every status code listed under its category.')]
    queries = (
        ('code-404', 'Type 404.', '404'), ('code-200', 'Type 200.', '200'), ('code-418', 'Type 418.', '418'),
        ('code-first-digit', 'Type 5.', '5'), ('code-prefix', 'Type 30.', '30'),
        ('name-teapot', 'Type teapot.', 'teapot'), ('name-not-found', 'Type not found.', 'not found'),
        ('name-continue', 'Type Continue.', 'Continue'), ('name-ok-upper', 'Type OK in capital letters.', 'OK'),
        ('name-lowercase', 'Type forbidden in lower case.', 'forbidden'),
        ('description', 'Type redirect.', 'redirect'), ('description-proxy', 'Type proxy.', 'proxy'),
        ('webdav', 'Type webdav.', 'webdav'), ('category-client', 'Type client error.', 'client error'),
        ('category-success', 'Type 2xx success.', '2xx success'), ('category-1xx', 'Type 1xx.', '1xx'),
        ('gateway', 'Type gateway.', 'gateway'), ('too-many', 'Type too many.', 'too many'),
        ('spaces', 'Type 404 with spaces around it.', '  404  '),
        ('typo', 'Type the misspelled word forbiden.', 'forbiden'),
        ('unicode', 'Type a word with a non-Latin letter.', 'caf' + chr(233)),
    )
    for cid, goal, query in queries:
        cases.append(find(cid, goal, [fill(query, placeholder=SEARCH)], shown))
    cases.append(find('no-match', 'Type a search that matches nothing.', [fill('zzzzqqqq', placeholder=SEARCH)], 'A search with no match lists no status code.'))
    cases.append(find('cleared', 'Type 404 and then clear the search.', [fill('404', placeholder=SEARCH), fill('', placeholder=SEARCH)], 'Clearing the search lists every status code again.'))
    return episode('http-status-codes', 'reference', bind(cases, {'no-match': 'code-404/list', 'cleared': 'code-404/list'}))


# -- Keycode info ---------------------------------------------------------------------------------------
KEY_PAGE = '/keycode-info'
KEY_SEEN = multi(info=outs(labels=True, allow_empty=True), text=lines(skip=2))


def keycode_info():
    def pressed(cid, goal, keys, requirement):
        return case(cid, goal, KEY_PAGE, [press(k) for k in keys], [point('info', requirement, KEY_SEEN)])

    shown = 'The key, keycode, code, location and modifiers of the pressed key are shown.'
    cases = [case('default', DEFAULT, KEY_PAGE, [], [point('info', 'The page asks for a key press and shows no key information.', KEY_SEEN)])]
    rows = (
        ('letter', 'Press a.', ['a']), ('capital', 'Press Shift and A together.', ['Shift+A']), ('digit', 'Press 5.', ['5']),
        ('enter', 'Press Enter.', ['Enter']), ('escape', 'Press Escape.', ['Escape']), ('space', 'Press the space bar.', ['Space']),
        ('tab', 'Press Tab.', ['Tab']), ('backspace', 'Press Backspace.', ['Backspace']), ('delete', 'Press Delete.', ['Delete']),
        ('arrow-up', 'Press the up arrow.', ['ArrowUp']), ('arrow-left', 'Press the left arrow.', ['ArrowLeft']),
        ('home', 'Press Home.', ['Home']), ('page-down', 'Press Page Down.', ['PageDown']), ('f2', 'Press F2.', ['F2']),
        ('shift-left', 'Press the left Shift key.', ['ShiftLeft']), ('shift-right', 'Press the right Shift key.', ['ShiftRight']),
        ('control', 'Press Control.', ['Control']), ('alt', 'Press Alt.', ['Alt']), ('meta', 'Press Meta.', ['Meta']),
        ('ctrl-a', 'Press Control and a together.', ['Control+a']), ('alt-x', 'Press Alt and x together.', ['Alt+x']),
        ('shift-tab', 'Press Shift and Tab together.', ['Shift+Tab']), ('ctrl-shift-a', 'Press Control, Shift and a together.', ['Control+Shift+a']),
        ('numpad-5', 'Press 5 on the number pad.', ['Numpad5']), ('numpad-enter', 'Press Enter on the number pad.', ['NumpadEnter']),
        ('minus', 'Press the minus key.', ['Minus']), ('comma', 'Press the comma key.', [',']), ('semicolon', 'Press the semicolon key.', [';']),
        ('backquote', 'Press the backquote key.', ['Backquote']), ('two-keys', 'Press a and then b.', ['a', 'b']),
        ('same-key', 'Press z three times.', ['z', 'z', 'z']),
    )
    for cid, goal, keys in rows:
        cases.append(pressed(cid, goal, keys, shown))
    return episode('keycode-info', 'reference', cases)


# -- PDF signature checker ------------------------------------------------------------------------------
PDF_PAGE = '/pdf-signature-checker'
DROP = 'Drag and drop a PDF file here, or click to select a file or Browse files'
PDF_SEEN = multi(text=lines(skip=2))


def pdf_signature_checker():
    def chosen(cid, goal, picks, requirement):
        steps = []
        for name, mime in picks:
            steps += [click(DROP), upload(name, mime), wait(1.0)]
        return case(cid, goal, PDF_PAGE, steps, [point('result', requirement, PDF_SEEN)])

    cases = [
        case('default', DEFAULT, PDF_PAGE, [], [point('result', 'The page opens with the upload area and no file.', PDF_SEEN)]),
        chosen('unsigned', 'Choose the document sheet.pdf.', [('sheet.pdf', 'application/pdf')], 'A PDF without a signature shows its name and size and says no signature was found.'),
        chosen('text-file', 'Choose the text file memo.txt.', [('memo.txt', 'text/plain')], 'A file that is not a PDF shows its name and size and says no signature was found.'),
        chosen('image', 'Choose the image tile.png.', [('tile.png', 'image/png')], 'An image shows its name and size and says no signature was found.'),
        chosen('no-type', 'Choose sheet.pdf with no known type.', [('sheet.pdf', 'application/octet-stream')], 'A PDF with no known type is checked the same way.'),
        chosen('two-files', 'Choose sheet.pdf and then memo.txt.', [('sheet.pdf', 'application/pdf'), ('memo.txt', 'text/plain')], 'The file chosen last replaces the one chosen before.'),
    ]
    wf = episode('pdf-signature-checker', 'checker', cases)
    wf['inputs'] = dict(FILES)
    return wf


def build():
    return [http_status_codes(), keycode_info(), pdf_signature_checker()]

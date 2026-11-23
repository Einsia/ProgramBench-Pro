'''Program episodes: the shell around the tools: home page, favourites, menu, command palette, language and About.'''
from pbuild import address, cards, case, choose, click, controls, fields, lines, menu, multi, point, press, reload, typed, wait, episode

DEFAULT = 'Open the page without typing.'
HOME = '/'
ENGLISH = 'English'
CATEGORIES = (('crypto', 'Crypto'), ('converter', 'Converter'), ('web', 'Web'), ('images', 'Images & Videos'), ('development', 'Development'),
              ('network', 'Network'), ('math', 'Math'), ('measurement', 'Measurement'), ('text', 'Text'), ('data', 'Data'))


def fav(name):
    '''The favourite button that follows the first card whose link starts with the tool name.'''
    return {'op': 'click-after', 'link': name, 'tag': 'button'}


# -- Home page and favourites ---------------------------------------------------------------------------
def home_favourites():
    seen = multi(headings=lines(partial=True), cards=cards(), menu=menu())

    def one(cid, goal, steps, requirement, requires=()):
        return case(cid, goal, HOME, steps, [point('home', requirement, seen, requires)])

    added = 'The tools appear in a favourites section of the home page and as the first category of the menu.'
    gone = 'A favourite whose button is pressed again leaves the favourites and an empty section goes away.'
    kept = 'The favourites are still there after reloading the page.'
    base = ['add-one/home']
    return episode('home-favourites', 'shell', [
        one('default', DEFAULT, [], 'The home page lists every tool and shows no favourites section.'),
        one('add-one', 'Add Hash text to the favourites with the button of its card.', [fav('Hash text')], added),
        one('add-other', 'Add Bcrypt to the favourites with the button of its card.', [fav('Bcrypt')], added),
        one('add-two', 'Add Hash text and then Bcrypt to the favourites.', [fav('Hash text'), fav('Bcrypt')], added),
        one('add-two-reversed', 'Add Bcrypt and then Hash text to the favourites.', [fav('Bcrypt'), fav('Hash text')], 'The favourites are listed in the order they were added.'),
        one('add-three', 'Add Hash text, Bcrypt and UUIDs generator to the favourites.', [fav('Hash text'), fav('Bcrypt'), fav('UUIDs generator')], added),
        one('add-slash-name', 'Add Encrypt / decrypt text to the favourites.', [fav('Encrypt / decrypt text')], added),
        one('add-remove', 'Add Hash text to the favourites and press the button of its favourite card again.', [fav('Hash text'), fav('Hash text')], gone, base),
        one('remove-one-of-two', 'Add Hash text and Bcrypt, then press the button of the first favourite card.', [fav('Hash text'), fav('Bcrypt'), fav('Hash text')], gone, base),
        one('remove-both', 'Add Hash text and Bcrypt, then remove both from the favourites.', [fav('Hash text'), fav('Bcrypt'), fav('Hash text'), fav('Bcrypt')], gone, base),
        one('add-again', 'Add Hash text, remove it and add it again.', [fav('Hash text'), fav('Hash text'), fav('Hash text')], added, base),
        one('stored-one', 'Add Hash text to the favourites and reload the page.', [fav('Hash text'), reload()], kept, base),
        one('stored-two', 'Add Hash text and Bcrypt to the favourites and reload the page.', [fav('Hash text'), fav('Bcrypt'), reload()], kept, base),
        one('stored-removed', 'Add Hash text, remove it and reload the page.', [fav('Hash text'), fav('Hash text'), reload()], 'A removed favourite stays removed after reloading the page.', base),
    ])


# -- Menu categories ------------------------------------------------------------------------------------
def menu_categories():
    seen = multi(menu=menu())

    def one(cid, goal, steps, requirement, requires=()):
        return case(cid, goal, HOME, steps, [point('menu', requirement, seen, requires)])

    hidden = 'The tools of the category disappear from the menu and the other categories stay.'
    cases = [one('default', DEFAULT, [], 'The menu lists every category with all of its tools.')]
    for cid, name in CATEGORIES:
        cases.append(one('collapse-' + cid, 'Collapse the %s category of the menu.' % name, [click(name)], hidden))
    cases += [
        one('expand-again', 'Collapse the Crypto category and open it again.', [click('Crypto'), click('Crypto')], 'Opening a collapsed category lists its tools again.', ['collapse-crypto/menu']),
        one('collapse-two', 'Collapse the Crypto and Web categories.', [click('Crypto'), click('Web')], hidden),
        one('collapse-three', 'Collapse the Crypto, Web and Text categories.', [click('Crypto'), click('Web'), click('Text')], hidden),
        one('collapse-one-expand-other', 'Collapse Crypto and Web and open Crypto again.', [click('Crypto'), click('Web'), click('Crypto')], 'Only the category that is still collapsed hides its tools.', ['collapse-two/menu']),
        one('stored-collapsed', 'Collapse the Crypto category and reload the page.', [click('Crypto'), reload()], 'A collapsed category stays collapsed after reloading the page.', ['collapse-crypto/menu']),
        one('stored-two', 'Collapse the Crypto and Data categories and reload the page.', [click('Crypto'), click('Data'), reload()], 'Collapsed categories stay collapsed after reloading the page.', ['collapse-crypto/menu']),
        one('stored-expanded', 'Collapse Crypto, open it again and reload the page.', [click('Crypto'), click('Crypto'), reload()], 'An opened category stays open after reloading the page.', ['collapse-crypto/menu']),
    ]
    return episode('menu-categories', 'shell', cases)


# -- Command palette ------------------------------------------------------------------------------------
OPEN = [press('Control+k'), wait(0.5)]


def find(text, extra=()):
    return OPEN + [typed(text), wait(0.5)] + list(extra)


def command_palette():
    seen = multi(page=address(), options=controls(area='any', role='option'))

    def one(cid, goal, steps, requirement, requires=(), page=HOME, search=False):
        observed = multi(page=address(), options=controls(area='any', role='option'),
                         search=fields('Type to search a tool or a command...')) if search else seen
        return case(cid, goal, page, steps, [point('palette', requirement, observed, requires)])

    listed = 'The palette lists the tools and commands that match, grouped by category.'
    go = [press('Enter'), wait(0.8)]
    cases = [one('open', 'Press Control and K.', OPEN, 'The palette opens with an empty search field.', search=True)]
    for cid, query in (('hash', 'hash'), ('base64', 'base64'), ('uuid', 'uuid'), ('json', 'json'), ('color', 'color'), ('dark', 'dark'), ('random', 'random'),
                       ('about', 'about'), ('github', 'github'), ('bug', 'bug'), ('uppercase', 'HASH'), ('typo', 'hsh'), ('description', 'password')):
        cases.append(one('search-' + cid, 'Open the palette and type %s.' % query, find(query), listed,
                         ['search-hash/palette'] if cid == 'typo' else (), search=cid == 'typo'))
    for cid, query in (('text', 'text'), ('generator', 'generator'), ('converter', 'converter')):
        cases.append(one('cap-' + cid, 'Open the palette and type %s.' % query, find(query), 'No more than five options are listed under each category.'))
    cases.append(one('no-match', 'Open the palette and type a word that matches nothing.', find('zzzzqqqq'), 'A search with no match lists no option.', ['search-hash/palette'], search=True))
    cases += [
        one('enter-hash', 'Open the palette, type hash and press Enter.', find('hash', go), 'Enter opens the first matching tool and closes the palette.', ['search-hash/palette']),
        one('enter-uuid', 'Open the palette, type uuid and press Enter.', find('uuid', go), 'Enter opens the first matching tool and closes the palette.', ['search-uuid/palette']),
        one('enter-about', 'Open the palette, type about and press Enter.', find('about', go), 'Enter opens the About page.', ['search-about/palette']),
        one('down-enter', 'Open the palette, type hash, press the down arrow and Enter.', find('hash', [press('ArrowDown')] + go), 'The down arrow moves the choice to the next option.', ['search-hash/palette']),
        one('down-twice-enter', 'Open the palette, type hash, press the down arrow twice and Enter.', find('hash', [press('ArrowDown'), press('ArrowDown')] + go), 'Each press of the down arrow moves the choice one option on.', ['search-hash/palette']),
        one('up-clamped', 'Open the palette, type hash, press the up arrow and Enter.', find('hash', [press('ArrowUp')] + go), 'The up arrow does not move the choice above the first option.', ['search-hash/palette']),
        one('down-up-enter', 'Open the palette, type hash, press the down arrow, the up arrow and Enter.', find('hash', [press('ArrowDown'), press('ArrowUp')] + go), 'The up arrow moves the choice back.', ['search-hash/palette']),
        one('escape', 'Open the palette and press Escape.', OPEN + [press('Escape'), wait(0.5)], 'Escape closes the palette.', ['open/palette']),
        one('escape-clears', 'Open the palette, type hash, press Escape and open it again.', find('hash', [press('Escape'), wait(0.3)]) + OPEN, 'A palette opened again starts with an empty search.', ['search-hash/palette'], search=True),
        one('open-twice', 'Press Control and K twice.', OPEN + [press('Control+k'), wait(0.3)], 'Pressing the shortcut again keeps the palette open.', ['open/palette'], search=True),
        one('from-tool', 'Open the Hash text tool, press Control and K and type base64.', find('base64'), listed, ['search-base64/palette'], '/hash-text'),
        one('from-tool-enter', 'Open the Hash text tool, press Control and K, type uuid and press Enter.', find('uuid', go), 'Enter opens the matching tool from any page.', ['search-uuid/palette'], '/hash-text'),
    ]
    return episode('command-palette', 'shell', cases)


# -- Language and About ---------------------------------------------------------------------------------
LANGUAGES = (
    ('german', 'Deutsch'), ('spanish', 'Espa' + chr(241) + 'ol'), ('french', 'Fran' + chr(231) + 'ais'), ('portuguese', 'Portugu' + chr(234) + 's'),
    ('ukrainian', ''.join(map(chr, (1059, 1082, 1088, 1072, 1111, 1085, 1089, 1100, 1082, 1072)))),
    ('vietnamese', 'Ti' + chr(7871) + 'ng Vi' + chr(7879) + 't'), ('chinese', chr(20013) + chr(25991)),
)


def language():
    seen = multi(page=address(), headings=lines(partial=True), menu=menu())

    def one(cid, goal, steps, requirement, page=HOME, requires=()):
        return case(cid, goal, page, steps, [point('texts', requirement, seen, requires)])

    cases = [one('default', DEFAULT, [], 'The page opens in English.')]
    for cid, name in LANGUAGES:
        cases.append(one('home-' + cid, 'Choose %s in the language selector of the home page.' % name, [choose(ENGLISH, name)], 'The headings and the menu are written in the chosen language.'))
    for cid, name in LANGUAGES:
        cases.append(one('tool-' + cid, 'Open the Hash text tool and choose %s in the language selector.' % name, [choose(ENGLISH, name)], 'The page frame and menu follow the chosen language; the tool keeps any untranslated title and description.', '/hash-text'))
    cases += [
        one('stored-german', 'Choose Deutsch and reload the page.', [choose(ENGLISH, 'Deutsch'), reload()], 'The chosen language is kept after reloading the page.', HOME, ['home-german/texts']),
        one('stored-chinese', 'Choose ' + LANGUAGES[-1][1] + ' and reload the page.', [choose(ENGLISH, LANGUAGES[-1][1]), reload()], 'The chosen language is kept after reloading the page.', HOME, ['home-chinese/texts']),
        one('back-to-english', 'Choose Deutsch and then English again.', [choose(ENGLISH, 'Deutsch'), choose('Deutsch', ENGLISH)], 'Choosing English again restores the English texts.', HOME, ['home-german/texts']),
        one('two-changes', 'Choose Deutsch and then Fran' + chr(231) + 'ais.', [choose(ENGLISH, 'Deutsch'), choose('Deutsch', 'Fran' + chr(231) + 'ais')], 'The last chosen language is used.', HOME, ['home-german/texts']),
    ]
    return episode('language', 'shell', cases)


def about():
    seen = multi(page=address(), text=lines(partial=True))

    def one(cid, goal, steps, requirement, requires=()):
        return case(cid, goal, '/about', steps, [point('about', requirement, seen, requires)])

    return episode('about-page', 'shell', [
        one('default', DEFAULT, [], 'The About page shows its headings, its text and its links.'),
        one('german', 'Choose Deutsch in the language selector.', [choose(ENGLISH, 'Deutsch')], 'The About text is written in the chosen language.', ['default/about']),
        one('chinese', 'Choose ' + LANGUAGES[-1][1] + ' in the language selector.', [choose(ENGLISH, LANGUAGES[-1][1])], 'The About text is written in the chosen language.', ['default/about']),
        one('reloaded', 'Reload the page.', [reload()], 'The About page shows the same text after reloading.', ['default/about']),
    ])


def build():
    return [home_favourites(), menu_categories(), command_palette(), language(), about()]

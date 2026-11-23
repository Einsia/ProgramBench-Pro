'''GUI episodes: favorites, menu categories, command palette, language and theme.'''
from gbuild import be, cp, episode
from pbuild import address, cards, controls, lines, menu, multi

HOME_SEEN = multi(headings=lines(partial=True), cards=cards(), menu=menu())
MENU_SEEN = multi(menu=menu())
TEXTS_SEEN = multi(page=address(), headings=lines(partial=True), menu=menu())
PALETTE_SEEN = multi(page=address(), options=controls(area='any', role='option', count_only=True))
ENGLISH = 'English'


def click(text):
    return {'do': 'click', 'text': text, 'area': 'menu'}


def fav(name):
    return {'do': 'click-after', 'link': name, 'tag': 'button'}


def pick(current, option):
    return {'do': 'choose', 'current': current, 'option': option}


def press(key):
    return {'do': 'press', 'key': key}


def typed(value):
    return {'do': 'type', 'value': value}


def wait(seconds=0.5):
    return {'do': 'wait', 'seconds': seconds}


RELOAD = {'do': 'reload'}


def prep_fav(*names):
    return [{'op': 'click-after', 'link': n, 'tag': 'button'} for n in names]


def favorites():
    shown = 'The favorites are listed in a favorites section of the home page and as the first category of the menu.'
    return episode('gui-favorites', 'shell', [
        cp('add', 'Add the Hash text tool to your favorites from the home page.', 'Hash text is listed as a favorite on the home page and in the menu.',
           [fav('Hash text')], [be('home', shown, HOME_SEEN)]),
        cp('add-two', 'Add the Bcrypt tool and then the UUIDs generator tool to your favorites from the home page.', 'Both tools are listed as favorites, Bcrypt first.',
           [fav('Bcrypt'), fav('UUIDs generator')], [be('home', shown, HOME_SEEN)]),
        cp('remove', 'Hash text and Bcrypt are your favorites. Remove Hash text from your favorites and keep Bcrypt.', 'Bcrypt is still a favorite and Hash text is not.',
           [fav('Hash text')], [be('home', 'Only Bcrypt is left in the favorites.', HOME_SEEN, ['add-two/home'])], steps=prep_fav('Hash text', 'Bcrypt'), requires=['add-two/home']),
        cp('remove-last', 'Hash text is your only favorite. Remove it from your favorites.', 'No favorites section is shown any more, on the home page or in the menu.',
           [fav('Hash text')], [be('home', 'The favorites section is gone.', HOME_SEEN, ['add/home'])], steps=prep_fav('Hash text'), requires=['add/home']),
        cp('reload', 'Add the Hash text tool to your favorites and reload the page.', 'After the reload Hash text is still listed as a favorite.',
           [fav('Hash text'), RELOAD], [be('home', 'The favorite is kept after reloading the page.', HOME_SEEN, ['add/home'])], requires=['add/home']),
    ])


def menu():
    hidden = 'The tools of the category are no longer listed in the menu and the other categories keep their tools.'
    return episode('gui-menu', 'shell', [
        cp('collapse', 'Hide the tools of the Crypto category in the menu.', 'The tools of Crypto are hidden from the menu and the other categories still show theirs.',
           [click('Crypto')], [be('menu', hidden, MENU_SEEN)]),
        cp('collapse-web', 'Hide the tools of the Web category in the menu.', 'The tools of Web are hidden from the menu and the other categories still show theirs.',
           [click('Web')], [be('menu', hidden, MENU_SEEN)]),
        cp('expand', 'The Crypto category of the menu is hidden. Show its tools again.', 'The tools of Crypto are listed in the menu again.',
           [click('Crypto')], [be('menu', 'The tools of Crypto are listed again.', MENU_SEEN, ['collapse/menu'])], steps=[{'op': 'click', 'target': {'text': 'Crypto'}}], requires=['collapse/menu']),
        cp('reload', 'Hide the tools of the Crypto category in the menu and reload the page.', 'After the reload the tools of Crypto are still hidden.',
           [click('Crypto'), RELOAD], [be('menu', 'The hidden category stays hidden after reloading the page.', MENU_SEEN, ['collapse/menu'])], requires=['collapse/menu']),
    ])


def palette():
    find = [press('Control+k'), wait(), typed('hash'), wait()]
    return episode('gui-palette', 'shell', [
        cp('open-hash', 'From the home page, search for the Hash text tool with the command palette and open it.', 'The Hash text tool is open and the palette is closed.',
           find + [press('Enter'), wait(0.8)], [be('page', 'The page of the Hash text tool is open and no palette option is listed.', PALETTE_SEEN)]),
        cp('open-uuid', 'From the home page, search for the UUIDs generator with the command palette and open it.', 'The UUIDs generator tool is open and the palette is closed.',
           [press('Control+k'), wait(), typed('uuid'), wait(), press('Enter'), wait(0.8)], [be('page', 'The page of the UUIDs generator is open and no palette option is listed.', PALETTE_SEEN, ['open-hash/page'])], requires=['open-hash/page']),
        cp('about', 'From the home page, use the command palette to open the About page.', 'The About page is open.',
           [press('Control+k'), wait(), typed('about'), wait(), press('Enter'), wait(0.8)], [be('page', 'The About page is open and no palette option is listed.', PALETTE_SEEN, ['open-hash/page'])], requires=['open-hash/page']),
        cp('close', 'Open the command palette and then close it without choosing anything.', 'The palette is closed and the home page is still shown.',
           [press('Control+k'), wait(), press('Escape'), wait()], [be('page', 'The home page is shown and no palette option is listed.', PALETTE_SEEN, ['open-hash/page'])], requires=['open-hash/page']),
        cp('from-tool', 'On the Hash text tool, search for the UUIDs generator with the command palette and open it.', 'The UUIDs generator tool is open.',
           [press('Control+k'), wait(), typed('uuid'), wait(), press('Enter'), wait(0.8)], [be('page', 'The page of the UUIDs generator is open and no palette option is listed.', PALETTE_SEEN, ['open-hash/page'])], page='/hash-text', requires=['open-hash/page']),
    ])


def language():
    wrote = 'The headings and the menu are written in the chosen language.'
    return episode('gui-language', 'shell', [
        cp('german', 'Change the language of the site to Deutsch.', 'The headings and the menu are written in German.',
           [pick(ENGLISH, 'Deutsch')], [be('texts', wrote, TEXTS_SEEN)]),
        cp('french', 'Change the language of the site to Fran' + chr(231) + 'ais.', 'The headings and the menu are written in French.',
           [pick(ENGLISH, 'Fran' + chr(231) + 'ais')], [be('texts', wrote, TEXTS_SEEN)]),
        cp('chinese', 'Change the language of the site to ' + chr(20013) + chr(25991) + '.', 'The headings and the menu are written in Chinese.',
           [pick(ENGLISH, chr(20013) + chr(25991))], [be('texts', wrote, TEXTS_SEEN)]),
        cp('tool-page', 'On the Hash text tool, change the language of the site to Espa' + chr(241) + 'ol.', 'The frame of the page is written in Spanish: the search box reads Buscar and the language selector shows Espa' + chr(241) + 'ol.',
           [pick(ENGLISH, 'Espa' + chr(241) + 'ol')], [be('texts', 'The frame of the page follows the chosen language.', TEXTS_SEEN)], page='/hash-text'),
        cp('back', 'The site is in Deutsch. Change it back to English.', 'The headings and the menu are written in English again.',
           [pick('Deutsch', ENGLISH)], [be('texts', 'The English texts are back.', TEXTS_SEEN, ['german/texts'])], steps=[{'op': 'choose', 'current': ENGLISH, 'option': 'Deutsch'}], requires=['german/texts']),
        cp('reload', 'Change the language of the site to Deutsch and reload the page.', 'After the reload the site is still in German.',
           [pick(ENGLISH, 'Deutsch'), RELOAD], [be('texts', 'The language is kept after reloading the page.', TEXTS_SEEN, ['german/texts'])], requires=['german/texts']),
    ])


def theme():
    toggle = {'do': 'click', 'aria': 'Toggle dark/light mode'}
    return episode('gui-theme', 'shell', [
        cp('dark', 'Switch the site to its dark theme.', 'The page has dark surfaces and light text.', [toggle]),
        cp('palette-dark', 'Use the command palette to switch the site to its dark theme.', 'The page has dark surfaces and light text.',
           [press('Control+k'), wait(), typed('dark'), wait(), press('Enter'), wait(0.8)]),
        cp('light-again', 'Switch the site to its dark theme and then back to the light theme.', 'The page has light surfaces and dark text again.', [toggle, toggle]),
        cp('dark-reload', 'Switch the site to its dark theme and reload the page.', 'After the reload the page still has dark surfaces and light text.', [toggle, RELOAD]),
        cp('tool-page', 'On the Hash text tool, switch the site to its dark theme.', 'The tool page has dark surfaces and light text.', [toggle], page='/hash-text'),
    ])


def build():
    return [favorites(), menu(), palette(), language(), theme()]

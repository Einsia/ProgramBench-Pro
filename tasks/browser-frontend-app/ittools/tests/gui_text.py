'''GUI episodes: text and reference tool pages driven by an evaluator (math, validators, text tools, keys, timer, conversions).'''
from gbuild import be, cp, episode
from pbuild import blocks, controls, fields, lines, multi, outs

NL = chr(10)
FENCE = chr(96) * 3
INPUTS = {'type': 'inputs'}
TIME = ' Time on this page passes only when you advance the page clock.'


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


def fill(value, label=None, placeholder=None):
    step = {'do': 'fill', 'value': value}
    step.update({'label': label} if label is not None else {'placeholder': placeholder})
    return step


def prefill(value, label=None, placeholder=None):
    target = {'label': label} if label is not None else {'placeholder': placeholder}
    return {'op': 'fill', 'target': target, 'value': value}


def click(text):
    return {'do': 'click', 'text': text}


def press(key):
    return {'do': 'press', 'key': key}


def advance(seconds):
    return {'do': 'clock', 'seconds': seconds}


WAIT = {'do': 'wait', 'seconds': 0.5}


# -- math evaluator -----------------------------------------------------------------------------------
MATH_IN = 'Your math expression (ex: 2*sqrt(6) )...'
MATH_SEEN = multi(input=INPUTS, result=lines(skip=2))


def math():
    page = '/math-evaluator'
    shown = 'The result card shows the value of the expression.'
    return episode('gui-math', 'calculator', [
        cp('sqrt', 'On the math evaluator, calculate this expression:' + block('2*sqrt(16)+1'), 'The page shows the result 9.',
           [fill('2*sqrt(16)+1', placeholder=MATH_IN)], [be('result', shown, MATH_SEEN)], page=page),
        cp('power', 'On the math evaluator, calculate this expression:' + block('2^10'), 'The page shows the result 1024.',
           [fill('2^10', placeholder=MATH_IN)], [be('result', shown, MATH_SEEN)], page=page),
        cp('units', 'On the math evaluator, calculate this expression:' + block('2 inch to cm'), 'The page shows the result 5.08 cm.',
           [fill('2 inch to cm', placeholder=MATH_IN)], [be('result', shown, MATH_SEEN)], page=page),
        cp('invalid', 'On the math evaluator, type this expression and nothing else:' + block('2 +'), 'The page shows no result.',
           [fill('2 +', placeholder=MATH_IN)], [be('result', 'No result card is shown.', MATH_SEEN, ['sqrt/result'])], page=page, requires=['sqrt/result']),
    ])


# -- password and IBAN validators ---------------------------------------------------------------------
PASS_IN = 'Enter a password...'
PASS_SEEN = multi(result=lines(start='Duration to crack this password with brute force'))
IBAN_IN = 'Enter an IBAN to check for validity...'
IBAN_SEEN = multi(input=fields(IBAN_IN), result=lines(skip=2, reading='values'))


def validators():
    return episode('gui-validators', 'validator', [
        cp('pw-weak', 'On the password strength analyser, check this password:' + block('abcdefgh'),
           'The page shows a password length of 8 and a character set size of 26.',
           [fill('abcdefgh', placeholder=PASS_IN)], [be('result', 'The figures follow the password.', PASS_SEEN)], page='/password-strength-analyser'),
        cp('pw-strong', 'On the password strength analyser, check this password:' + block('Abcdef12!@'),
           'The page shows a password length of 10 and a character set size of 94.',
           [fill('Abcdef12!@', placeholder=PASS_IN)], [be('result', 'The figures follow the password.', PASS_SEEN)], page='/password-strength-analyser'),
        cp('iban-valid', 'On the IBAN validator, check this IBAN:' + block('DE89370400440532013000'),
           'The page says the IBAN is valid and shows the country code DE.',
           [fill('DE89370400440532013000', placeholder=IBAN_IN)], [be('result', 'The IBAN is reported valid with its country and friendly format.', IBAN_SEEN)], page='/iban-validator-and-parser'),
        cp('iban-invalid', 'On the IBAN validator, check this IBAN:' + block('GB29NWBK60161331926818'),
           'The page says the IBAN is not valid and names a wrong checksum.',
           [fill('GB29NWBK60161331926818', placeholder=IBAN_IN)], [be('result', 'The IBAN is reported invalid with the reason.', IBAN_SEEN, ['iban-valid/result'])],
           page='/iban-validator-and-parser', requires=['iban-valid/result']),
    ])


# -- email normalizer and SafeLink decoder ------------------------------------------------------------
EMAIL_IN = 'Put your emails here (one per line)...'
EMAIL_SEEN = multi(input=INPUTS, output=outs(allow_empty=True))
SAFE_LABEL = 'Your input Outlook SafeLink Url:'
SAFE_SEEN = multi(input=fields(SAFE_LABEL), output=blocks(allow_empty=True))
SAFE_LINK = 'https://eur01.safelinks.protection.outlook.com/?url=https%3A%2F%2Fit-tools.tech%2Fdocs%3Fa%3D1%26b%3D2&data=05%7C01%7Cuser%40example.org&reserved=0'
OTHER_LINK = 'https://example.org/?url=https%3A%2F%2Fit-tools.tech'


def text_tools():
    mail = 'First.Last+news@gmail.com'
    return episode('gui-text-tools', 'normalizer', [
        cp('email', 'On the email normalizer, normalize this address:' + block(mail), 'The normalized address is firstlast@gmail.com.',
           [fill(mail, placeholder=EMAIL_IN)], [be('output', 'The address is shown in its normalized form.', EMAIL_SEEN)], page='/email-normalizer'),
        cp('email-clear', 'The email normalizer holds the address First.Last+news@gmail.com. Empty both boxes with the control made for it.',
           'Both the input and the normalized box are empty.',
           [click('Clear emails')], [be('output', 'Both boxes are empty.', EMAIL_SEEN, ['email/output'])],
           page='/email-normalizer', steps=[prefill(mail, placeholder=EMAIL_IN)], requires=['email/output']),
        cp('safelink', 'On the Outlook SafeLink decoder, decode this link:' + block(SAFE_LINK), 'The decoded address https://it-tools.tech/docs?a=1&b=2 is shown.',
           [fill(SAFE_LINK, label=SAFE_LABEL)], [be('output', 'The wrapped address is shown decoded.', SAFE_SEEN)], page='/safelink-decoder'),
        cp('not-safelink', 'On the Outlook SafeLink decoder, try this link:' + block(OTHER_LINK), 'The page shows an error and no decoded address.',
           [fill(OTHER_LINK, label=SAFE_LABEL)], [be('output', 'A link that is not a SafeLink is refused with an error.', SAFE_SEEN, ['safelink/output'])],
           page='/safelink-decoder', requires=['safelink/output']),
    ])


# -- keycode info -------------------------------------------------------------------------------------
KEY_SEEN = multi(info=outs(labels=True, allow_empty=True), text=lines(skip=2))


def keys():
    page = '/keycode-info'
    shown = 'The key, keycode, code, location and modifiers of the pressed key are shown.'
    return episode('gui-keys', 'reference', [
        cp('enter', 'On the keycode info page, press the Enter key.', 'The page shows the key Enter, the keycode 13 and the code Enter.',
           [press('Enter')], [be('info', shown, KEY_SEEN)], page=page),
        cp('shift-a', 'On the keycode info page, press the A key while holding Shift.', 'The page shows the key A, the keycode 65, the code KeyA and the modifier Shift.',
           [press('Shift+A')], [be('info', shown, KEY_SEEN)], page=page),
        cp('arrow-up', 'On the keycode info page, press the up arrow key.', 'The page shows the key ArrowUp, the keycode 38 and the code ArrowUp.',
           [press('ArrowUp')], [be('info', shown, KEY_SEEN)], page=page),
        cp('ctrl-a', 'On the keycode info page, press the key combination Control+a: hold Control and press the a key, without Shift, so the key is a lowercase a.', 'The page shows the key a, the keycode 65, the code KeyA and the modifier Ctrl.',
           [press('Control+a')], [be('info', shown, KEY_SEEN)], page=page),
    ])


# -- chronometer --------------------------------------------------------------------------------------
CHRONO_SEEN = multi(display=lines(skip=2, reading='all'))


def timer():
    page = '/chronometer'
    return episode('gui-timer', 'timer', [
        cp('run', 'On the chronometer, start it and let 65 seconds pass.' + TIME,
           'The chronometer shows one minute and five seconds (01:05) and its button now offers to stop it.',
           [click('Start'), WAIT, advance(65), WAIT], [be('display', 'The display follows the time that passed.', CHRONO_SEEN)], page=page),
        cp('stop', 'On the chronometer, start it, let 10 seconds pass, stop it and let 100 more seconds pass.' + TIME,
           'The chronometer still shows 00:10 and its button offers to start it again.',
           [click('Start'), WAIT, advance(10), WAIT, click('Stop'), WAIT, advance(100), WAIT],
           [be('display', 'A stopped chronometer keeps its time.', CHRONO_SEEN, ['run/display'])], page=page, requires=['run/display']),
        cp('reset', 'On the chronometer, start it, let 30 seconds pass and then reset it.' + TIME,
           'The chronometer shows 00:00 again.',
           [click('Start'), WAIT, advance(30), WAIT, click('Reset'), WAIT], [be('display', 'Reset sets the display to zero.', CHRONO_SEEN, ['run/display'])], page=page, requires=['run/display']),
    ])


# -- BIP39, Markdown and Docker conversions -----------------------------------------------------------
ENTROPY = 'Your string...'
MNEMONIC = 'Your mnemonic...'
BIP_SEEN = multi(entropy=fields(ENTROPY), passphrase=fields(MNEMONIC))
PHRASE = ' '.join(['abandon'] * 11 + ['about'])
MD_LABEL = 'Your Markdown to convert:'
MD_SEEN = multi(input=fields(MD_LABEL), html=blocks(allow_empty=True))
DOCKER_LABEL = 'Your docker run command:'
DOCKER_SEEN = multi(input=fields(DOCKER_LABEL), compose=blocks(allow_empty=True), notes=lines(start=DOCKER_LABEL))


def conversions():
    markdown = NL.join(['# Title', '', '- one', '- two'])
    command = 'docker run -d --name web -p 8080:80 nginx'
    return episode('gui-conversion', 'converter', [
        cp('bip-to-passphrase', 'On the BIP39 passphrase generator, use this entropy and read the passphrase it gives:' + block('0' * 32),
           'The passphrase is the word abandon eleven times followed by the word about.',
           [fill('0' * 32, placeholder=ENTROPY)], [be('passphrase', 'The passphrase follows the entropy.', BIP_SEEN)], page='/bip39-generator'),
        cp('bip-to-entropy', 'On the BIP39 passphrase generator, enter this passphrase and read the entropy it stands for:' + block(PHRASE),
           'The entropy field shows 32 zeros.',
           [fill(PHRASE, placeholder=MNEMONIC)], [be('passphrase', 'The entropy follows the passphrase.', BIP_SEEN, ['bip-to-passphrase/passphrase'])],
           page='/bip39-generator', requires=['bip-to-passphrase/passphrase']),
        cp('markdown', 'On the Markdown to HTML page, convert this Markdown:' + block('# Title', '', '- one', '- two'),
           'The HTML has a level 1 heading Title and a list with the items one and two.',
           [fill(markdown, label=MD_LABEL)], [be('html', 'The Markdown is shown as HTML.', MD_SEEN)], page='/markdown-to-html'),
        cp('docker', 'On the Docker run to Docker compose converter, convert this command:' + block(command),
           'The compose file defines a service web that uses the image nginx and maps port 8080 to 80.',
           [fill(command, label=DOCKER_LABEL)], [be('compose', 'The command is turned into a compose file.', DOCKER_SEEN)], page='/docker-run-to-docker-compose-converter'),
    ])


def build():
    return [math(), validators(), text_tools(), keys(), timer(), conversions()]

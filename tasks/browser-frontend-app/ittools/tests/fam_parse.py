'''Program episodes: IBAN validator, password strength analyser, phone parser and user-agent parser.'''
from pbuild import bind, case, choose, click, clip, fields, fill, lines, multi, point, episode

DEFAULT = 'Open the page without typing.'


# -- IBAN validator and parser --------------------------------------------------------------------------
IBAN_PAGE = '/iban-validator-and-parser'
IBAN_IN = 'Enter an IBAN to check for validity...'
IBAN_SEEN = multi(input=fields(IBAN_IN), result=lines(skip=2, reading='values'))


def iban_validator_and_parser():
    def one(cid, goal, text, requirement, requires=()):
        return case(cid, goal, IBAN_PAGE, [fill(text, placeholder=IBAN_IN)], [point('result', requirement, IBAN_SEEN, requires)])

    ok = 'The IBAN is reported valid with its country, BBAN and friendly format.'
    bad = 'The IBAN is reported invalid with the reasons it was refused.'
    cases = [
        case('default', DEFAULT, IBAN_PAGE, [], [point('result', 'The page opens with no result and three valid examples listed.', IBAN_SEEN)]),
        one('france', 'Type FR7630006000011234567890189.', 'FR7630006000011234567890189', ok),
        one('germany-spaced', 'Type DE89 3704 0044 0532 0130 00 with its spaces.', 'DE89 3704 0044 0532 0130 00', 'Spaces in the IBAN are ignored.'),
        one('uk-lowercase', 'Type gb29nwbk60161331926819 in lowercase.', 'gb29nwbk60161331926819', 'Lowercase letters are accepted.'),
        one('dashes', 'Type GB29-NWBK-6016-1331-9268-19 with dashes.', 'GB29-NWBK-6016-1331-9268-19', 'Dashes in the IBAN are ignored.'),
        one('netherlands', 'Type NL91ABNA0417164300.', 'NL91ABNA0417164300', ok),
        one('switzerland', 'Type CH9300762011623852957.', 'CH9300762011623852957', ok),
        one('qr-iban', 'Type the Swiss QR-IBAN CH4431999123000889012.', 'CH4431999123000889012', 'A QR-IBAN is recognised as one.'),
        one('belgium', 'Type BE68539007547034.', 'BE68539007547034', ok),
        one('spain', 'Type ES9121000418450200051332.', 'ES9121000418450200051332', ok),
        one('italy', 'Type IT60X0542811101000000123456.', 'IT60X0542811101000000123456', ok),
        one('norway-short', 'Type the short Norwegian IBAN NO9386011117947.', 'NO9386011117947', ok),
        one('malta-long', 'Type the long Maltese IBAN MT84MALT011000012345MTLCAST001S.', 'MT84MALT011000012345MTLCAST001S', ok),
        one('checksum', 'Type GB29NWBK60161331926818 with a wrong last digit.', 'GB29NWBK60161331926818', bad, ['uk-lowercase/result']),
        one('too-short', 'Type GB29NWBK6016133192681 with a digit missing.', 'GB29NWBK6016133192681', bad, ['uk-lowercase/result']),
        one('bban-format', 'Type GB29NWBK6016133192681A with a letter where digits belong.', 'GB29NWBK6016133192681A', bad, ['uk-lowercase/result']),
        one('no-country', 'Type 1234567890.', '1234567890', bad, ['uk-lowercase/result']),
        one('unknown-country', 'Type XX001234.', 'XX001234', bad, ['uk-lowercase/result']),
        one('two-letters', 'Type DE.', 'DE', bad, ['uk-lowercase/result']),
        one('text', 'Type hello.', 'hello', bad, ['uk-lowercase/result']),
        one('blank', 'Type only spaces.', '   ', 'A value with only spaces shows no result.', ['france/result']),
    ]
    cases.append(case('copy-example', 'Click the German example IBAN.', IBAN_PAGE, [click('DE89 3704 0044 0532 0130 00')],
                      [point('copied', 'Clicking an example copies the IBAN without spaces.', multi(copied=clip(), input=fields(IBAN_IN)))]))
    return episode('iban-validator-and-parser', 'validator', cases)


# -- Password strength analyser -------------------------------------------------------------------------
PASS_PAGE = '/password-strength-analyser'
PASS_IN = 'Enter a password...'
PASS_SEEN = multi(result=lines(start='Duration to crack this password with brute force'))


def password_strength_analyser():
    def one(cid, goal, text, requirement):
        return case(cid, goal, PASS_PAGE, [fill(text, placeholder=PASS_IN)], [point('result', requirement, PASS_SEEN)])

    rate = 'The crack time, length, entropy, character set size and score are shown.'
    cases = [
        case('default', DEFAULT, PASS_PAGE, [], [point('result', 'The page opens with an empty password and the figures at zero.', PASS_SEEN)]),
        one('lower-4', 'Type abcd.', 'abcd', 'A very weak password is cracked instantly.'),
        one('lower-6', 'Type abcdef.', 'abcdef', 'A weak password takes less than a second.'),
        one('lower-8', 'Type abcdefgh.', 'abcdefgh', rate),
        one('lower-10', 'Type abcdefghij.', 'abcdefghij', rate),
        one('lower-12', 'Type abcdefghijkl.', 'abcdefghijkl', rate),
        one('upper', 'Type ABCDEFGH.', 'ABCDEFGH', 'Uppercase letters alone give a set of 26.'),
        one('digits-4', 'Type 1234.', '1234', 'Digits alone give a set of 10.'),
        one('digits-8', 'Type 12345678.', '12345678', 'Digits alone give a set of 10.'),
        one('symbols', 'Type !@#$%^&*.', '!@#$%^&*', 'Symbols alone give a set of 32.'),
        one('mixed', 'Type Abcdef12.', 'Abcdef12', 'Three character classes add up to a set of 62.'),
        one('all-classes', 'Type Abcdef12!@.', 'Abcdef12!@', 'Four character classes add up to a set of 94.'),
        one('space', 'Type a single space.', ' ', 'A space counts as a special character.'),
        one('underscore', 'Type eight underscores.', '________', 'An underscore counts as a special character.'),
        one('accents', 'Type p' + chr(228) + 'ssw' + chr(246) + 'rd.', 'p' + chr(228) + 'ssw' + chr(246) + 'rd', 'Accented letters count as special characters.'),
        one('passphrase', 'Type Correct Horse Battery Staple 2024!.', 'Correct Horse Battery Staple 2024!', 'A long password reaches the top score.'),
        one('huge', 'Type a 48-character password of four classes.', 'aB3$' * 12, 'A huge crack time is shown in millennia with an exponent.'),
        one('years', 'Type a 12-character password of three classes.', 'Abcdef123456', rate),
        one('days', 'Type a 10-character password of two classes.', 'abcdef1234', rate),
    ]
    return episode('password-strength-analyser', 'analyser', cases)


# -- Phone parser and formatter -------------------------------------------------------------------------
PHONE_PAGE = '/phone-parser-and-formatter'
PHONE_LABEL = 'Phone number:'
PHONE_SEEN = multi(input=fields(PHONE_LABEL), result=lines(start=PHONE_LABEL, reading='values'))
US = 'United States (+1)'


def phone_parser_and_formatter():
    def one(cid, goal, text, requirement, before=(), requires=()):
        return case(cid, goal, PHONE_PAGE, list(before) + [fill(text, label=PHONE_LABEL)], [point('result', requirement, PHONE_SEEN, requires)])

    def pick(name, search):
        return [choose(US, name, search=search)]

    shown = 'The number is described with its country, validity, type and formats.'
    cases = [
        case('default', DEFAULT, PHONE_PAGE, [], [point('result', 'The page opens with the United States selected and no result.', PHONE_SEEN)]),
        one('us-national', 'Type (212) 456-7890 with the United States selected.', '(212) 456-7890', shown),
        one('us-international', 'Type +1 650 253 0000.', '+1 650 253 0000', shown),
        one('us-mobile', 'Type +1 415 555 2671.', '+1 415 555 2671', shown),
        one('us-toll-free', 'Type +1 800 555 0199.', '+1 800 555 0199', shown),
        one('france-prefix', 'Type +33 1 23 45 67 89 with the United States selected.', '+33 1 23 45 67 89',
            'A leading plus sign overrides the selected country.'),
        one('france-selected', 'Select France and type 01 23 45 67 89.', '01 23 45 67 89', 'The selected country is used for a national number.',
            pick('France (+33)', 'France')),
        one('uk-selected', 'Select United Kingdom and type 020 7946 0958.', '020 7946 0958', shown, pick('United Kingdom (+44)', 'United Kingdom')),
        one('uk-premium', 'Type +44 909 8790879.', '+44 909 8790879', shown),
        one('germany-selected', 'Select Germany and type 030 123456.', '030 123456', shown, pick('Germany (+49)', 'Germany')),
        one('japan-selected', 'Select Japan and type 03-1234-5678.', '03-1234-5678', shown, pick('Japan (+81)', 'Japan')),
        one('australia-selected', 'Select Australia and type 02 1234 5678.', '02 1234 5678', shown, pick('Australia (+61)', 'Australia')),
        one('override-selected', 'Select France and type +1 212 456 7890.', '+1 212 456 7890', 'A leading plus sign overrides the country that was selected.',
            pick('France (+33)', 'France')),
        one('parentheses', 'Type +1 (212) 456-7890.', '+1 (212) 456-7890', 'Parentheses and dashes are accepted.'),
        one('too-short', 'Type 12345.', '12345', 'A number that is too short is reported as not valid or not possible.'),
        one('unknown-code', 'Type +999 123456.', '+999 123456', 'An unknown calling code shows no result.'),
        one('plus-only', 'Type a lone plus sign.', '+', 'A lone plus sign shows no result.'),
    ]
    for cid, goal, text in (('letters', 'Type abc.', 'abc'), ('mixed-letters', 'Type 212 CALL NOW.', '212 CALL NOW'), ('dot', 'Type 212.456.7890.', '212.456.7890')):
        cases.append(one(cid, goal, text, 'Characters other than digits, spaces, plus, dashes and parentheses are refused with a message.',
                         requires=['us-national/result']))
    return episode('phone-parser-and-formatter', 'parser', bind(cases, {'unknown-code': 'us-national/result', 'plus-only': 'us-national/result'}))


# -- User-agent parser ----------------------------------------------------------------------------------
UA_PAGE = '/user-agent-parser'
UA_LABEL = 'User agent string'
UA_SEEN = multi(input=fields(UA_LABEL), result=lines(start=UA_LABEL))
WEBKIT = 'AppleWebKit/537.36 (KHTML, like Gecko)'


def user_agent_parser():
    def one(cid, goal, text, requirement):
        return case(cid, goal, UA_PAGE, [fill(text, label=UA_LABEL)], [point('result', requirement, UA_SEEN)])

    shown = 'The browser, engine, OS, device and CPU are named with versions where the string gives them.'
    cases = [
        case('default', DEFAULT, UA_PAGE, [], [point('result', 'The page opens with the browser own user agent already parsed.', UA_SEEN)]),
        one('chrome-windows', 'Type a Chrome on Windows user agent.', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' + WEBKIT + ' Chrome/120.0.0.0 Safari/537.36', shown),
        one('firefox-linux', 'Type a Firefox on Linux user agent.', 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0', shown),
        one('safari-mac', 'Type a Safari on macOS user agent.',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15', shown),
        one('iphone', 'Type a Safari on iPhone user agent.',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1', shown),
        one('ipad', 'Type a Safari on iPad user agent.',
            'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1', shown),
        one('android', 'Type a Chrome on Android phone user agent.',
            'Mozilla/5.0 (Linux; Android 14; Pixel 8) ' + WEBKIT + ' Chrome/120.0.0.0 Mobile Safari/537.36', shown),
        one('edge', 'Type an Edge on Windows user agent.',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' + WEBKIT + ' Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0', shown),
        one('arm-linux', 'Type a Chrome on ARM Linux user agent.', 'Mozilla/5.0 (X11; Linux aarch64) ' + WEBKIT + ' Chrome/120.0.0.0 Safari/537.36', shown),
        one('tv', 'Type a smart TV user agent.',
            'Mozilla/5.0 (SMART-TV; Linux; Tizen 7.0) ' + WEBKIT + ' 94.0.4606.31/7.0 TV Safari/537.36', shown),
        one('bot', 'Type the Googlebot user agent.', 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)', shown),
        one('curl', 'Type curl/8.4.0.', 'curl/8.4.0', 'A command line client is named without engine or OS.'),
        one('trim', 'Type a Firefox user agent with spaces around it.', '  Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0  ',
            'Spaces around the string are ignored.'),
        one('nonsense', 'Type some words that are not a user agent.', 'just some words', 'Nothing is recognised and every part says it is not available.'),
        one('empty', 'Clear the user agent.', '', 'An empty string shows every part as not available.'),
        one('blank', 'Type only spaces.', '   ', 'A string of only spaces shows every part as not available.'),
    ]
    return episode('user-agent-parser', 'parser', cases)


def build():
    return [iban_validator_and_parser(), password_strength_analyser(), phone_parser_and_formatter(), user_agent_parser()]

'''GUI episodes: tool pages driven by an evaluator, with program companions (network, converters, crypto, reference).'''
from gbuild import be, cp, episode
from pbuild import blocks, controls, fields, lines, multi, outs, toggles

NL = chr(10)
FENCE = chr(96) * 3
INPUTS = {'type': 'inputs'}


def fill(value, label=None, placeholder=None, nth=0):
    step = {'do': 'fill', 'value': value}
    step.update({'label': label} if label is not None else {'placeholder': placeholder})
    if nth:
        step['nth'] = nth
    return step


def click(text, nth=0):
    step = {'do': 'click', 'text': text}
    if nth:
        step['nth'] = nth
    return step


def tick(index):
    return {'do': 'click', 'role': 'checkbox', 'nth': index}


def pick(current, option):
    return {'do': 'choose', 'current': current, 'option': option}


def prefill(value, label=None, placeholder=None):
    target = {'label': label} if label is not None else {'placeholder': placeholder}
    return {'op': 'fill', 'target': target, 'value': value}


def block(*rows):
    return NL + FENCE + NL + NL.join(rows) + NL + FENCE + NL


# -- network calculators ------------------------------------------------------------------------------
SUBNET = 'An IPv4 address with or without mask'
SUBNET_SEEN = multi(input=fields(SUBNET), table=lines(skip=2, reading='values'))
ADDR = 'The ipv4 address:'
ADDR_SEEN = multi(input=fields(ADDR), result=fields('Decimal:', 'Hexadecimal:', 'Binary:', 'Ipv6:', 'Ipv6 (short):'))
START, END = 'Start address', 'End address'
RANGE_SEEN = multi(input=fields(START, END), result=lines(skip=2, reading='values'))
SWITCH = 'Switch start and end IPv4 address'


def network():
    return episode('gui-network', 'calculator', [
        cp('subnet', 'On the IPv4 subnet calculator, work out the block of 172.16.5.9/20.',
           'The page shows the network address 172.16.0.0, the broadcast address 172.16.15.255 and a size of 4096 addresses.',
           [fill('172.16.5.9/20', label=SUBNET)], [be('table', 'The table describes the block 172.16.0.0/20.', SUBNET_SEEN)], page='/ipv4-subnet-calculator'),
        cp('next-block', 'The IPv4 subnet calculator shows the block 192.168.0.200/24. Move on to the next block of the same size.',
           'The calculator describes the block that starts at 192.168.1.0 and its address field shows that block.',
           [click('Next block')], [be('table', 'The address field and the table show the block 192.168.1.0/24.', SUBNET_SEEN)],
           page='/ipv4-subnet-calculator', steps=[prefill('192.168.0.200/24', label=SUBNET)]),
        cp('previous-block', 'The IPv4 subnet calculator shows the block 10.0.0.0/16. Move back to the previous block of the same size.',
           'The calculator describes the block that starts at 9.255.0.0 and its address field shows that block.',
           [click('Previous block')], [be('table', 'The address field and the table show the block 9.255.0.0/16.', SUBNET_SEEN, ['next-block/table'])],
           page='/ipv4-subnet-calculator', steps=[prefill('10.0.0.0/16', label=SUBNET)], requires=['next-block/table']),
        cp('address', 'On the IPv4 address converter, convert the address 10.0.0.1.',
           'The page shows the decimal form 167772161 and the hexadecimal form 0A000001.',
           [fill('10.0.0.1', label=ADDR)], [be('result', 'The converted fields follow the address 10.0.0.1.', ADDR_SEEN)], page='/ipv4-address-converter'),
        cp('range', 'On the IPv4 range expander, expand the range from 10.0.0.5 to 10.0.1.20 to the smallest block that holds it.',
           'The page shows the block 10.0.0.0/23 with 512 addresses.',
           [fill('10.0.0.5', label=START), fill('10.0.1.20', label=END)], [be('result', 'The table shows the block 10.0.0.0/23.', RANGE_SEEN)], page='/ipv4-range-expander'),
        cp('range-switch', 'The IPv4 range expander shows a start address above the end address and offers a way to fix it. Fix it with that control.',
           'The page shows the block 10.0.0.0/28 with 16 addresses.',
           [click(SWITCH)], [be('result', 'The addresses are exchanged and the table shows the block 10.0.0.0/28.', RANGE_SEEN, ['range/result'])],
           page='/ipv4-range-expander', steps=[prefill('10.0.0.9', label=START), prefill('10.0.0.1', label=END)], requires=['range/result']),
    ])


# -- converters ---------------------------------------------------------------------------------------
COLORS = multi(colors=fields('hex:', 'rgb:', 'hsl:', 'name:'))
LIST_SEEN = multi(output=blocks(allow_empty=True))
OBF = 'String to obfuscate:'
OBF_SEEN = multi(result=lines(start=OBF))


def converters():
    token = 'ghp_abc123XYZ789secret'
    return episode('gui-converters', 'converter', [
        cp('hex-to-rgb', 'On the color converter, convert the color #ff8800 to its rgb form.',
           'The rgb field shows rgb(255, 136, 0).',
           [fill('#ff8800', label='hex:')], [be('colors', 'The colour fields follow #ff8800.', COLORS)], page='/color-converter'),
        cp('rgb-to-hex', 'On the color converter, find the hex form of the color rgb(0, 128, 255).',
           'The hex field shows #0080ff.',
           [fill('rgb(0, 128, 255)', label='rgb:')], [be('colors', 'The colour fields follow rgb(0, 128, 255).', COLORS)], page='/color-converter'),
        cp('name-to-hex', 'On the color converter, find the hex form of the CSS color named tomato.',
           'The hex field shows #ff6347.',
           [fill('tomato', label='name:')], [be('colors', 'The colour fields follow the name tomato.', COLORS)], page='/color-converter'),
        cp('sort-join', 'On the list converter, type these four lines as the input:' + block('b', 'a', 'b', 'c') +
           'Turn them into one sorted list without repeated items, written on one line with a semicolon and a space between the items.',
           'The result is a; b; c.',
           [pick('Sort alphabetically', 'Sort ascending'), fill('; ', label='Separator'), fill(NL.join(['b', 'a', 'b', 'c']), label='Your input data')],
           [be('output', 'The list is sorted, has no repeats and uses the semicolon separator.', LIST_SEEN)], page='/list-converter'),
        cp('obfuscate', 'On the string obfuscator, hide the text ' + token + ' so that only its first four and last four characters stay readable.',
           'The result is ghp_ followed by 14 asterisks and cret.',
           [fill(token, label=OBF)], [be('result', 'The middle of the text is replaced by asterisks.', OBF_SEEN)], page='/string-obfuscator'),
    ])


# -- crypto -------------------------------------------------------------------------------------------
VECTOR = '$2a$05$CCCCCCCCCCCCCCCCCCCCC.E5YPO9kmyuRGyh0XouQYb4YMJKvyOeW'
BCRYPT_SEEN = multi(text=lines(skip=2))


def crypto():
    compare = [('Your string to compare...', 'Your hash to compare...')]
    text_ph, hash_ph = compare[0]
    return episode('gui-crypto', 'crypto', [
        cp('uuid-nil', 'On the UUIDs generator, generate the nil UUID.',
           'The page shows the UUID 00000000-0000-0000-0000-000000000000.',
           [click('NIL')], [be('uuid', 'The page shows the all-zero UUID.', multi(inputs=INPUTS, output=outs()))], page='/uuid-generator'),
        cp('bcrypt-match', 'On the bcrypt page, check whether the text U*U matches this hash:' + block(VECTOR),
           'The page answers Yes.',
           [fill('U*U', placeholder=text_ph), fill(VECTOR, placeholder=hash_ph)], [be('result', 'The comparison answers Yes.', BCRYPT_SEEN)], page='/bcrypt'),
        cp('bcrypt-mismatch', 'On the bcrypt page, check whether the text U*V matches this hash:' + block(VECTOR),
           'The page answers No.',
           [fill('U*V', placeholder=text_ph), fill(VECTOR, placeholder=hash_ph)], [be('result', 'The comparison answers No.', BCRYPT_SEEN, ['bcrypt-match/result'])],
           page='/bcrypt', requires=['bcrypt-match/result']),
    ])


# -- reference tools ----------------------------------------------------------------------------------
SEARCH = 'Search http status...'
HTTP_SEEN = multi(input=fields(SEARCH), list=lines(skip=2, partial=True))
CRON_IN = '* * * * *'
CRON_SEEN = multi(input=fields(CRON_IN), switches=toggles(), text=lines(skip=2, stop='Verbose'))
CHMOD_SEEN = multi(result=lines(skip=2), command=outs(), boxes=toggles())


def reference():
    return episode('gui-reference', 'reference', [
        cp('http-404', 'On the HTTP status codes page, search the list for the text 404.',
           'The list shows the 404 status with its name.',
           [fill('404', placeholder=SEARCH)], [be('list', 'The list is narrowed to the search.', HTTP_SEEN)], page='/http-status-codes'),
        cp('http-teapot', 'On the HTTP status codes page, search the list for the text teapot.',
           'The list shows the 418 status with its name.',
           [fill('teapot', placeholder=SEARCH)], [be('list', 'The list is narrowed to the search.', HTTP_SEEN)], page='/http-status-codes'),
        cp('cron-weekdays', 'On the crontab generator, describe the schedule 30 8 * * 1-5.',
           'The page describes the schedule as running at 08:30 from Monday through Friday.',
           [fill('30 8 * * 1-5', placeholder=CRON_IN)], [be('text', 'The description follows the schedule.', CRON_SEEN)], page='/crontab-generator'),
        cp('cron-five', 'On the crontab generator, describe the schedule */5 * * * *.',
           'The page describes the schedule as running every 5 minutes.',
           [fill('*/5 * * * *', placeholder=CRON_IN)], [be('text', 'The description follows the schedule.', CRON_SEEN, ['cron-weekdays/text'])], page='/crontab-generator', requires=['cron-weekdays/text']),
        cp('cron-invalid', 'On the crontab generator, try the schedule 60 * * * *.',
           'The page flags the schedule as invalid and gives no description of it.',
           [fill('60 * * * *', placeholder=CRON_IN)], [be('text', 'The schedule is flagged as invalid.', CRON_SEEN, ['cron-weekdays/text'])], page='/crontab-generator', requires=['cron-weekdays/text']),
        cp('chmod-744', 'On the chmod calculator, give the owner read, write and execute permission and the group and the public read permission only.',
           'The calculator shows the mode 744 and the command chmod 744 path.',
           [tick(0), tick(3), tick(6), tick(1), tick(2)], [be('result', 'The mode follows the ticked permissions.', CHMOD_SEEN)], page='/chmod-calculator'),
        cp('chmod-640', 'On the chmod calculator, give the owner read and write permission, the group read permission only and the public no permission.',
           'The calculator shows the mode 640 and the command chmod 640 path.',
           [tick(0), tick(3), tick(1)], [be('result', 'The mode follows the ticked permissions.', CHMOD_SEEN, ['chmod-744/result'])], page='/chmod-calculator', requires=['chmod-744/result']),
    ])


def build():
    return [network(), converters(), crypto(), reference()]

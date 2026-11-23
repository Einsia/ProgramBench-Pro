'''Program episodes: IPv4 subnet, address and range tools, MAC address and IPv6 ULA generators, random port.'''
from pbuild import case, changed, click, clock, fields, remember, fill, lines, multi, outs, point, reload, shape, episode

DEFAULT = 'Open the page without typing.'


# -- IPv4 subnet calculator -----------------------------------------------------------------------------
SUBNET = 'An IPv4 address with or without mask'
SUBNET_PAGE = '/ipv4-subnet-calculator'
SUBNET_SEEN = multi(input=fields(SUBNET), table=lines(skip=2, reading='values'))


def block(cid, goal, text, requirement, after=()):
    return case(cid, goal, SUBNET_PAGE, [fill(text, label=SUBNET)] + list(after),
                [point('table', requirement, SUBNET_SEEN)])


def ipv4_subnet_calculator():
    cases = [
        case('default', DEFAULT, SUBNET_PAGE, [],
             [point('table', 'The page opens with a stored example block already calculated.', SUBNET_SEEN)]),
        block('class-a', 'Type 10.1.2.3/8.', '10.1.2.3/8', 'The table describes the block and names class A.'),
        block('class-b', 'Type 172.16.5.9/20.', '172.16.5.9/20', 'The table describes the block and names class B.'),
        block('class-c', 'Type 192.168.1.77/26.', '192.168.1.77/26', 'The table describes the block and names class C.'),
        block('class-d', 'Type 224.0.0.1/4.', '224.0.0.1/4', 'The table describes the block and names class D.'),
        block('class-e', 'Type 240.0.0.0/4.', '240.0.0.0/4', 'The table describes the block and names class E.'),
        block('single', 'Type 10.0.0.7/32.', '10.0.0.7/32', 'A single-address block has no broadcast address.'),
        block('pair', 'Type 10.0.0.0/31.', '10.0.0.0/31', 'A two-address block has no broadcast address.'),
        block('everything', 'Type 0.0.0.0/0.', '0.0.0.0/0', 'The whole address space is described with its full size.'),
        block('no-mask', 'Type 203.0.113.9 without a mask.', '203.0.113.9', 'An address without a mask is a single-address block.'),
        block('dotted-mask', 'Type 192.168.10.0/255.255.254.0.', '192.168.10.0/255.255.254.0',
              'A dotted mask is accepted in place of a prefix length.'),
        block('spaces', 'Type an address with spaces around it.', '  172.20.1.1/16  ', 'Spaces around the address are ignored.'),
        block('next', 'Type 10.20.30.40/16 and press Next block.', '10.20.30.40/16',
              'Next block moves to the following block of the same size and puts it in the input.', [click('Next block')]),
        block('next-twice', 'Type 10.20.30.40/16 and press Next block twice.', '10.20.30.40/16',
              'Each press moves one more block forward.', [click('Next block'), click('Next block')]),
        block('previous', 'Type 10.0.0.0/16 and press Previous block.', '10.0.0.0/16',
              'Previous block moves to the preceding block of the same size and puts it in the input.', [click('Previous block')]),
        block('stored', 'Type 10.9.8.7/12 and reload the page.', '10.9.8.7/12',
              'The typed block is still there after reloading the page.', [reload()]),
    ]
    for cid, goal, text in (('refused', 'Type text that is not an address.', 'not an address'),
                            ('bad-prefix', 'Type 10.0.0.1/33.', '10.0.0.1/33')):
        cases.append(case(cid, goal, SUBNET_PAGE, [fill(text, label=SUBNET)],
                          [point('message', 'A value that cannot be parsed is refused with a message and no table is shown.',
                                 lines(start=SUBNET), ['class-a/table'])]))
    return episode('ipv4-subnet-calculator', 'calculator', cases)


# -- IPv4 address converter -----------------------------------------------------------------------------
ADDR = 'The ipv4 address:'
ADDR_OUTS = ('Decimal:', 'Hexadecimal:', 'Binary:', 'Ipv6:', 'Ipv6 (short):')
ADDR_PAGE = '/ipv4-address-converter'
ADDR_SEEN = multi(input=fields(ADDR), result=fields(*ADDR_OUTS))


def ipv4_address_converter():
    def one(cid, goal, text, requirement, after=()):
        return case(cid, goal, ADDR_PAGE, [fill(text, label=ADDR)] + list(after),
                    [point('result', requirement, ADDR_SEEN)])

    shown = 'The address is shown as decimal, hexadecimal, binary and two IPv6 forms.'
    cases = [
        case('default', DEFAULT, ADDR_PAGE, [],
             [point('result', 'The page opens with a stored example address already converted.', ADDR_SEEN)]),
        one('private', 'Type 10.0.0.1.', '10.0.0.1', shown),
        one('loopback', 'Type 127.0.0.1.', '127.0.0.1', shown),
        one('zero', 'Type 0.0.0.0.', '0.0.0.0', 'The zero address converts with its padding.'),
        one('broadcast', 'Type 255.255.255.255.', '255.255.255.255', 'The highest address converts with its padding.'),
        one('public', 'Type 8.8.4.4.', '8.8.4.4', shown),
        one('spaces', 'Type an address with spaces around it.', ' 192.0.2.99 ', 'Spaces around the address are ignored.'),
        one('stored', 'Type 172.31.4.5 and reload the page.', '172.31.4.5',
            'The typed address is still there after reloading the page.', [reload()]),
    ]
    for cid, goal, text in (('too-big', 'Type 256.1.1.1.', '256.1.1.1'), ('too-short', 'Type 1.2.3.', '1.2.3')):
        cases.append(case(cid, goal, ADDR_PAGE, [fill(text, label=ADDR)], [
            point('result', 'An invalid address leaves every converted field empty.', ADDR_SEEN, ['private/result']),
            point('message', 'An invalid address is flagged with a message.', lines(start=ADDR, stop='Decimal:'),
                  ['private/result'])]))
    return episode('ipv4-address-converter', 'converter', cases)


# -- IPv4 range expander --------------------------------------------------------------------------------
START, END = 'Start address', 'End address'
SWITCH = 'Switch start and end IPv4 address'
RANGE_PAGE = '/ipv4-range-expander'
RANGE_SEEN = multi(input=fields(START, END), result=lines(skip=2, reading='values'))


def ipv4_range_expander():
    def one(cid, goal, start, end, requirement, after=()):
        return case(cid, goal, RANGE_PAGE, [fill(start, label=START), fill(end, label=END)] + list(after),
                    [point('result', requirement, RANGE_SEEN)])

    cases = [
        case('default', DEFAULT, RANGE_PAGE, [],
             [point('result', 'The page opens with a stored example range already expanded.', RANGE_SEEN)]),
        one('exact', 'Type 10.0.0.0 to 10.0.0.255.', '10.0.0.0', '10.0.0.255', 'A range that is already a block keeps its size.'),
        one('unaligned', 'Type 10.0.0.5 to 10.0.1.20.', '10.0.0.5', '10.0.1.20',
            'A range is widened to the smallest block that holds it.'),
        one('single', 'Type 1.1.1.1 to 1.1.1.1.', '1.1.1.1', '1.1.1.1', 'One address is a block of size one.'),
        one('everything', 'Type 0.0.0.0 to 255.255.255.255.', '0.0.0.0', '255.255.255.255',
            'The whole address space is one block with its full size.'),
        one('crossing', 'Type 192.168.1.255 to 192.168.2.0.', '192.168.1.255', '192.168.2.0',
            'A range that straddles a boundary is widened to the block that holds both ends.'),
        one('large', 'Type 10.0.0.1 to 10.255.255.254.', '10.0.0.1', '10.255.255.254',
            'Large sizes are shown with thousands separators.'),
        one('switch', 'Type 10.0.0.9 to 10.0.0.1 and press the switch button.', '10.0.0.9', '10.0.0.1',
            'The switch button exchanges the two addresses and the block is then shown.', [click(SWITCH)]),
        one('stored', 'Type 10.20.0.0 to 10.20.3.255 and reload the page.', '10.20.0.0', '10.20.3.255',
            'The typed addresses are still there after reloading the page.', [reload()]),
        case('reversed', 'Type 10.0.0.9 to 10.0.0.1.', RANGE_PAGE, [fill('10.0.0.9', label=START), fill('10.0.0.1', label=END)],
             [point('message', 'A start above the end is explained with an offer to switch them and no block is shown.',
                    lines(start=END), ['exact/result'])]),
        case('bad-start', 'Type abc as the start and 10.0.0.1 as the end.', RANGE_PAGE,
             [fill('abc', label=START), fill('10.0.0.1', label=END)],
             [point('message', 'An invalid start is flagged with a message and no block is shown.',
                    lines(start=START), ['exact/result'])]),
        case('bad-end', 'Type 10.0.0.1 as the start and 10.0.0.999 as the end.', RANGE_PAGE,
             [fill('10.0.0.1', label=START), fill('10.0.0.999', label=END)],
             [point('message', 'An invalid end is flagged with a message and no block is shown.',
                    lines(start=START), ['exact/result'])]),
    ]
    return episode('ipv4-range-expander', 'calculator', cases)


# -- MAC address generator ------------------------------------------------------------------------------
MAC_PAGE = '/mac-address-generator'
QTY = 'Please Input'
PREFIX = 'MAC address prefix:'
HEX_UP, HEX_LOW = '[0-9A-F]{2}', '[0-9a-f]{2}'
DEFAULT_PREFIX = ['64', '16', '7F']


def mac_pattern(prefix, sep=':', upper=True):
    parts = list(prefix) + [HEX_UP if upper else HEX_LOW] * (6 - len(prefix))
    return ('[' + sep + ']' if sep else '').join(parts)


def macs(prefix, sep=':', upper=True, source='block'):
    return shape(source, line_pattern=mac_pattern(prefix, sep, upper), lines=True, only_patterns=True)


def mac_address_generator():
    def one(cid, goal, steps, seen, requirement):
        return case(cid, goal, MAC_PAGE, steps, [point('macs', requirement, seen)])

    low = ['64', '16', '7f']
    cases = [
        one('default', DEFAULT, [], macs(DEFAULT_PREFIX), 'One uppercase address with the stored prefix and colons is shown.'),
        one('lowercase', 'Press Lowercase.', [click('Lowercase')], macs(low, upper=False), 'The address is shown in lowercase.'),
        one('dash', 'Press the dash separator.', [click('-')], macs(DEFAULT_PREFIX, '-'), 'Bytes are joined with dashes.'),
        one('dot', 'Press the dot separator.', [click('.')], macs(DEFAULT_PREFIX, '.'), 'Bytes are joined with dots.'),
        one('plain', 'Press the None separator.', [click('None')], macs(DEFAULT_PREFIX, ''), 'Bytes are joined without a separator.'),
        one('quantity-5', 'Set the quantity to 5.', [fill('5', placeholder=QTY)], macs(DEFAULT_PREFIX),
            'Five addresses are shown, one per line.'),
        one('quantity-100', 'Set the quantity to 100.', [fill('100', placeholder=QTY)], macs(DEFAULT_PREFIX),
            'One hundred addresses are shown, one per line.'),
        one('prefix-short', 'Type the prefix AA:B1.', [fill('AA:B1', label=PREFIX)], macs(['AA', 'B1']),
            'The remaining bytes are random after a two-byte prefix.'),
        one('prefix-full', 'Type the prefix DE:AD:BE:EF:00:01.', [fill('DE:AD:BE:EF:00:01', label=PREFIX)],
            macs(['DE', 'AD', 'BE', 'EF', '00', '01']), 'A six-byte prefix is the whole address.'),
        one('prefix-dashed', 'Type the prefix 0A-1B-2C.', [fill('0A-1B-2C', label=PREFIX)], macs(['0A', '1B', '2C']),
            'A prefix with dashes is accepted.'),
        one('combined', 'Set 3 addresses, the prefix AA:BB:CC, lowercase and dashes.',
            [fill('3', placeholder=QTY), fill('AA:BB:CC', label=PREFIX), click('Lowercase'), click('-')],
            macs(['aa', 'bb', 'cc'], '-', False), 'Quantity, prefix, case and separator all apply together.'),
        one('stored', 'Set 2 addresses, the prefix AB:CD:EF and dashes, then reload.',
            [fill('2', placeholder=QTY), fill('AB:CD:EF', label=PREFIX), click('-'), reload()],
            macs(['AB', 'CD', 'EF'], '-'), 'Quantity, prefix and separator are kept after reloading and the case goes back to uppercase.'),
        one('refresh', 'Press Refresh.', [remember(BLOCK0), click('Refresh')], multi(macs=macs(DEFAULT_PREFIX), changed=changed(BLOCK0)), 'Refresh shows a new valid address.'),
        one('copy', 'Set 3 addresses and press Copy.', [fill('3', placeholder=QTY), click('Copy')],
            macs(DEFAULT_PREFIX, source='clipboard'), 'Copy puts every address on the clipboard, one per line.'),
    ]
    for cid, goal, text in (('refused', 'Type the prefix xyz.', 'xyz'),
                            ('too-long', 'Type a seven-byte prefix.', '11:22:33:44:55:66:77'),
                            ('no-separator', 'Type the prefix a1b2.', 'a1b2'),
                            ('one-digit', 'Type the prefix 6:A.', '6:A')):
        cases.append(case(cid, goal, MAC_PAGE, [fill(text, label=PREFIX)],
                          [point('message', 'An invalid prefix is flagged with a message and no address is shown.',
                                 lines(start=PREFIX), ['default/macs'])]))
    return episode('mac-address-generator', 'generator', cases)


# -- IPv6 ULA generator ---------------------------------------------------------------------------------
ULA_PAGE = '/ipv6-ula-generator'
ULA_MAC = 'MAC address:'
ULA_SEEN = multi(input=fields(ULA_MAC), result=outs(labels=True))


def ipv6_ula_generator():
    def one(cid, goal, mac, requirement, before=()):
        return case(cid, goal, ULA_PAGE, list(before) + [fill(mac, label=ULA_MAC)],
                    [point('result', requirement, ULA_SEEN)])

    shown = 'The ULA prefix and its first and last routable blocks are shown.'
    cases = [
        case('default', DEFAULT, ULA_PAGE, [],
             [point('result', 'The page opens with a stored example MAC address already turned into a ULA.', ULA_SEEN)]),
        one('colon', 'Type 00:1A:2B:3C:4D:5E.', '00:1A:2B:3C:4D:5E', shown),
        one('dash', 'Type 00-1A-2B-3C-4D-5E.', '00-1A-2B-3C-4D-5E', 'Dashes are accepted and change the result.'),
        one('upper', 'Type AA:BB:CC:DD:EE:FF.', 'AA:BB:CC:DD:EE:FF', shown),
        one('lower', 'Type aa:bb:cc:dd:ee:ff.', 'aa:bb:cc:dd:ee:ff', 'The typed text is used as typed, so case changes the result.'),
        one('short', 'Type 00:1A:2B.', '00:1A:2B', 'A three-byte value is accepted.'),
        one('later-hour', 'Let one hour pass, then type 00:1A:2B:3C:4D:5E.', '00:1A:2B:3C:4D:5E',
            'The current time is part of the result.', [clock(3600)]),
        one('later-day', 'Let one day pass, then type 00:1A:2B:3C:4D:5E.', '00:1A:2B:3C:4D:5E',
            'A different time gives a different result.', [clock(86400)]),
    ]
    for cid, goal, text in (('refused', 'Type text that is not a MAC address.', 'not a mac'),
                            ('too-short', 'Type 00:1A.', '00:1A')):
        cases.append(case(cid, goal, ULA_PAGE, [fill(text, label=ULA_MAC)],
                          [point('message', 'An invalid MAC address is flagged with a message and no ULA is shown.',
                                 lines(start=ULA_MAC), ['colon/result'])]))
    return episode('ipv6-ula-generator', 'generator', cases)


# -- Random port generator ------------------------------------------------------------------------------
PORT_PAGE = '/random-port-generator'
CLIP, BLOCK0 = {'from': 'clipboard'}, {'from': 'block', 'index': 0}
PORT = ('(10(2[4-9]|[3-9][0-9])|1[1-9][0-9]{2}|[2-9][0-9]{3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])')
PORT_SEEN = shape('clipboard', patterns={'in_range': PORT}, only_patterns=True)


def random_port_generator():
    said = 'The copied port is a whole number from 1024 to 65535.'
    cases = [
        case('copy', 'Press Copy.', PORT_PAGE, [click('Copy')], [point('port', said, PORT_SEEN)]),
        case('refresh', 'Press Copy, then Refresh and Copy again.', PORT_PAGE, [click('Copy'), remember(CLIP), click('Refresh'), click('Copy')],
             [point('port', said + ' Refresh gives another port.', multi(port=PORT_SEEN, changed=changed(CLIP)))]),
        case('refresh-again', 'Press Copy, then Refresh three times and Copy again.', PORT_PAGE,
             [click('Copy'), remember(CLIP), click('Refresh'), click('Refresh'), click('Refresh'), click('Copy')],
             [point('port', said + ' Refresh gives another port.', multi(port=PORT_SEEN, changed=changed(CLIP)))]),
    ]
    return episode('random-port-generator', 'generator', cases)


def build():
    return [ipv4_subnet_calculator(), ipv4_address_converter(), ipv4_range_expander(), mac_address_generator(),
            ipv6_ula_generator(), random_port_generator()]

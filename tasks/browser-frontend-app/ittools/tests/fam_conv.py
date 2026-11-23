'''Program episodes: JSON diff, Markdown to HTML and the Docker run to Docker compose converter.'''
import json

from pbuild import NL, bind, blocks, case, click, fields, fill, lines, multi, point, switch, toggles, episode

DEFAULT = 'Open the page without typing.'
BT = chr(96)
BS = chr(92)
QUOTE = chr(34)
APOS = chr(39)
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)


def j(value):
    return json.dumps(value, ensure_ascii=False)


# -- JSON diff ------------------------------------------------------------------------------------------
DIFF_PAGE = '/json-diff'
LEFT, RIGHT = 'Your first JSON', 'Your JSON to compare'
DIFF_SEEN = multi(inputs=fields(LEFT, RIGHT), switches=toggles(), result=lines(start=RIGHT))
ONLY = 0


def json_diff():
    def one(cid, goal, left, right, requirement, after=(), requires=()):
        steps = [fill(left, label=LEFT), fill(right, label=RIGHT)] + list(after)
        return case(cid, goal, DIFF_PAGE, steps, [point('result', requirement, DIFF_SEEN, requires)])

    shown = 'The two documents are compared and every difference is marked.'
    base = {'name': 'box', 'size': 3, 'tags': ['a', 'b'], 'inner': {'x': 1, 'y': [1, 2]}}
    other = {'name': 'box', 'size': 4, 'tags': ['a', 'c', 'd'], 'inner': {'x': 1, 'y': [1, 3], 'z': None}}
    json5 = NL.join(['{', '  // note', '  a: 1,', '  b: [2,],', '}'])
    rows = [
        ('changed', 'Type two objects that differ in one value.', j({'a': 1, 'b': 2}), j({'a': 1, 'b': 3}), shown),
        ('same', 'Type two equal documents.', j(base), j(base), 'Two equal documents are reported as the same.'),
        ('key-order', 'Type two objects with the same keys in another order.', j({'a': 1, 'b': 2}), j({'b': 2, 'a': 1}), 'The order of the keys does not matter.'),
        ('added', 'Type an object and the same object with one more key.', j({'a': 1}), j({'a': 1, 'b': 2}), 'A key that only the second document has is marked as added.'),
        ('removed', 'Type an object and the same object with one key less.', j({'a': 1, 'b': 2}), j({'a': 1}), 'A key that only the first document has is marked as removed.'),
        ('replaced', 'Type two objects with no key in common.', j({'a': 1}), j({'b': 2}), 'Every key is marked as removed or added.'),
        ('nested', 'Type two nested documents with changes at several depths.', j(base), j(other), shown),
        ('deep', 'Type two documents nested five levels deep that differ at the bottom.', j({'a': {'b': {'c': {'d': {'e': 1}}}}}), j({'a': {'b': {'c': {'d': {'e': 2}}}}}), shown),
        ('array-change', 'Type two lists that differ in one item.', j([1, 2, 3]), j([1, 5, 3]), shown),
        ('array-longer', 'Type a list and a longer list.', j([1]), j([1, 2, 3]), 'Extra items of the second list are marked as added.'),
        ('array-shorter', 'Type a list and a shorter list.', j([1, 2, 3]), j([1]), 'Missing items of the second list are marked as removed.'),
        ('array-objects', 'Type two lists of objects where one object changes and one is new.', j([{'id': 1, 'n': 'a'}, {'id': 2, 'n': 'b'}]), j([{'id': 1, 'n': 'a'}, {'id': 2, 'n': 'c'}, {'id': 3}]), shown),
        ('object-to-value', 'Type a document where an object becomes a number.', j({'a': {'x': 1}}), j({'a': 5}), shown),
        ('array-to-object', 'Type a document where a list becomes an object.', j({'a': [1]}), j({'a': {'x': 1}}), shown),
        ('null', 'Type a document where null becomes a number.', j({'a': None}), j({'a': 1}), shown),
        ('number-string', 'Type a document where a number becomes a text.', j({'a': 1}), j({'a': '1'}), 'A number and a text with the same digits are different.'),
        ('booleans', 'Type two documents where one boolean flips.', j({'a': True, 'b': False}), j({'a': False, 'b': False}), shown),
        ('scalars', 'Type 1 and 2.', '1', '2', shown),
        ('strings', 'Type two different texts.', j('old'), j('new'), shown),
        ('root-types', 'Type a list and an object.', j([1]), j({'a': 1}), shown),
        ('empty-containers', 'Type an empty object and an empty list.', '{}', '[]', shown),
        ('unicode', 'Type documents with non-Latin text.', j({'w': UNI}), j({'w': 'other'}), shown),
        ('json5', 'Type JSON5 with unquoted keys and a comment, and the same data as plain JSON.', json5, j({'a': 1, 'b': [2]}), 'JSON5 syntax is accepted and read as the data it stands for.'),
        ('long-text', 'Type two long texts that differ at the end.', j({'t': 'x' * 200 + 'a'}), j({'t': 'x' * 200 + 'b'}), shown),
    ]
    cases = [case('default', DEFAULT, DIFF_PAGE, [], [point('result', 'The page opens with both fields empty and no comparison.', DIFF_SEEN)])]
    cases += [one(*row) for row in rows]
    only = 'Only the parts that differ stay in the comparison.'
    cases += [
        one('only-changed', 'Type two documents with several differences and turn on Only show differences.', j(base), j(other), only, [switch(ONLY)]),
        one('only-same', 'Type two equal documents and turn on Only show differences.', j(base), j(base), 'Equal documents are still reported as the same.', [switch(ONLY)]),
        one('only-array', 'Type two lists and turn on Only show differences.', j([1, 2, 3, 4]), j([1, 9, 3]), only, [switch(ONLY)]),
        one('only-added-removed', 'Type two objects with an added and a removed key and turn on Only show differences.', j({'a': 1, 'b': 2}), j({'b': 2, 'c': 3}), only, [switch(ONLY)]),
        one('only-scalar', 'Type 1 and 2 and turn on Only show differences.', '1', '2', 'Two different numbers are still compared.', [switch(ONLY)]),
        one('only-off-again', 'Turn Only show differences on and off again.', j(base), j(other), 'Turning the switch off shows the whole comparison again.', [switch(ONLY), switch(ONLY)]),
    ]
    for cid, goal, left, right in (
        ('bad-left', 'Type text that is not JSON as the first document.', 'not json', j({'a': 1})),
        ('bad-right', 'Type text that is not JSON as the second document.', j({'a': 1}), 'not json'),
        ('both-bad', 'Type text that is not JSON in both fields.', 'nope', 'nada'),
        ('half-open', 'Type a JSON object that is never closed.', '{a:', j({'a': 1})),
    ):
        cases.append(one(cid, goal, left, right, 'A document that cannot be read is flagged with a message and no comparison is shown.', (), ['changed/result']))
    for cid, goal, left, right in (
        ('empty-left', 'Leave the first document empty.', '', j({'a': 1})),
        ('empty-right', 'Leave the second document empty.', j({'a': 1}), ''),
    ):
        cases.append(one(cid, goal, left, right, 'With one document missing no comparison is shown.', (), ['changed/result']))
    return episode('json-diff', 'diff', bind(cases, {'only-off-again': 'only-changed/result'}))


# -- Markdown to HTML -----------------------------------------------------------------------------------
MD_PAGE = '/markdown-to-html'
MD_LABEL = 'Your Markdown to convert:'
MD_SEEN = multi(input=fields(MD_LABEL), html=blocks(allow_empty=True))


def markdown_to_html():
    def one(cid, goal, text, requirement='The Markdown is shown as HTML.'):
        return case(cid, goal, MD_PAGE, [fill(text, label=MD_LABEL)], [point('html', requirement, MD_SEEN)])

    fence = BT * 3
    rows = [
        ('headings', 'Type six heading levels.', NL.join(['# One', '## Two', '### Three', '#### Four', '##### Five', '###### Six'])),
        ('setext', 'Type two headings underlined with equals signs and dashes.', NL.join(['Title', '=====', '', 'Sub', '---'])),
        ('paragraphs', 'Type two paragraphs.', NL.join(['first paragraph', '', 'second paragraph'])),
        ('soft-break', 'Type two lines without a blank line.', NL.join(['line one', 'line two'])),
        ('hard-break', 'Type a line that ends with two spaces and a second line.', 'line one  ' + NL + 'line two'),
        ('backslash-break', 'Type a line that ends with a backslash and a second line.', 'line one' + BS + NL + 'line two'),
        ('emphasis', 'Type emphasis written four ways.', '*em* and **strong** and ***both*** and _under_ and __double__'),
        ('strike', 'Type text between double tildes.', '~~gone~~ and kept'),
        ('inline-code', 'Type inline code with a less-than sign.', 'use ' + BT + 'x < y' + BT + ' here'),
        ('code-fenced', 'Type a fenced code block with a language.', NL.join([fence + 'js', 'const a = 1;', fence])),
        ('code-plain', 'Type a fenced code block without a language.', NL.join([fence, 'plain <b>text</b>', fence])),
        ('code-indented', 'Type an indented code block.', NL.join(['    indented code', '    more'])),
        ('bullets', 'Type a bullet list of three items.', NL.join(['- one', '- two', '- three'])),
        ('plus-list', 'Type a list started with plus signs.', NL.join(['+ one', '+ two'])),
        ('ordered', 'Type a numbered list.', NL.join(['1. one', '2. two', '10. ten'])),
        ('ordered-start', 'Type a numbered list that starts at three.', NL.join(['3. three', '4. four'])),
        ('ordered-paren', 'Type a numbered list with closing parentheses.', NL.join(['1) one', '2) two'])),
        ('nested', 'Type a list nested three levels deep.', NL.join(['- a', '  - b', '    - c', '- d'])),
        ('loose-list', 'Type a list with a blank line between items.', NL.join(['- a', '', '- b'])),
        ('task-list', 'Type a task list.', NL.join(['- [ ] todo', '- [x] done'])),
        ('blockquote', 'Type a quote with a nested quote.', NL.join(['> quote', '> more', '>', '> > nested'])),
        ('link', 'Type a link with a title.', '[text](https://example.org/a?b=1&c=2 ' + QUOTE + 'title' + QUOTE + ')'),
        ('ref-link', 'Type a link by reference.', NL.join(['[ref][1]', '', '[1]: https://example.org'])),
        ('autolink', 'Type an address between angle brackets.', '<https://example.org>'),
        ('bare-url', 'Type an address with no markup.', 'see https://example.org now'),
        ('image', 'Type an image.', '![alt text](https://example.org/i.png)'),
        ('rule', 'Type a horizontal rule between two paragraphs.', NL.join(['a', '', '---', '', 'b'])),
        ('table', 'Type a table with a centered column.', NL.join(['| a | b |', '|---|:-:|', '| 1 | 2 |'])),
        ('html-inline', 'Type text with an inline HTML tag.', 'plain <b>bold</b> text'),
        ('html-block', 'Type an HTML block.', '<div>x</div>'),
        ('script', 'Type a script element.', '<script>alert(1)</script>'),
        ('entities', 'Type text with entities and bare symbols.', 'a &amp; b &lt; c & d'),
        ('escapes', 'Type text with an escaped asterisk.', BS + '*not em' + BS + '*'),
        ('specials', 'Type angle brackets, an ampersand and a quote.', '< > & ' + QUOTE),
        ('unicode', 'Type text with non-Latin characters.', UNI),
        ('emoji', 'Type an emoji.', 'smile ' + chr(128512)),
        ('heading-markup', 'Type a heading with emphasis and a link inside.', '## A *fine* [page](https://example.org)'),
        ('code-in-list', 'Type a list item that holds a code block.', NL.join(['- item', '', '      code', '', '- next'])),
        ('long-line', 'Type one very long line.', 'word ' * 60),
        ('blank', 'Type only spaces.', '   '),
    ]
    cases = [case('default', DEFAULT, MD_PAGE, [], [point('html', 'The page opens with an empty input and no HTML.', MD_SEEN)])]
    cases += [one(*row) for row in rows]
    return episode('markdown-to-html', 'converter', bind(cases, {'blank': 'headings/html'}))


# -- Docker run to Docker compose -----------------------------------------------------------------------
DOCKER_PAGE = '/docker-run-to-docker-compose-converter'
DOCKER_LABEL = 'Your docker run command:'
DOCKER_SEEN = multi(input=fields(DOCKER_LABEL), compose=blocks(allow_empty=True), notes=lines(start=DOCKER_LABEL))


def docker_compose():
    def one(cid, goal, command, requirement='The command is turned into a compose file.', requires=()):
        return case(cid, goal, DOCKER_PAGE, [fill(command, label=DOCKER_LABEL)], [point('compose', requirement, DOCKER_SEEN, requires)])

    rows = [
        ('image-only', 'Type docker run nginx.', 'docker run nginx'),
        ('tag', 'Type an image with a tag.', 'docker run nginx:1.25-alpine'),
        ('registry', 'Type an image from a private registry with a port.', 'docker run registry.example.com:5000/team/app:2.0'),
        ('name-detach', 'Type a detached container with a name.', 'docker run -d --name web nginx'),
        ('ports', 'Type two published ports.', 'docker run -p 8080:80 -p 8443:443/tcp nginx'),
        ('udp', 'Type a UDP port.', 'docker run -p 5353:53/udp dns'),
        ('host-ip', 'Type a port bound to the loopback address.', 'docker run -p 127.0.0.1:8080:80 nginx'),
        ('expose', 'Type an exposed port.', 'docker run --expose 3000 node'),
        ('env', 'Type two environment variables, one with a space.', 'docker run -e MODE=prod -e ' + APOS + 'GREETING=hello world' + APOS + ' app'),
        ('env-file', 'Type an environment file.', 'docker run --env-file ./app.env app'),
        ('volumes', 'Type two volumes, one read only.', 'docker run -v /data:/var/data -v logs:/var/log:ro app'),
        ('mount', 'Type a mount option.', 'docker run --mount type=bind,source=/srv,target=/data app'),
        ('restart', 'Type a restart policy.', 'docker run --restart unless-stopped app'),
        ('network', 'Type a named network.', 'docker run --network my-net app'),
        ('host-network', 'Type the host network.', 'docker run --network host app'),
        ('identity', 'Type a host name, a user and a working directory.', 'docker run --hostname box -u 1000:1000 -w /app app'),
        ('entrypoint', 'Type an entrypoint.', 'docker run --entrypoint /bin/sh alpine'),
        ('command', 'Type a command after the image.', 'docker run alpine sleep 3600'),
        ('command-quoted', 'Type a quoted shell command after the image.', 'docker run alpine sh -c ' + APOS + 'echo hi && sleep 1' + APOS),
        ('privileged', 'Type the privileged flag and two capability options.', 'docker run --privileged --cap-add NET_ADMIN --cap-drop ALL app'),
        ('device', 'Type a device.', 'docker run --device /dev/ttyUSB0:/dev/ttyUSB0 app'),
        ('labels', 'Type two labels written two ways.', 'docker run -l app=web --label tier=front app'),
        ('limits', 'Type a memory limit and a CPU limit.', 'docker run --memory 512m --cpus 1.5 app'),
        ('log-options', 'Type a log driver and a log option.', 'docker run --log-driver json-file --log-opt max-size=10m app'),
        ('dns', 'Type a DNS server and an extra host.', 'docker run --dns 8.8.8.8 --add-host db:10.0.0.5 app'),
        ('tty', 'Type the interactive and terminal flags together.', 'docker run -it ubuntu bash'),
        ('read-only', 'Type the read-only and init flags.', 'docker run --read-only --init app'),
        ('sysctl', 'Type a sysctl and a ulimit.', 'docker run --sysctl net.core.somaxconn=1024 --ulimit nofile=1024:2048 app'),
        ('platform', 'Type a platform.', 'docker run --platform linux/amd64 app'),
        ('everything', 'Type a command with many options.', 'docker run -d --name api -p 3000:3000 -e NODE_ENV=production -v /srv/data:/data --restart always --network backend --memory 256m node:20 npm start'),
        ('continued', 'Type a command split over three lines with backslashes.', 'docker run -d ' + BS + NL + '  -p 80:80 ' + BS + NL + '  nginx'),
        ('spaces', 'Type a command with spaces around it.', '   docker run nginx   '),
        ('uppercase', 'Type the command in capital letters.', 'DOCKER RUN nginx'),
        ('unicode', 'Type an environment variable with non-Latin text.', 'docker run -e NAME=' + APOS + UNI + APOS + ' app'),
    ]
    cases = [case('default', DEFAULT, DOCKER_PAGE, [], [point('compose', 'The page opens with a sample command already converted.', DOCKER_SEEN)])]
    cases += [one(*row) for row in rows]
    partial = 'The page shows what it makes of options it cannot translate.'
    for cid, goal, command in (
        ('rm', 'Type the remove flag.', 'docker run --rm app'),
        ('pull', 'Type a pull policy.', 'docker run --pull always app'),
        ('unknown-flag', 'Type a flag that does not exist.', 'docker run --bogus-flag app'),
        ('sig-proxy', 'Type a signal proxy option.', 'docker run --sig-proxy=false app'),
        ('healthcheck', 'Type a health check with an interval.', 'docker run --health-cmd ' + APOS + 'curl -f http://localhost' + APOS + ' --health-interval 30s app'),
    ):
        cases.append(one(cid, goal, command, partial))
    for cid, goal, command in (
        ('no-run', 'Type docker ps.', 'docker ps'),
        ('words', 'Type two words that are not a command.', 'hello world'),
        ('open-quote', 'Type a command with a quote that is never closed.', 'docker run -e ' + APOS + 'A=1 nginx'),
        ('no-image', 'Type docker run with no image.', 'docker run'),
        ('empty', 'Clear the command.', ''),
    ):
        cases.append(one(cid, goal, command, 'A command that cannot be converted shows no compose file.', ['image-only/compose']))
    saved = multi(file={'type': 'download', 'parts': ['name', 'text']}, compose=blocks())
    said = 'The download button saves the compose file shown as docker-compose.yml.'
    cases.append(case('download-default', 'Press Download docker-compose.yml without typing.', DOCKER_PAGE,
                      [click('Download docker-compose.yml')], [point('file', said, saved)]))
    cases.append(case('download-command', 'Type docker run -d --name web -p 8080:80 nginx and press Download docker-compose.yml.', DOCKER_PAGE,
                      [fill('docker run -d --name web -p 8080:80 nginx', label=DOCKER_LABEL), click('Download docker-compose.yml')],
                      [point('file', said, saved, ['name-detach/compose'])]))
    return episode('docker-run-to-docker-compose-converter', 'converter', cases)


def build():
    return [json_diff(), markdown_to_html(), docker_compose()]

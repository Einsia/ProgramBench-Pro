'''Program episodes: benchmark builder, device information, git and regex cheat sheets, MIME types and emoji picker.'''
from pbuild import bind, blocks, case, choose, click, clip, clock, controls, copy_after, fields, fill, lines, multi, point, press, reload, wait, episode

DEFAULT = 'Open the page without typing.'
INPUTS = {'type': 'inputs'}
APOS = chr(39)
BS = chr(92)
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412)


# -- Benchmark builder ----------------------------------------------------------------------------------
BENCH_PAGE = '/benchmark-builder'
MEASURE = 'Set your measure...'
SUITE = 'Suite name'
UNIT = 'Unit'
BENCH_SEEN = multi(inputs=INPUTS, table=lines(skip=2))
BENCH_COPY = multi(copied=clip(), table=lines(skip=2))


def val(n, value):
    return fill(str(value), placeholder=MEASURE, nth=n)


def name(n, value):
    return fill(value, label=SUITE, nth=n)


def benchmark_builder():
    def one(cid, goal, steps, requirement, seen=BENCH_SEEN):
        return case(cid, goal, BENCH_PAGE, steps, [point('table', requirement, seen)])

    rank = 'The suites are ranked by their mean and each shows its samples, mean and variance.'
    cases = [one('default', DEFAULT, [], 'The page opens with two example suites already ranked.')]
    rows = [
        ('unit-ms', 'Type the unit ms.', [fill('ms', label=UNIT)], 'The unit is added to every mean and variance.'),
        ('unit-spaces', 'Type the unit ms with spaces around it.', [fill('  ms  ', label=UNIT)], 'Spaces around the unit are ignored.'),
        ('unit-unicode', 'Type a unit with a non-Latin letter.', [fill(chr(181) + 's', label=UNIT)], 'Any text can be used as the unit.'),
        ('unit-long', 'Type the unit milliseconds.', [fill('milliseconds', label=UNIT)], 'A long unit is added as typed.'),
        ('edit-first', 'Set the first measure of the first suite to 50.', [val(0, 50)], rank),
        ('edit-all', 'Set the four measures to 1, 2, 3 and 4.', [val(0, 1), val(1, 2), val(2, 3), val(3, 4)], rank),
        ('order-flip', 'Set the first suite to 100 and 200 and the second suite to 10 and 20.', [val(0, 100), val(1, 200), val(2, 10), val(3, 20)], 'The suite with the lower mean moves to the first place and the other shows its difference and ratio.'),
        ('equal-means', 'Set all four measures to 10.', [val(i, 10) for i in range(4)], 'Suites with the same mean show no difference and no ratio.'),
        ('best-zero', 'Set the first suite to 0 and 0 and the second suite to 5 and 5.', [val(0, 0), val(1, 0), val(2, 5), val(3, 5)], 'A best mean of zero gives an infinite ratio.'),
        ('negative', 'Set the first measure of the first suite to -5.', [val(0, -5)], rank),
        ('decimals', 'Set the first suite to 1.2345 and 2.3456.', [val(0, '1.2345'), val(1, '2.3456')], 'Means and variances are rounded to three decimals.'),
        ('decimals-unit', 'Type the unit ms and set the first suite to 1.2345 and 2.3456.', [fill('ms', label=UNIT), val(0, '1.2345'), val(1, '2.3456')], 'The unit follows each rounded figure.'),
        ('rename-first', 'Rename the first suite to Alpha.', [name(0, 'Alpha')], 'The new name is shown in the ranking.'),
        ('rename-second', 'Rename the second suite to Beta.', [name(1, 'Beta')], 'The new name is shown in the ranking.'),
        ('rename-empty', 'Clear the name of the first suite.', [name(0, '')], 'A suite with no name is still ranked.'),
        ('rename-unicode', 'Rename the first suite with non-Latin characters.', [name(0, UNI)], 'Non-Latin names are shown as typed.'),
        ('rename-same', 'Give both suites the name Same.', [name(0, 'Same'), name(1, 'Same')], 'Two suites can share a name.'),
        ('add-measure', 'Press Add a measure under the first suite and type 15.', [click('Add a measure'), val(2, 15)], 'The new measure is counted in the first suite.'),
        ('add-measure-empty', 'Press Add a measure under the first suite.', [click('Add a measure')], 'A new measure with no value is not counted.'),
        ('add-measure-second', 'Press Add a measure under the second suite and type 20.', [click('Add a measure', nth=1), val(4, 20)], 'The new measure is counted in the second suite.'),
        ('add-measure-twice', 'Press Add a measure twice under the first suite and type 1 and 2.', [click('Add a measure'), click('Add a measure'), val(2, 1), val(3, 2)], 'Both new measures are counted in the first suite.'),
        ('delete-first-measure', 'Press the delete button of the first measure.', [copy_after(MEASURE, 0)], 'The first measure of the first suite is removed from the suite.'),
        ('delete-last-measure', 'Press the delete button of the last measure.', [copy_after(MEASURE, 3)], 'The last measure of the second suite is removed from the suite.'),
        ('delete-both', 'Press the delete button of the first measure twice.', [copy_after(MEASURE, 0), copy_after(MEASURE, 0)], 'A suite with no measure is shown with no samples.'),
        ('delete-all', 'Delete every measure of both suites.', [copy_after(MEASURE, 0), copy_after(MEASURE, 0), copy_after(MEASURE, 0), copy_after(MEASURE, 0)], 'Suites with no measure show zero for every figure.'),
        ('clear-measure', 'Clear the first measure.', [val(0, '')], 'A measure with no value is not counted.'),
        ('enter-adds', 'Type 7 in the last measure of the first suite and press Enter.', [val(1, 7), press('Enter')], 'Enter in the last measure adds a new empty measure.'),
        ('enter-moves', 'Type 7 in the first measure and press Enter.', [val(0, 7), press('Enter')], 'Enter in another measure moves to the next one.'),
        ('add-suite-first', 'Press Add suite under the first suite.', [click('Add suite')], 'A new suite is inserted after the first suite.'),
        ('add-suite-last', 'Press Add suite under the last suite.', [click('Add suite', nth=1)], 'A new suite is added at the end.'),
        ('add-suite-fill', 'Add a suite after the first one, name it Middle and give it the value 3.', [click('Add suite'), name(1, 'Middle'), val(2, 3)], 'The new suite is ranked with the others.'),
        ('rank-three', 'Add a suite after the first one and give it the value 30.', [click('Add suite'), val(2, 30)], 'Three suites are ranked and each shows its distance from the best one.'),
        ('add-two-suites', 'Add a suite after the first one and another at the end.', [click('Add suite'), click('Add suite', nth=2)], 'Each new suite is named after the number of suites.'),
        ('delete-suite-first', 'Press Delete suite under the first suite.', [click('Delete suite')], 'The first suite is removed and only one is left.'),
        ('delete-suite-second', 'Press Delete suite under the second suite.', [click('Delete suite', nth=1)], 'The second suite is removed and only one is left.'),
        ('delete-then-add', 'Delete the first suite and add a suite after the one left.', [click('Delete suite'), click('Add suite')], 'A suite can be added again after one was deleted.'),
        ('reset', 'Press Reset suites.', [click('Reset suites')], 'Reset gives two empty suites.'),
        ('reset-after-edit', 'Type the unit ms, change a measure and press Reset suites.', [fill('ms', label=UNIT), val(0, 99), click('Reset suites')], 'Reset empties the suites and keeps the unit.'),
        ('fill-after-reset', 'Press Reset suites, press Add a measure and type 4.', [click('Reset suites'), click('Add a measure'), val(0, 4)], 'A measure can be added to an emptied suite.'),
        ('stored-unit', 'Type the unit ms and reload the page.', [fill('ms', label=UNIT), reload()], 'The unit is kept after reloading the page.'),
        ('stored-edit', 'Set the first measure to 42 and reload the page.', [val(0, 42), reload()], 'The measures are kept after reloading the page.'),
        ('stored-reset', 'Press Reset suites and reload the page.', [click('Reset suites'), reload()], 'The emptied suites are kept after reloading the page.'),
        ('stored-suite', 'Add a suite, name it Kept and reload the page.', [click('Add suite'), name(1, 'Kept'), reload()], 'The added suite is kept after reloading the page.'),
        ('stored-delete', 'Delete the first suite and reload the page.', [click('Delete suite'), reload()], 'The deleted suite stays deleted after reloading the page.'),
    ]
    for cid, goal, steps, requirement in rows:
        cases.append(one(cid, goal, steps, requirement))
    copies = [
        ('copy-markdown', 'Press Copy as markdown table.', [click('Copy as markdown table')], 'The ranking is copied as a markdown table.'),
        ('copy-bullets', 'Press Copy as bullet list.', [click('Copy as bullet list')], 'The ranking is copied as a bullet list.'),
        ('copy-markdown-unit', 'Type the unit ms, set a measure to 50 and press Copy as markdown table.', [fill('ms', label=UNIT), val(0, 50), click('Copy as markdown table')], 'The unit and the differences are copied in the table.'),
        ('copy-bullets-unit', 'Type the unit ms, set a measure to 50 and press Copy as bullet list.', [fill('ms', label=UNIT), val(0, 50), click('Copy as bullet list')], 'The unit and the differences are copied in the list.'),
        ('copy-markdown-three', 'Add a suite with the value 30 and press Copy as markdown table.', [click('Add suite'), val(2, 30), click('Copy as markdown table')], 'All three suites are copied in the table.'),
        ('copy-bullets-three', 'Add a suite with the value 30 and press Copy as bullet list.', [click('Add suite'), val(2, 30), click('Copy as bullet list')], 'All three suites are copied in the list.'),
        ('copy-markdown-reset', 'Press Reset suites and then Copy as markdown table.', [click('Reset suites'), click('Copy as markdown table')], 'Suites with no samples are still copied.'),
        ('copy-markdown-pipe', 'Rename the first suite A|B and press Copy as markdown table.', [name(0, 'A|B'), click('Copy as markdown table')], 'A bar in a name is copied as typed.'),
    ]
    for cid, goal, steps, requirement in copies:
        cases.append(one(cid, goal, steps, requirement, BENCH_COPY))
    return episode('benchmark-builder', 'builder', cases)


# -- Device information ---------------------------------------------------------------------------------
def device_information():
    seen = multi(text=lines(skip=2))
    return episode('device-information', 'reference', [
        case('default', DEFAULT, '/device-information', [], [point('text', 'The screen, window and browser details of the device are listed.', seen)]),
    ])


# -- Git and regex cheat sheets -------------------------------------------------------------------------
def git_memo():
    seen = multi(commands=blocks(), text=lines(skip=2, partial=True))
    return episode('git-memo', 'reference', [
        case('default', DEFAULT, '/git-memo', [], [point('commands', 'The page lists the common git commands in code blocks under their headings.', seen)]),
    ])


def regex_memo():
    seen = multi(text=lines(skip=2, partial=True))
    return episode('regex-memo', 'reference', [
        case('default', DEFAULT, '/regex-memo', [], [point('cheatsheet', 'The page lists the regular expression syntax in tables with links to further reading.', seen)]),
    ])


# -- MIME types -----------------------------------------------------------------------------------------
MIME_PAGE = '/mime-types'
PICK = 'Select your mimetype here... (ex: application/pdf)'
FROM_MIME = 'Know which file extensions are associated to a mime-type'
TO_MIME = 'Know which mime type is associated to a file extension'
MIME_FOUND = multi(found=lines(start=FROM_MIME, stop='File extension to mime type', partial=True))
EXT_FOUND = multi(found=lines(start=TO_MIME, stop='Mime types', partial=True))


def mime_types():
    def by_mime(cid, mime):
        return case(cid, 'Choose the MIME type %s.' % mime, MIME_PAGE, [choose(PICK, mime, search=mime)],
                    [point('extensions', 'The file extensions of the chosen MIME type are listed.', MIME_FOUND)])

    def by_ext(cid, ext):
        return case(cid, 'Choose the extension .%s.' % ext, MIME_PAGE, [choose(PICK, '.' + ext, search='.' + ext, current_nth=1)],
                    [point('mime', 'The MIME type of the chosen extension is shown.', EXT_FOUND)])

    both = multi(extensions=lines(start=FROM_MIME, stop='File extension to mime type', partial=True), mime=lines(start=TO_MIME, stop='Mime types', partial=True))
    cases = [case('default', DEFAULT, MIME_PAGE, [], [
        point('page', 'The page opens with two empty pickers and no result.', multi(head=lines(skip=2, stop='Mime types', partial=True))),
        point('table', 'The page lists every known MIME type with its extensions in a table.', multi(table=lines(start='Extensions', partial=True)))])]
    for cid, mime in (('pdf', 'application/pdf'), ('png', 'image/png'), ('jpeg', 'image/jpeg'), ('mp3', 'audio/mpeg'), ('text', 'text/plain'),
                      ('json', 'application/json'), ('zip', 'application/zip'), ('html', 'text/html'), ('mp4', 'video/mp4'),
                      ('octet', 'application/octet-stream'), ('svg', 'image/svg+xml'), ('xml', 'application/xml'),
                      ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                      ('js', 'application/javascript'), ('css', 'text/css'), ('gif', 'image/gif'), ('csv', 'text/csv'), ('woff2', 'font/woff2')):
        cases.append(by_mime('mime-' + cid, mime))
    for ext in ('pdf', 'png', 'jpg', 'jpeg', 'json', 'mp3', 'html', 'zip', 'csv', 'svg', 'txt', 'js', 'css', 'xml', 'docx', 'woff2', 'md', 'yaml', 'wasm', 'ico'):
        cases.append(by_ext('ext-' + ext, ext))
    cases.append(case('both', 'Choose application/pdf in the first picker and .pdf in the second.', MIME_PAGE,
                      [choose(PICK, 'application/pdf', search='application/pdf'), choose(PICK, '.pdf', search='.pdf')],
                      [point('both', 'Both pickers show their result at the same time.', both)]))
    return episode('mime-types', 'reference', cases)


# -- Emoji picker ---------------------------------------------------------------------------------------
EMOJI_PAGE = '/emoji-picker'
EMOJI_PH = 'Search emojis (e.g. ' + APOS + 'smile' + APOS + ')...'
EMOJI_HEAD = multi(input=fields(EMOJI_PH), head=lines(stop='People & Body', partial=True))
EMOJI_FOUND = multi(input=fields(EMOJI_PH), results=lines(skip=2, partial=True, reading='values'))
GRIN, PIZZA = chr(128512), chr(127829)


def search(query):
    return [fill(query, placeholder=EMOJI_PH), clock(1), wait(0.8)]


def emoji_picker():
    def found(cid, goal, query):
        return case(cid, goal, EMOJI_PAGE, search(query),
                    [point('results', 'Only the emoji that match the search are listed, or No results when none does.', EMOJI_FOUND)])

    def copied(cid, goal, steps, requirement):
        return case(cid, goal, EMOJI_PAGE, steps, [point('copied', requirement, multi(copied=clip()))])

    cases = [case('default', DEFAULT, EMOJI_PAGE, [], [point('groups', 'The page opens with every emoji listed in groups, the first group being Smileys and Emotion.', EMOJI_HEAD)])]
    for cid, goal, query in (
        ('smile', 'Type smile.', 'smile'), ('uppercase', 'Type SMILE in capital letters.', 'SMILE'), ('pizza', 'Type pizza.', 'pizza'),
        ('rocket', 'Type rocket.', 'rocket'), ('thumbs', 'Type thumbs up.', 'thumbs up'), ('exact', 'Type cat with an exact match mark.', APOS + 'cat'),
        ('prefix', 'Type grin with a prefix match mark.', '^grin'), ('code-point', 'Type the code point 0x1f600.', '0x1f600'),
        ('glyph', 'Type the grinning face itself.', GRIN), ('group', 'Type food.', 'food'), ('keyword', 'Type happy.', 'happy'),
        ('typo', 'Type the misspelled word smyle.', 'smyle'), ('country', 'Type japan.', 'japan'), ('no-match', 'Type a search that matches nothing.', 'zzzzqqqq'),
    ):
        cases.append(found(cid, goal, query))
    cases.append(case('cleared', 'Type smile and then clear the search.', EMOJI_PAGE, search('smile') + search(''),
                      [point('groups', 'Clearing the search lists the groups again.', EMOJI_HEAD)]))
    cases += [
        copied('copy-emoji', 'Click the first emoji.', [click(GRIN)], 'Clicking an emoji copies it.'),
        copied('copy-code-point', 'Click the code point of the first emoji.', [click('0x1f600')], 'Clicking a code point copies it.'),
        copied('copy-unicode', 'Click the unicode escape of the first emoji.', [click(BS + 'ud83d' + BS + 'ude00')], 'Clicking a unicode escape copies it.'),
        copied('copy-second', 'Click the code point of the second emoji.', [click('0x1f603')], 'Clicking a code point copies it.'),
        copied('copy-from-search', 'Type pizza and click the pizza emoji.', search('pizza') + [click(PIZZA)], 'An emoji found by a search is copied the same way.'),
        copied('copy-code-from-search', 'Type pizza and click the code point of the pizza emoji.', search('pizza') + [click('0x1f355')], 'A code point found by a search is copied the same way.'),
    ]
    return episode('emoji-picker', 'reference', bind(cases, {'cleared': 'smile/results'}))


def build():
    return [benchmark_builder(), device_information(), git_memo(), regex_memo(), mime_types(), emoji_picker()]

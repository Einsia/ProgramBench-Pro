"""Deterministic Markdown input documents for the serialization and rendering episodes.

Fixtures play two roles:

* SAVE fixtures (families listed in SAVE_FAMILIES) are authored in deliberately NON-canonical forms that the
  reference re-serializes to a *different* canonical form (irregular spacing, alternative markers, lazy
  continuations, odd nesting, unclosed fences, ragged tables). A save or copy-as-Markdown round-trip of one of
  these therefore differs from an echo of the input, so it discriminates a faithful serializer both from a
  candidate that merely copies the input and from one that normalizes differently. Only construct families the
  reference actually normalizes are used for the round-trip.

* RENDER fixtures (families listed in RENDER_FAMILIES) are canonical construct documents whose *rendering* is
  compared through copy-as-HTML and export. They cover the constructs the reference preserves verbatim on save
  (emphasis, inline code, links and images, thematic breaks, math, raw HTML, hard breaks) — which a save
  round-trip cannot discriminate — as well as headings, lists, tables, code and quotes, through the rendering
  channel.

The expected canonical and rendered output is never written here: the record captures whatever the pinned
reference produces and freezes it as the truth, so the fixtures carry no reference-specific knowledge beyond
ordinary Markdown.
"""
from __future__ import annotations

# name -> markdown text. Grouped by family; names are stable identifiers used by the specification.
TEXT: dict[str, str] = {}


def add(name, text):
    assert name not in TEXT, name
    TEXT[name] = text
    return name


# =================================================================================================
# SAVE fixtures: non-canonical inputs the reference re-serializes to a different canonical form.
# =================================================================================================

# ---------------------------------------------------------------- headings (sz-head-*)
add('sz-head-space-after.md', '#     Heading with collapsed spaces\n\nbody\n')
add('sz-head-closed.md', '##   Closed heading   ##\n\nbody\n')
add('sz-head-trailing-ws.md', '# Heading with trailing spaces    \n')
add('sz-head-tabs.md', '#\tTab after the hash\n')
add('sz-head-leading-space.md', '   # Up to three leading spaces\n')
add('sz-head-trailing-hashes.md', '#   Spaced word   #####   \n')
add('sz-head-levels.md', '#  One\n##   Two\n###    Three\n####     Four\n')
add('sz-head-consecutive.md', '# First section\n## Second section\n### Third section\n')
add('sz-head-para-adjacent.md', '# A heading\nparagraph right after with no blank line\n')
add('sz-head-closed-uneven.md', '###  Three open two close  ##\n')
add('sz-head-tab-and-space.md', '##\t  mixed whitespace heading\n')
add('sz-head-unicode.md', '# 日本語の見出し\n## Ещё заголовок\n')

# ---------------------------------------------------------------- bullet lists (sz-bul-*)
add('sz-bul-dash-space.md', '-   first apple\n-   second banana\n-   third cherry\n')
add('sz-bul-star-space.md', '*   red star\n*   green star\n')
add('sz-bul-plus-space.md', '+   one plus\n+   two plus\n')
add('sz-bul-tab.md', '-\ttabbed one\n-\ttabbed two\n')
add('sz-bul-deep-nest.md', '- a\n    - b\n        - c\n            - d\n')
add('sz-bul-nested.md', '- top\n    - nested one\n    - nested two\n- top two\n')
add('sz-bul-blank-between.md', '- one\n\n- two\n- three\n')
add('sz-bul-multiparagraph.md', '- first paragraph\n\n  second paragraph of first item\n- second item\n')
add('sz-bul-mixed-indent.md', '-   spaced marker\n  - two space marker\n')
add('sz-bul-with-code.md', '- item\n\n  ```\n  code in item\n  ```\n- next\n')
add('sz-bul-deep-three.md', '- level one\n   - level two three-space\n      - level three six-space\n')

# ---- expansion: more normalizing bullet cases
add('sz-bul-two-space.md', '-  two space one\n-  two space two\n')
add('sz-bul-star-nested.md', '* top\n    * child one\n    * child two\n* top two\n')
add('sz-bul-plus-nested.md', '+ outer\n    + inner a\n    + inner b\n')
add('sz-bul-para-continuation.md', '- item with\n  a lazy continuation line\n- second item\n')

# ---------------------------------------------------------------- ordered lists (sz-ord-*)
add('sz-ord-dot-space.md', '1.  one\n2.  two\n3.  three\n')
add('sz-ord-paren-space.md', '1)  one paren\n2)  two paren\n')
add('sz-ord-wide-space.md', '1.    alpha\n2.    beta\n3.    gamma\n')
add('sz-ord-deep.md', '1. a\n    1. b\n        1. c\n')
add('sz-ord-nested-bullet.md', '1. first\n    - a\n    - b\n2. second\n')
add('sz-ord-nested-mixed.md', '1. outer\n    1. inner one\n    2. inner two\n2. outer two\n')
add('sz-ord-paren-nested.md', '1) first\n    1) nested one\n2) second\n')
add('sz-ord-tab.md', '1.\ttabbed one\n2.\ttabbed two\n')

# ---------------------------------------------------------------- task lists (sz-task-*)
add('sz-task-upper.md', '- [X] done upper\n- [ ] not done\n')
add('sz-task-nested.md', '- [ ] parent\n    - [x] child done\n    - [ ] child todo\n')
add('sz-task-spacing.md', '- [ ]  spaced task\n- [x]  another spaced\n')
add('sz-task-mixed-upper.md', '- [X] a\n- [ ] b\n- [X] c\n')
add('sz-task-deep.md', '- [ ] top\n    - [x] mid\n        - [ ] deep\n')

# ---------------------------------------------------------------- code blocks (sz-code-*)
add('sz-code-blank-lines.md', '```\n\ncode after blank\n\n```\n')
add('sz-code-no-close.md', '```python\nx = 1\ny = 2\n')
add('sz-code-info-space.md', '```  js  \nconst a = 1\n```\n')
add('sz-code-empty.md', '```\n```\n')
add('sz-code-indented-blank.md', '    line one\n\n    line two\n')
add('sz-code-tilde-info.md', '~~~   python   \nprint(1)\n~~~\n')
add('sz-code-long-info-space.md', '````   text   \ncode with ``` inside\n````\n')
add('sz-code-trailing-blank-in-fence.md', '```\ncontent line\n\n\n```\n')

# ---------------------------------------------------------------- blockquotes (sz-quote-*)
add('sz-quote-lazy.md', '> lazy continuation\nstill the quote\n')
add('sz-quote-nested.md', '> outer\n> > inner\n> back to outer\n')
add('sz-quote-deep.md', '> a\n> > b\n> > > c\n')
add('sz-quote-heading-inside.md', '> # quoted heading\n> body paragraph\n')
add('sz-quote-nospace.md', '>no space here\n>second line\n')
add('sz-quote-lazy-multi.md', '> first line of quote\nlazily continued\nand more\n')
add('sz-quote-nested-lazy.md', '> outer start\n> > inner start\ninner lazy line\n')
add('sz-quote-code-inside.md', '> text before\n> ```\n> fenced in quote\n> ```\n')

# ---------------------------------------------------------------- tables (sz-table-*) — all reformat
add('sz-table-basic.md', '| A | B |\n| - | - |\n| 1 | 2 |\n| 3 | 4 |\n')
add('sz-table-align.md', '| L | C | R |\n|:--|:-:|--:|\n| a | b | c |\n')
add('sz-table-ragged.md', '| A | B | C |\n|---|---|---|\n| 1 | 2 |\n')
add('sz-table-inline.md', '| name | value |\n|------|-------|\n| **bold** | `code` |\n')
add('sz-table-escaped-pipe.md', '| col | note |\n|-----|------|\n| a | x \\| y |\n')
add('sz-table-wide-cells.md', '| short | a very long header cell |\n|---|---|\n| x | y |\n')
add('sz-table-min.md', '| x |\n|---|\n| 1 |\n')
add('sz-table-empty-cells.md', '| a | b |\n|---|---|\n|  |  |\n| 1 |  |\n')
add('sz-table-no-outer-pipes.md', 'a | b\n--- | ---\n1 | 2\n')
add('sz-table-colon-variants.md', '| a | b | c | d |\n|:-|:-:|-:|-|\n| 1 | 2 | 3 | 4 |\n')
add('sz-table-uneven-width.md', '| h1 | header two is wide |\n|:---|:---|\n| x | y |\n| longer cell | z |\n')
add('sz-table-align-right.md', '| item | qty |\n|---|--:|\n| apples | 3 |\n| pears | 12 |\n')

# ---------------------------------------------------------------- whitespace & structure (sz-ws-*)
add('sz-ws-multiple-blanks.md', 'first\n\n\n\nsecond\n\n\n\nthird\n')
add('sz-ws-leading-blanks.md', '\n\n\nfirst line after blanks\n')
add('sz-ws-only-spaces-line.md', 'first paragraph\n   \nsecond paragraph\n')
add('sz-ws-trailing-blanks.md', 'content line\n\n\n\n')
add('sz-ws-para-then-heading.md', 'a paragraph of text\n# then a heading with no blank line\n')
add('sz-ws-mixed-constructs.md',
    '#   Doc heading\n\n'
    '-   loose bullet\n-   second\n\n'
    '1)  ordered one\n2)  ordered two\n\n'
    '> a quote\nlazily continued\n\n'
    '| a | b |\n|---|---|\n| 1 | 2 |\n')
add('sz-ws-heading-list-adjacent.md', '## Items\n-   one\n-   two\n')

# =================================================================================================
# RENDER fixtures: canonical construct documents compared through copy-as-HTML and export.
# =================================================================================================

# headings & rules
add('rd-headings.md', '# Heading one\n\n## Heading two\n\n### Heading three\n\nA paragraph.\n')
add('rd-heading-levels.md', '# One\n\n## Two\n\n### Three\n\n#### Four\n\n##### Five\n\n###### Six\n')
add('rd-hr.md', 'before the rule\n\n---\n\nafter the rule\n')
add('rd-heading-inline.md', '# Heading with **bold** and `code`\n')
# emphasis (preserved on save -> rendering discriminates)
add('rd-bold.md', 'This has **bold text** in it.\n')
add('rd-italic.md', 'This has *italic text* in it.\n')
add('rd-strike.md', 'This has ~~struck through~~ text.\n')
add('rd-bold-italic.md', 'This is ***bold and italic*** together.\n')
add('rd-emphasis-mixed.md', 'Text with **bold**, *italic* and ~~strike~~ words.\n')
add('rd-emphasis-nested.md', 'A **bold with *italic* inside** here.\n')
add('rd-emphasis-underscore.md', 'Using __double__ and _single_ underscores.\n')
# inline code & escapes
add('rd-inline-code.md', 'Use `inline code` and `another span` here.\n')
add('rd-inline-code-backtick.md', 'A span with a backtick: ``a ` b`` here.\n')
add('rd-escapes.md', 'Escaped \\*star\\* and \\_underscore\\_ and \\#hash stay literal.\n')
add('rd-hardbreak.md', 'line one with a hard break  \nline two follows\n')
# links & images
add('rd-link.md', 'See [the site](http://example.com) now.\n')
add('rd-link-title.md', 'See [site](http://example.com "A Title") now.\n')
add('rd-link-reference.md', 'See [the ref][id] now.\n\n[id]: http://example.com "Ref Title"\n')
add('rd-autolink.md', 'Visit <http://example.com> directly.\n')
add('rd-image.md', 'An image ![alt text](http://example.com/i.png) here.\n')
add('rd-image-title.md', 'An image ![alt](http://example.com/i.png "Img Title") here.\n')
add('rd-link-in-emphasis.md', 'A [**bold link**](http://x.io) and plain text.\n')
# lists
add('rd-bullet.md', '- first\n- second\n- third\n')
add('rd-ordered.md', '1. one\n2. two\n3. three\n')
add('rd-ordered-start.md', '5. five\n6. six\n7. seven\n')
add('rd-nested.md', '- top one\n  - child a\n  - child b\n- top two\n')
add('rd-task.md', '- [ ] first todo\n- [x] second done\n- [ ] third todo\n')
add('rd-ordered-nested.md', '1. first\n   1. inner one\n   2. inner two\n2. second\n')
# tables
add('rd-table.md', '| Name | Age |\n|:-----|----:|\n| Alice | 30 |\n| Bob | 25 |\n')
add('rd-table-center.md', '| Left | Center | Right |\n|:-----|:------:|------:|\n| a | b | c |\n')
# code
add('rd-code.md', '```python\nprint("hello")\nvalue = 1\n```\n')
add('rd-code-plain.md', '```\nplain code\nsecond line\n```\n')
# quotes
add('rd-quote.md', '> a quote line\n> second line\n')
add('rd-quote-nested.md', '> outer\n>\n> > inner\n')
# math (preserved literally on save -> rendering captures reference form)
add('rd-math-inline.md', 'Inline math $E = mc^2$ here.\n')
add('rd-math-block.md', '$$\n\\int_0^1 x\\,dx\n$$\n')
# raw html
add('rd-html-inline.md', 'Text with <span>inline html</span> here.\n')
# mixed document
add('rd-mixed.md',
    '# Report Title\n\n'
    'Alpha **bold** and *italic* text with `code` and a [link](http://x.io).\n\n'
    '- one\n- two\n\n'
    '1. first\n2. second\n\n'
    '> a quote line\n\n'
    '| a | b |\n|---|---|\n| 1 | 2 |\n')

# =================================================================================================
# GUI episode source documents and export-rendering sources (used by the GUI/editing episodes).
# =================================================================================================
add('gui-para.md', 'Alpha beta gamma delta.\n')
add('gui-items.md', 'First item here.\n\nSecond item here.\n\nThird item here.\n')
add('gui-rich.md', '# Report Title\n\nAlpha **bold** and *italic* text with `code`.\n\n- one\n- two\n\n> a quote line\n')
add('gui-plain.md', 'The quick brown fox jumps over the lazy dog.\n')
add('gui-find.md', 'Alpha line one.\n\nBeta needle here.\n\nGamma line three.\n')

add('render-table.md', '| Name | Age |\n|:-----|----:|\n| Alice | 30 |\n| Bob | 25 |\n')
add('render-nested.md', '- top one\n    - child a\n    - child b\n- top two\n')
add('render-links.md', 'A [site link](http://example.com) and an image ![alt text](http://x.io/i.png) and `inline code`.\n')
add('render-tasks.md', '- [ ] first todo\n- [x] second done\n- [ ] third todo\n')
add('render-code.md', '```python\nprint("hello")\nvalue = 1\n```\n')
add('render-emphasis.md', 'Text with **bold**, *italic* and ~~strike~~ words.\n')
add('render-headings.md', '# Heading one\n\n## Heading two\n\n### Heading three\n\n---\n\nA paragraph.\n')


# =================================================================================================
# Expansion fixtures (same two roles), grouped by the same prefixes so the family globs pick them up.
# =================================================================================================

# SAVE expansion — headings
add('sz-head-closed-many.md', '####   Four level closed   ####\n')
add('sz-head-two-consecutive.md', '## Alpha section\n### Beta section\n')
add('sz-head-trailing-tab.md', '# Heading with a trailing tab\t\n')
add('sz-head-wide-space.md', '###      wide gap heading\n')
# SAVE expansion — ordered lists
add('sz-ord-dot-wide.md', '1.   first wide\n2.   second wide\n')
add('sz-ord-paren-wide.md', '1)   paren wide a\n2)   paren wide b\n')
add('sz-ord-deep-four.md', '1. a\n    1. b\n        1. c\n            1. d\n')
add('sz-ord-nested-bullet-deep.md', '1. first\n    - sub a\n        - sub sub\n2. second\n')
# SAVE expansion — task lists
add('sz-task-upper-only.md', '- [X] all upper one\n- [X] all upper two\n')
add('sz-task-nested-deep.md', '- [ ] a\n    - [ ] b\n        - [x] c\n')
add('sz-task-wide-space.md', '- [ ]   wide spaced\n- [x]   wide spaced two\n')
# SAVE expansion — code blocks
add('sz-code-tilde-no-close.md', '~~~\ncode without a close\n')
add('sz-code-blank-leading.md', '```\n\n\nfirst code line\n```\n')
add('sz-code-info-trailing.md', '```python   \nprint(1)\n```\n')
# SAVE expansion — blockquotes
add('sz-quote-nospace-multi.md', '>line one\n>line two\n>line three\n')
add('sz-quote-nested-deep-lazy.md', '> a\n> > b\nlazy c\n')
add('sz-quote-blank-nested.md', '> outer\n> > inner one\n> > inner two\n> outer back\n')
# SAVE expansion — tables
add('sz-table-three-col.md', '| x | y | z |\n|---|---|---|\n| 1 | 2 | 3 |\n')
add('sz-table-long-content.md', '| key | value |\n|--|--|\n| name | a long value here |\n')
add('sz-table-center-only.md', '| a | b |\n|:-:|:-:|\n| 1 | 2 |\n')
# SAVE expansion — whitespace & structure
add('sz-ws-blanks-around-heading.md', 'para one\n\n\n# A heading\n\n\npara two\n')
add('sz-ws-far-apart.md', 'first paragraph\n\n\n\n\nfar apart paragraph\n')
add('sz-ws-heading-then-list.md', '# Title here\n-   one\n-   two\n')

# RENDER expansion — more canonical construct documents
add('rd-emphasis-in-list.md', '- **bold item**\n- *italic item*\n- ~~struck item~~\n')
add('rd-emphasis-adjacent.md', 'word **bold** then *italic* then normal.\n')
add('rd-strike-bold.md', 'A ~~struck~~ and **bold** mix here.\n')
add('rd-inline-code-multi.md', 'First `one` then `two` then `three` spans.\n')
add('rd-link-multiple.md', 'See [one](http://a.io) and [two](http://b.io) links.\n')
add('rd-image-reference.md', 'An ![img][logo] here.\n\n[logo]: http://x.io/l.png\n')
add('rd-link-and-image.md', 'A [link](http://x.io) and ![img](http://y.io/i.png) together.\n')
add('rd-bullet-long.md', '- first item text\n- second item text\n- third item text\n')
add('rd-task-nested.md', '- [ ] parent\n  - [x] child done\n  - [ ] child todo\n')
add('rd-ordered-bullet-nested.md', '1. first\n   - a\n   - b\n2. second\n')
add('rd-table-three.md', '| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |\n')
add('rd-code-no-lang.md', '```\nno language code\nsecond line\n```\n')
add('rd-quote-multiline.md', '> line one\n> line two\n> line three\n')
add('rd-quote-with-list.md', '> - item one\n> - item two\n')
add('rd-math-multiple.md', 'Both $a$ and $b$ inline here.\n')
add('rd-html-block.md', '<div class="note">\n<p>raw html block</p>\n</div>\n')
add('rd-heading-mixed.md', '# Title\n\nText then a `code` span and **bold**.\n')
add('rd-mixed-two.md',
    '## Section\n\n'
    'A paragraph with a [link](http://x.io) and ~~strike~~.\n\n'
    '- [ ] todo one\n- [x] done two\n\n'
    '```js\nconst x = 1;\n```\n')


def content(entry) -> bytes:
    name = entry['name'] if isinstance(entry, dict) else entry
    if isinstance(entry, dict) and 'text' in entry:
        return entry['text'].encode('utf-8')
    if isinstance(entry, dict) and 'fixture' in entry:
        name = entry['fixture']
    return TEXT[name].encode('utf-8')


# Serialization families (save round-trip and copy-as-Markdown): the reference normalizes each of these.
SAVE_FAMILIES = {
    'headings': [n for n in TEXT if n.startswith('sz-head-')],
    'bullet-lists': [n for n in TEXT if n.startswith('sz-bul-')],
    'ordered-lists': [n for n in TEXT if n.startswith('sz-ord-')],
    'task-lists': [n for n in TEXT if n.startswith('sz-task-')],
    'code-blocks': [n for n in TEXT if n.startswith('sz-code-')],
    'blockquotes': [n for n in TEXT if n.startswith('sz-quote-')],
    'tables': [n for n in TEXT if n.startswith('sz-table-')],
    'whitespace': [n for n in TEXT if n.startswith('sz-ws-')],
}

# Rendering families (copy-as-HTML): canonical construct documents, including constructs preserved verbatim on save.
RENDER_FAMILIES = {
    'headings-rules': [n for n in TEXT if n.startswith(('rd-head', 'rd-hr'))],
    'emphasis': [n for n in TEXT if n.startswith('rd-bold') or n.startswith('rd-italic')
                 or n.startswith('rd-strike') or n.startswith('rd-emphasis') or n == 'rd-bold-italic.md'],
    'inline-code': [n for n in TEXT if n.startswith('rd-inline-code') or n in ('rd-escapes.md', 'rd-hardbreak.md')],
    'links-images': [n for n in TEXT if n.startswith(('rd-link', 'rd-autolink', 'rd-image'))],
    'lists': [n for n in TEXT if n in ('rd-bullet.md', 'rd-ordered.md', 'rd-ordered-start.md', 'rd-nested.md',
                                       'rd-task.md', 'rd-ordered-nested.md')],
    'tables': [n for n in TEXT if n.startswith('rd-table')],
    'code': [n for n in TEXT if n.startswith('rd-code')],
    'quotes': [n for n in TEXT if n.startswith('rd-quote')],
    'math': [n for n in TEXT if n.startswith('rd-math')],
    'html': [n for n in TEXT if n.startswith('rd-html')],
    'mixed': [n for n in TEXT if n == 'rd-mixed.md'],
}

# Backwards-compatible alias (the round-trip build iterates the serialization families).
FAMILIES = SAVE_FAMILIES

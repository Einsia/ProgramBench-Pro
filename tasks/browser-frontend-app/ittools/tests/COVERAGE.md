# IT-Tools coverage

Version 1.0.0, reference IT-Tools 2024.10.22-7ca5933. Exact counts and budgets come from `data/manifest.json`:
122 episodes (89 program, 33 GUI) with 1676 checkpoints and 1868 scoring points, 139 frontend and 1729 backend.
The count comes from distinct behaviors only: every point of a tool page observes a different input, option or state of that tool.

## Coverage

Every tool page of the release is covered by a program episode unless it is listed under the exclusions below. Each checkpoint opens the page in a fresh browser profile, applies its steps and reads the page.

| Tools | Program episodes | Checkpoints | Points |
| --- | ---: | ---: | ---: |
| Hash text, HMAC, basic auth and Base64 text | 4 | 46 | 97 |
| URL, HTML entity, binary, Unicode, NATO, roman numeral, base, case, slug, numeronym, percentage, temperature and text statistics tools | 13 | 90 | 92 |
| JSON, YAML, TOML, XML and CSV converters and the JSON, YAML and XML formatters | 13 | 98 | 98 |
| IPv4 subnet, address and range tools, MAC address and IPv6 ULA generators, random port | 6 | 71 | 73 |
| IBAN, password strength, phone number and user agent parsers | 4 | 77 | 77 |
| Math evaluator, chmod calculator, list converter, lorem ipsum, string obfuscator | 5 | 98 | 98 |
| URL parser, JWT parser, Outlook SafeLink decoder, email normalizer | 4 | 65 | 67 |
| UUID, ULID, token, BIP39, bcrypt, encryption and OTP tools | 7 | 164 | 164 |
| Crontab generator, date-time converter, ETA calculator, chronometer | 4 | 106 | 106 |
| Color converter, regex tester, SQL prettifier, meta tag generator, MAC address lookup | 5 | 143 | 143 |
| JSON diff, Markdown to HTML, Docker run to Docker compose | 3 | 125 | 125 |
| Base64 file converter, QR code, WiFi QR code, SVG placeholder, RSA key pair | 5 | 112 | 112 |
| HTTP status codes, keycode info, PDF signature checker | 3 | 62 | 62 |
| Benchmark builder, device information, git and regex cheat sheets, MIME types, emoji picker | 6 | 118 | 119 |
| Text diff and the HTML WYSIWYG editor | 2 | 77 | 77 |
| Home page and favorites, menu categories, command palette, language, About page | 5 | 85 | 85 |

GUI episodes (a goal for the evaluator and a program companion that reads the state the goal produces):

| Episode | Goals | Points |
| --- | ---: | ---: |
| `gui-favorites` | 5 | 10 |
| `gui-menu` | 4 | 8 |
| `gui-palette` | 5 | 10 |
| `gui-language` | 6 | 12 |
| `gui-theme` | 5 | 5 |
| `gui-network` | 6 | 12 |
| `gui-converters` | 5 | 10 |
| `gui-crypto` | 3 | 6 |
| `gui-reference` | 7 | 14 |
| `gui-json-diff` | 4 | 8 |
| `gui-regex` | 5 | 10 |
| `gui-benchmark` | 6 | 12 |
| `gui-parsers` | 4 | 8 |
| `gui-sql` | 3 | 6 |
| `gui-math` | 4 | 8 |
| `gui-validators` | 4 | 8 |
| `gui-text-tools` | 4 | 8 |
| `gui-keys` | 4 | 8 |
| `gui-timer` | 3 | 6 |
| `gui-conversion` | 4 | 8 |
| `gui-hash` | 3 | 6 |
| `gui-generators` | 4 | 8 |
| `gui-downloads` | 2 | 4 |
| `gui-date` | 4 | 8 |
| `gui-encode` | 5 | 10 |
| `gui-numbers` | 4 | 8 |
| `gui-format` | 8 | 16 |
| `gui-url` | 3 | 6 |
| `gui-binary` | 2 | 4 |
| `gui-nato` | 2 | 4 |
| `gui-stats` | 2 | 4 |
| `gui-percentage` | 5 | 10 |
| `gui-temperature` | 4 | 8 |

Excluded, with the reason:

| Excluded | Reason |
| --- | --- |
| ascii-text-drawer | The figlet font path points at an online address, so offline the font request fails and the page shows no result; the tool needs an online service. |
| camera-recorder | Needs a camera device, which the runtime does not have. |
| Print as PDF of markdown-to-html | Opens a new window and the print dialog; the runtime closes new windows. |
| Links to GitHub, Twitter, Buy me a coffee, the About page links, the palette commands Github repository and Report a bug | External addresses; the runtime blocks them and the product is offline. |
| Page types Song, Music album, Playlist, Radio station, Movie, Episode, TV show and Other video of the meta tag generator | In the reference the page type list shows Music and Video as group headers that select nothing, so the child types cannot be reached through the interface; there is no reference behavior to require. |
| PEAP without an EAP phase 2 method in the WiFi QR code generator | The reference shows no QR code for this combination although every other method does; an equivalent implementation need not share this quirk. |
| RSA key sizes of 256 and 264 bits | The reference shows no key pair at these sizes although 512 bits and above work; sizes from 512 bits up are covered. |
| The Heading 3 button of the HTML WYSIWYG editor | The reference writes a level 4 heading for it, the same as the Heading 4 button, which is covered. |
| Raw base64 of a PNG, PDF, GIF or JPEG pressed with Download file in the base64 file converter | The type is recognised from the signature and the reference then produces no file; the data address forms are covered and the extension filled in from a bare signature is checked. |
| Base64 text written without padding | Near duplicate of the invalid length case; text written with url safe characters is covered as a refusal. |
| Signed PDF files in the PDF signature checker | No signed PDF fixture can be built without a certificate authority; unsigned PDFs, other files and the replacement of the chosen file are covered. |
| Highlighting of differences in the text diff editor | Colours and decorations are not text in the observation and cannot be judged reliably; the texts of both sides are covered. |
| User agent lines of the device information page | Depend on the browser build; the screen and window figures are fixed by the runtime. |
| The Random tool palette command | Picks any tool by chance. |
| The favorite button in the header of a tool page | The reference stores an empty entry instead of the tool, so it has no usable behavior; favorites are covered from the cards of the home page. |
| The component demo pages under /c-lib | Development-only demonstrations of the interface library, not part of the tools. |
| The sliders of the lorem ipsum generator (paragraphs, sentences per paragraph, words per sentence) and of the token generator (length) | The sliders have no role, name or value in the interface the runtime reports, so a check could only reach them by screen position or private markup; the token length is covered through the length in the address, the lorem ipsum settings by their switches. |
| Persistence of the JSON to CSV converter | The reference keeps neither the input nor any setting after a reload, so there is no behavior to require. |
| Side by side and inline modes of the text diff, other display modes of the JSON diff | This release has no such control; the Only show differences switch of the JSON diff is covered. |
| The copy button of the arabic number in the roman numeral converter | The reference puts the text [object Object] on the clipboard instead of the number, so a correct implementation would fail; the copy button of the numeral is covered. |
| The number 0 in the roman numeral converter | The number field refuses values below 1 and keeps the previous value, a property of the field rather than of the conversion; numbers from 1 to 3999 and the refusal of larger ones are covered. |
| A salt rounds value of 0 in the bcrypt tool | The reference falls back to the default of 10 rounds (its library treats 0 as not set) instead of raising the value to the minimum of 4; both readings are reasonable, so neither is required. Costs from 4 to 12 are covered. |
| Decrypting text that has no salt header (words that are not a ciphertext, a base64 text without the header) in the encryption tool | The reference then derives the key from a random salt, so on some runs it shows an error and on others an empty text; ciphertexts with the header that are cut short, use another key or another algorithm are covered. |
| Colours of the light and dark theme as program checks | The theme is not text in the observation; the theme goals are judged by the evaluator from the screenshot and have no program companion. |

## How points are checked

- Every check reaches the candidate through the task black-box runtime: its snapshot of the controls, preformatted results and text of the whole page, its keyboard, pointer, upload, download and clipboard operations, its page clock and its lifecycle operations (reset, restart). Nothing reads candidate files or processes.
- Program episodes open one tool page per checkpoint in a fresh browser profile, apply fixed inputs and read the page. Fields are located by label or placeholder, never by position, except where a control has no name (copy buttons follow their result field, editor toolbars are pressed by place).
- Result text is read from the tool area: the page text from the title line of the tool (in any interface language) up to a copyright line or the end of the page, so layout and the menu do not count. Where values sit in text rather than fields (IBAN and phone facts, subnet tables, OTP codes, emoji names), the text is read in reading order with the text of value controls included; adjacent equal table values remain separate, while menu and home cards are compared as the sequence of tool and category names they show.
- Values that differ on every run are also checked to change when the page is asked for a new one (refresh), and hashes and ciphertexts make a round trip through the compare and decrypt sections of the same tool.
- Expected values are recorded from the pinned reference. Random outputs (UUIDs, ULIDs, tokens, keys, salts, generated addresses) are checked by shape: length, character set and structure of each line. Outputs that depend on time are read at the fixed page clock instant 2026-03-04T05:06:07Z and moved only through the clock operation.
- Points that only verify a refusal, an empty result or an unchanged or restored state, and that a page ignoring its input would also pass, are bound (requires) to a positive point of the same episode, so such a page earns nothing from them; this was checked with candidates that ignore every input or every click.
- Command-palette opening and clearing also check the search field. Empty searches depend on a successful matching search; the palette command that changes the theme is judged from the visible colours in a GUI goal.
- GUI episodes give one evaluator agent per episode one goal per checkpoint; the checkpoint starts from a fresh browser profile on the page the goal names. Each goal has a frontend point judged by the evaluator from its acceptance text and, where the result is text, a program companion that reads the state the goal produced.
- Points are binary. The task score is the fraction of episodes whose points all pass. Candidate defects fail the affected episodes; verifier faults and provider outages invalidate the run.

## Budgets and time

GUI episodes have call, token and active-time budgets in the manifest (calls 30 + 30 per checkpoint, tokens 400,000 + 500,000 per checkpoint, seconds 300 + 240 per checkpoint). Program episodes need no evaluator and run under the wall-clock limit recorded in the manifest.

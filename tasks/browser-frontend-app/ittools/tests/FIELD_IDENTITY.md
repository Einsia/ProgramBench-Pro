# Field identity maintenance

`field_identity.py` projects the affected input/result groups to semantic field
names before comparing values. The schema is selected by the checkpoint page,
shared by program and GUI checks. It does not select by candidate or episode ID.

| Page | Semantic roles and their source | Original `name_of()` fallback |
| --- | --- | --- |
| temperature-converter | Eight scale captions; `fam_encode.temperature`, `gui_measure.temperature` | Eight `Please Input` fields in scale order |
| hash-text | Eight algorithms in `fam_hash.HASHES`, `gui_more.hashing` | Eight `Input text` results in algorithm order |
| keycode-info | Key, keycode, code, location, modifiers; `fam_misc.KEY_SEEN`, `gui_text.KEY_SEEN` and reference body text | `Key name...`, `Keycode...`, `Code...`, `Code...`, `None` |
| uuid-generator | Quantity, namespace, name; `fam_gen.uuid_generator` and visible Quantity caption | `UUID quantity`, `Namespace`, `Name` |
| svg-placeholder-generator | Width (in px), height (in px), font size, custom text; `fam_files.svg_placeholder_generator` and `gui-downloads` reference captions | `SVG width...`, `SVG height...`, `Font size...`, `Custom text` |
| rsa-key-pair-generator | Bits; `fam_files.rsa_key_pair_generator` | `Please Input` |
| string-obfuscator | String, keep first, keep last; `fam_text.string_obfuscator` | `String to obfuscate:`, `Please Input`, `Please Input` |
| email-normalizer | Raw emails to normalize; `fam_web.EMAIL_SEEN`, `gui_text.EMAIL_SEEN`, reference body text | `Put your emails here (one per line)...` |
| base-converter | Input number, input base, custom; `fam_encode.bases`, `gui_encode.numbers` and reference body text | `Input number`, `Put your input base here (ex: 10)`, `Please Input` |
| json-prettify / yaml-prettify / xml-formatter | Indent size, source document; `fam_format.formatter` | `Please Input`, followed by the source document's placeholder/label |

The runtime's `caption()` fallback only searches nearby text inside a control's
container. Reference wrappers often keep the visible caption outside that
container, so `name_of()` falls back to a placeholder. These repeated strings
are not algorithm or unit names. Their declared positions recover that identity
for original records. A semantic caption takes precedence over an incidental
placeholder; conflicting recognized identities and unknown primary names fail.
Punctuation, case and accents may vary. Units and base/algorithm digits remain
part of identity. No result value is used to find a field.

Named fields may appear in a different visual order. Projection orders the full
group by identity before an `outputs` slice is selected. Swapping values between
roles, duplicating/missing fields, changing units or algorithms, and differences
in other observation text remain failures. Unmapped pages retain strict labels.

`Hooks.judge()` applies the same projection to expected observations in memory;
comparison never edits its input bundle. Published records contain semantic
field names, and the projection also accepts archived placeholder-based records.
The normal companion logic sees the backend result without any frontend verdict
override.

Run maintainer regressions with an external `TMPDIR`:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/maintainer_field_identity_test.py
```

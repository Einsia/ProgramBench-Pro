# Markdown fixture sources

`markdown.json` contains deduplicated inputs from CommonMark 0.30 and the listed markdown-it project releases. Download URLs and SHA-256 digests are in `SOURCES.json`; original notices are in `licenses/`. Expected HTML from those projects is not used for scoring: the actual StackEdit release supplies the frozen observations.

The entries whose IDs start with `cm-` adapt examples from **CommonMark Spec 0.30**, by **John MacFarlane**, https://spec.commonmark.org/0.30/, under **Creative Commons Attribution-ShareAlike 4.0 International (CC-BY-SA-4.0)**. The adaptation extracts Markdown inputs and section names from the published JSON test corpus, adds stable case IDs and groups, removes expected outputs, and deduplicates equal inputs. Those adapted entries remain available under CC-BY-SA-4.0; see `licenses/CC-BY-SA-4.0.txt`. No endorsement by the original authors is implied.

Entries whose IDs start with `ext-` adapt MIT-licensed markdown-it/plugin test inputs. Their original notices are in `licenses/markdown-it*.txt`; the archives at the pinned URLs contain the full sources. Task-authored fixture files are separate from these attributed inputs.

The small `convert-*.html`, workspace backup and invalid-input fixtures are original task inputs. Their expected behavior is recorded from the reference application.

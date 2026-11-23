'''Export of the task and link notebooks: the small format matrix on notebooks whose pages hold checkboxes, tags, dates and links.

Each scenario uploads its own notebook (a setup row), exports it once in one format and reads the exported file of every page; a row is the
exit code, printed lines and files written, or the scrubbed text of one exported page file, so each row is one distinct observation.
'''
import export_cases as ex

NOTEBOOKS = (('tasks', ex.SMALL), ('links', ex.SMALL))


def build(suite):
    for key, combos in NOTEBOOKS:
        family = 'export-' + key
        for fmt, template, ext in combos:
            label = ex.safe(fmt + '-' + template)
            scenario = ex.prepare(suite, family, key + '-' + label, key)
            suite.add(family, scenario, 'run', ex._run('m-' + key + '-' + label, fmt, template, ('-r',)), needs=ex._needs,
                      description=f'Export the {key} notebook as {fmt} with the {template} template: exit code, printed lines and files written.')
            for relative in ex.page_files(key, ext):
                suite.add(family, scenario, 'page-' + ex.safe(relative), ex._page(relative), needs=ex._ready,
                          description=f'Exported text of {relative} ({fmt}, {template} template, {key} notebook).')

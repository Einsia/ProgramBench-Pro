'''Musical document interchange and project version/template persistence.'''
import specification as s
import specification_more as m


def imported(wf, name, saved, acceptance):
    return s.step('imported', 'Import ' + s.path(wf, name) + ' using the application import command; acknowledge '
                  'any warning about the default soundfont. Save the result as ' + s.path(wf, saved) + '.',
                  acceptance + ' The project is saved with its requested name.',
                  [{'op': 'import-file', 'file': name}, {'op': 'save-project', 'file': saved}],
                  [s.written(saved), {'kind': 'project-notes', 'path': saved,
                   'description': 'The saved project preserves the imported track type, note positions, lengths, keys, levels and panning.'}],
                  requires={'visible': ['state-1']})


def build():
    out = []

    def add(*args, **kwargs):
        out.append(s.frozen_form(s.episode(*args, **kwargs)))

    wf = 'midi-import-export'
    add(wf, 'midi', ['tone12.mid'], [
        imported(wf, 'tone12.mid', 'imported.mmpz', 'An imported MIDI track with a note pattern appears in the Song-Editor.'),
        s.step('exported', 'Export the imported project to a MIDI file at ' + s.path(wf, 'export.mid') + '.',
               'The MIDI export completes and the exported file is available.',
               [{'op': 'export-midi', 'file': 'export.mid'}],
               [s.written('export.mid'), {'kind': 'file-midi', 'path': 'export.mid',
                'description': 'The MIDI export preserves note keys, durations, positions, velocities and tempo, independently of MIDI track layout and tick resolution.'}],
               depends=['imported'], requires={'visible': ['state-1']})])

    wf = 'hydrogen-import'
    add(wf, 'hydrogen', ['beat.h2song'], [
        imported(wf, 'beat.h2song', 'hydrogen.mmpz',
                 'The imported beat is placed in the song and its sampled instrument is present in the Beat+Bassline Editor.'),
        m.exported_step(wf, 'rendered', 'Export the imported song.',
                        'The imported beat remains in the song after export.', [], 'hydrogen.wav',
                        'The exported WAV contains the three imported sample notes at their requested positions and levels.',
                        depends=['imported'])])

    wf = 'gui-export-tracks'
    output_folder = s.path(wf, 'placeholder.wav').rsplit('/', 1)[0]
    add(wf, 'export', ['duet.mmp'], [
        s.step('opened', 'Open the supplied project ' + s.path(wf, 'duet.mmp') + '.',
               'The Song-Editor shows Low and High instrument tracks with their note patterns and the toolbar tempo reads 120.',
               [{'op': 'open-project', 'file': 'duet.mmp'}]),
        s.step('exported', 'Export the project tracks as separate WAV files in ' + output_folder
               + ' using Export Tracks and the default audio settings.',
               'Export completes and separate WAV files for the Low and High tracks are available.',
               [{'op': 'export-tracks', 'folder': output_folder}],
               [dict(s.exported('1_Low.wav', slack=4096,
                     description='The Low track export contains only its two lower notes.'), trim_start=1024),
                dict(s.exported('2_High.wav', slack=4096,
                     description='The High track export contains only its two higher notes.'), trim_start=1024)],
               depends=['opened'], requires={'visible': ['state-1', 'state-2']})])

    wf = 'project-versions-template'
    add(wf, 'project', ['duet.mmp'], [
        m.saved_step(wf, 'saved', 'Open ' + s.path(wf, 'duet.mmp') + ' and set the tempo to 155 BPM.',
                     'The Song-Editor shows Low and High and the tempo reads 155.',
                     [{'op': 'open-project', 'file': 'duet.mmp'}, {'op': 'tempo', 'value': 155}],
                     'version.mmpz', './head', 'The initial project version retains the tempo 155.'),
        s.step('versioned', 'Set the tempo to 175 BPM and save as a new version with the application version-save command.',
               'The tempo reads 175 and the project title shows a new numbered version.',
               [{'op': 'tempo', 'value': 175}, {'op': 'new-version', 'file': 'version-01.mmpz'}],
               [s.saved('version.mmpz', './head', 'The original version still has tempo 155.', fields=('bpm',)),
                s.saved('version-01.mmpz', './head', 'The numbered version has tempo 175.', fields=('bpm',))],
               depends=['saved'], requires={'visible': ['state-2']}),
        s.step('template', 'Save the current project as the default template.',
               'The current Low/High project remains visible at 175 BPM and a default template is saved.',
               [{'op': 'default-template'}],
               [{'kind': 'project-notes', 'path': 'default.mpt', 'description': 'The template retains both note tracks.'}],
               depends=['versioned'], requires={'visible': ['state-1']}),
        m.saved_step(wf, 'restarted', 'The application has restarted. Save its new project, which should be based on the default template.',
                     'The new project starts at 175 BPM with the Low and High tracks and their note patterns.',
                     [], 'from-template.mmpz', './head', 'The new project inherits the default template tempo.',
                     depends=['template'], fields=('bpm',))])
    out[-1]['checkpoints'][-1]['lifecycle'] = 'restart'
    # This separate episode exercises the template menu without depending on
    # the previous episode's private state.
    wf = 'new-from-template'
    add(wf, 'project', ['duet.mmp'], [
        s.step('template', 'Open ' + s.path(wf, 'duet.mmp') + ', set the tempo to 165 BPM, and save it as the default template.',
               'The Low and High tracks are visible at 165 BPM, and the default template is saved.',
               [{'op': 'open-project', 'file': 'duet.mmp'}, {'op': 'tempo', 'value': 165}, {'op': 'default-template'}],
               [s.saved('default.mpt', './head', fields=('bpm',))], requires={'visible': ['state-1']}),
        m.saved_step(wf, 'created', 'Change the current tempo to 90 BPM, then create a new project from the saved default template via New from template. Discard unsaved changes if asked.',
                     'The new project has the template tempo 165 and its Low and High tracks.',
                     [{'op': 'tempo', 'value': 90}, {'op': 'from-template', 'name': 'default'}],
                     'chosen-template.mmpz', './head', 'The project created from the template restores tempo 165.',
                     depends=['template'], fields=('bpm',))])
    return out

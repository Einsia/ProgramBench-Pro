'''Second batch of GUI episodes: toolbar wheels, tempo, sidebar instruments, the audio file processor, clips, beat
steps and exports.

Built on the helpers of specification.py. Every checkpoint ends with Save As under a new name or with an export, and
the independent checks read only that file; the expected values are frozen at record.
'''
import specification as s


def saved_step(wf, sid, goal, acceptance, ops, name, xpath, what, depends=(), fields=None, ranges=None):
    target = s.path(wf, name)
    recipe = list(ops) + [{'op': 'save-project', 'file': name}]
    return s.step(sid, goal + ' Then save the project as ' + target + '.',
                  acceptance + ' The project is saved without an error message and its name ' + name.rsplit('.', 1)[0]
                  + ' is shown in the window title.', recipe,
                  [s.written(name, 'The project file ' + name + ' was written.'),
                   s.saved(name, xpath, what, fields=fields, ranges=ranges)],
                  depends=list(depends), requires={'visible': ['state-1']})


def exported_step(wf, sid, goal, acceptance, ops, name, what, depends=()):
    target = s.path(wf, name)
    recipe = list(ops) + [{'op': 'export', 'file': name}]
    return s.step(sid, goal + ' Then export the project as a WAV file named ' + target
                  + ' with the default export settings (confirm the export dialog with its Start button).',
                  acceptance + ' The export finished without an error message and its dialog is closed.', recipe,
                  [s.exported(name, 'wav', 'signal', 4096, what)], depends=list(depends),
                  requires={'visible': ['state-1']})


def build():
    out = []

    def add(*a, **kw):
        out.append(s.frozen_form(s.episode(*a, **kw)))

    # ------------------------------------------------------------ toolbar
    wf = 'toolbar-master-sliders'
    add(wf, 'toolbar', [], [
        saved_step(wf, 'volume', 'Raise the master volume slider of the toolbar by 10 steps, from 100 to 110 (the mouse wheel turns it by one step per notch).',
                   'The master volume slider of the toolbar reads 110.', [{'op': 'master-volume', 'notches': 10}],
                   'volume.mmpz', './head', 'The saved project holds the master volume 110.'),
        saved_step(wf, 'pitch', 'Raise the master pitch slider of the toolbar by 3 steps, from 0 to 3.',
                   'The master pitch slider of the toolbar reads 3 and the master volume slider still reads 110.',
                   [{'op': 'master-pitch', 'notches': 3}], 'pitch.mmpz', './head',
                   'The saved project holds the master pitch 3 next to the master volume 110.', depends=['volume']),
        saved_step(wf, 'signature', 'Raise the numerator of the time signature display by 2, from 4 to 6 (the mouse wheel over the upper number).',
                   'The time signature display shows 6 over 4.', [{'op': 'time-signature', 'notches': 2}],
                   'signature.mmpz', './head', 'The saved project holds the time signature 6 over 4.', depends=['pitch'])])

    # ------------------------------------------------------------ project
    wf = 'project-tempo-values'
    add(wf, 'project', [], [
        saved_step(wf, 'slower', 'Set the tempo of the project to 90 beats per minute.', 'The tempo display of the toolbar reads 90.',
                   [{'op': 'tempo', 'value': 90}], 't90.mmpz', './head', 'The saved project holds the tempo 90.'),
        saved_step(wf, 'faster', 'Set the tempo of the project to 200 beats per minute.', 'The tempo display of the toolbar reads 200.',
                   [{'op': 'tempo', 'value': 200}], 't200.mmpz', './head', 'The saved project holds the tempo 200.', depends=['slower']),
        s.step('reopened', 'The application was restarted and shows a fresh default project. Open the saved project '
               + s.path(wf, 't200.mmpz') + '.', 'The tempo display of the toolbar reads 200 again and the window title shows t200.',
               [{'op': 'open-project', 'file': 't200.mmpz'}], lifecycle='restart', depends=['faster'])])

    # ------------------------------------------------------------ sidebar
    wf = 'sidebar-instruments'
    add(wf, 'sidebar', [], [
        saved_step(wf, 'kicker', 'Drag the Kicker instrument from the Instrument Plugins list (the first tab of the left sidebar) into the Song-Editor, below the last track, so that a new instrument track is created; close the list again by clicking its tab.',
                   'The Song-Editor lists a new instrument track named Kicker below the four default tracks.',
                   [{'op': 'plugin-drag', 'plugin': 'Kicker', 'tracks': 4}], 'kicker.mmpz', './song/trackcontainer/track',
                   'The saved project lists its tracks with their type and name, the new one named Kicker.'),
        saved_step(wf, 'processor', 'Drag the AudioFileProcessor instrument from the Instrument Plugins list into the Song-Editor, below the last track; close the list again by clicking its tab.',
                   'The Song-Editor lists a track named AudioFileProcessor below the Kicker track.',
                   [{'op': 'plugin-drag', 'plugin': 'AudioFileProcessor', 'tracks': 5}], 'processor.mmpz',
                   './song/trackcontainer/track', 'The saved project lists six tracks, the last one named AudioFileProcessor.', depends=['kicker'])])

    # ------------------------------------------------------------ instrument window
    wf = 'audio-file-processor'
    sample = s.path(wf, 'tone-440.wav')
    add(wf, 'instrument-window', ['tone-440.wav'], [
        saved_step(wf, 'loaded', 'Add an audio file processor track: drag AudioFileProcessor from the Instrument Plugins list into the Song-Editor, below the last track, close the list again, open the new track by clicking its name and load the audio file '
                   + sample + ' into it (the small file button next to the interpolation list opens a file dialog).',
                   'A track named tone-440.wav is listed in the Song-Editor below the four default tracks and its instrument window shows a sample length of about 1000 ms.',
                   [{'op': 'plugin-drag', 'plugin': 'AudioFileProcessor', 'tracks': 4},
                    {'op': 'open-instrument', 'name': 'AudioFileProcessor'},
                    {'op': 'afp-sample', 'file': 'tone-440.wav'}], 'loaded.mmpz', './/audiofileprocessor',
                   'The saved audio file processor names the loaded sample file.'),
        saved_step(wf, 'reversed', 'In the instrument window of that track, switch on Reverse sample.',
                   'The Reverse sample button of the instrument window is shown switched on.',
                   [{'op': 'afp-switch', 'name': 'Reverse sample'}], 'reversed.mmpz', './/audiofileprocessor',
                   'The saved audio file processor has the sample reversed.', depends=['loaded']),
        saved_step(wf, 'looped', 'In the same instrument window, switch on Enable loop.',
                   'The Enable loop button is shown switched on and Disable loop is off.',
                   [{'op': 'afp-switch', 'name': 'Enable loop'}], 'looped.mmpz', './/audiofileprocessor',
                   'The saved audio file processor has the loop switched on.', depends=['reversed'])])

    # ------------------------------------------------------------ song clips
    wf = 'song-clips'
    sample = s.path(wf, 'tone-440.wav')
    add(wf, 'song-editor', ['tone-440.wav'], [
        saved_step(wf, 'pattern', 'In the Song-Editor, create a clip on the TripleOscillator track at the very start of the song by clicking its empty row with the draw tool (the pencil of the Song-Editor toolbar).',
                   'A clip is shown at the start of the TripleOscillator row.', [{'op': 'clip', 'row': 0, 'bar': 0}],
                   'pattern.mmpz', './song/trackcontainer/track/pattern', 'The saved project holds one pattern on the first track.'),
        saved_step(wf, 'beat', 'Create a clip on the Beat/Bassline 0 row at the start of bar 5 of the song ruler.',
                   'A clip starts at bar 5 in the Beat/Bassline 0 row.', [{'op': 'clip', 'row': 2, 'bar': 4}],
                   'beat-clip.mmpz', './song/trackcontainer/track/bbtco', 'The saved project holds one Beat/Bassline clip with its position and length.',
                   depends=['pattern'], fields=('pos', 'len', 'muted', 'usestyle')),
        saved_step(wf, 'sample', 'Create a clip on the Sample track row at the start of the song, then give it the audio file ' + sample
                   + ' (double-click the clip and enter the path in the file dialog).',
                   'The Sample track row shows a clip at the start of the song that is about half a bar long.',
                   [{'op': 'clip', 'row': 1, 'bar': 0}, {'op': 'clip-sample', 'row': 1, 'bar': 0, 'file': 'tone-440.wav'}],
                   'sample-clip.mmpz', './song/trackcontainer/track/sampletco',
                   'The saved project holds one sample clip at the start with its sample file and length near half a bar (72 to 120 ticks).',
                   depends=['beat'], fields=('pos', 'len', 'muted', 'src'), ranges={'len': [72, 120]})])

    # ------------------------------------------------------------ export
    wf = 'export-sample-clip'
    sample = s.path(wf, 'tone-440.wav')
    add(wf, 'export', ['tone-440.wav'], [
        exported_step(wf, 'exported', 'Put the audio file ' + sample + ' on the Sample track: create a clip at the start of its row, then double-click the clip to choose the file.',
                      'The Sample track row shows a clip at the start of the song.',
                      [{'op': 'clip', 'row': 1, 'bar': 0}, {'op': 'clip-sample', 'row': 1, 'bar': 0, 'file': 'tone-440.wav'}],
                      'out1.wav', 'out1.wav is a WAV file that decodes to the rendered song.'),
        exported_step(wf, 'quieter', 'Lower the master volume slider of the toolbar by 20 steps, from 100 to 80.',
                      'The master volume slider of the toolbar reads 80.', [{'op': 'master-volume', 'notches': -20}],
                      'out2.wav', 'out2.wav is a WAV file whose level follows the lowered master volume.', depends=['exported']),
        exported_step(wf, 'slower', 'Set the tempo of the project to 70 beats per minute.', 'The tempo display of the toolbar reads 70.',
                      [{'op': 'tempo', 'value': 70}], 'out3.wav', 'out3.wav is a WAV file whose length follows the slower tempo.',
                      depends=['quieter'])])

    # ------------------------------------------------------------ beat editor
    wf = 'beat-steps'
    add(wf, 'beat-editor', [], [
        saved_step(wf, 'first', 'Open the Beat+Bassline Editor (the main toolbar has a button for it) and switch on the first step of its Kicker row.',
                   'The Beat+Bassline Editor is open and only the first step of the Kicker row is on.',
                   [{'op': 'beat-step', 'row': 0, 'step': 0}], 'steps1.mmpz', './/pattern/note',
                   'The saved project lists the notes of its patterns with position, length and key.'),
        saved_step(wf, 'more', 'Switch on the fifth and the ninth step of the Kicker row, counting from the left.',
                   'The first, fifth and ninth steps of the Kicker row are on.',
                   [{'op': 'beat-step', 'row': 0, 'step': 4}, {'op': 'beat-step', 'row': 0, 'step': 8}], 'steps2.mmpz',
                   './/pattern/note', 'The saved project lists three notes of the Kicker pattern.', depends=['first']),
        saved_step(wf, 'off', 'Switch the fifth step of the Kicker row off again.',
                   'The first and ninth steps of the Kicker row are on and the fifth is off.',
                   [{'op': 'beat-step', 'row': 0, 'step': 4}], 'steps3.mmpz', './/pattern/note',
                   'The saved project lists two notes of the Kicker pattern.', depends=['more'])])
    import specification_third
    out.extend(specification_third.build())
    return out

'''Fourth batch of GUI episodes: instrument plugins dropped and dragged into the Song-Editor, off-beat steps of the
Beat+Bassline Editor, further tempo values, the toolbar at the ends of its ranges, exports of a beat pattern and of two
sample clips, and renaming further tracks.

Built on the helpers of specification.py and specification_more.py with operations that already ran in the earlier
batches. Every checkpoint ends with Save As under a new name or with an export; the independent checks read only that.
'''
import specification as s
import specification_more as m

TRACKS = './song/trackcontainer/track'
INSTRUMENT = './song/trackcontainer/track/instrumenttrack/instrument'
STEPS = './/pattern/note'
HEAD = './head'


def build():
    out = []

    def add(*a, **kw):
        out.append(s.frozen_form(s.episode(*a, **kw)))

    wf = 'plugin-tracks'
    add(wf, 'sidebar', [], [
        m.saved_step(wf, 'monstro', 'Replace the instrument of the TripleOscillator track: open the Instrument Plugins list (the first tab of the left sidebar), drag Monstro onto the TripleOscillator row of the Song-Editor and close the list again by clicking its tab.',
                     'The first track row is named Monstro and a Monstro instrument window is open; the other three tracks are unchanged.',
                     [{'op': 'plugin-drop', 'plugin': 'Monstro', 'row': 0}], 'monstro.mmpz', INSTRUMENT,
                     'The saved project holds the Monstro instrument in the first track.'),
        m.saved_step(wf, 'bass', 'Drag LB302 from the Instrument Plugins list into the Song-Editor below the last track, so that a new track is created, and close the list again.',
                     'The Song-Editor lists a fifth track named LB302 below the four existing ones.',
                     [{'op': 'plugin-drag', 'plugin': 'LB302', 'tracks': 4}], 'bass.mmpz', INSTRUMENT,
                     'The saved project holds the Monstro and the LB302 instrument in two instrument tracks.', depends=['monstro']),
        m.saved_step(wf, 'wavetable', 'Drag Watsyn from the Instrument Plugins list into the Song-Editor below the last track and close the list again.',
                     'The Song-Editor lists a sixth track named Watsyn below the LB302 track.',
                     [{'op': 'plugin-drag', 'plugin': 'Watsyn', 'tracks': 5}], 'wavetable.mmpz', INSTRUMENT,
                     'The saved project holds the Monstro, the LB302 and the Watsyn instrument in three instrument tracks.',
                     depends=['bass'])])

    wf = 'beat-steps-offbeat'
    add(wf, 'beat-editor', [], [
        m.saved_step(wf, 'fourth', 'Open the Beat+Bassline Editor (the main toolbar has a button for it) and switch on the fourth step of its Kicker row, counting from the left.',
                     'The Beat+Bassline Editor is open and only the fourth step of the Kicker row is on.',
                     [{'op': 'beat-step', 'row': 0, 'step': 3}], 'off1.mmpz', STEPS,
                     'The saved project lists one note of the Kicker pattern with its position, length and key.'),
        m.saved_step(wf, 'more', 'Switch on the eighth and the twelfth step of the Kicker row, counting from the left.',
                     'The fourth, eighth and twelfth steps of the Kicker row are on.',
                     [{'op': 'beat-step', 'row': 0, 'step': 7}, {'op': 'beat-step', 'row': 0, 'step': 11}], 'off2.mmpz', STEPS,
                     'The saved project lists three notes of the Kicker pattern.', depends=['fourth']),
        m.saved_step(wf, 'off', 'Switch the fourth step of the Kicker row off again.',
                     'The eighth and twelfth steps of the Kicker row are on and the fourth is off.',
                     [{'op': 'beat-step', 'row': 0, 'step': 3}], 'off3.mmpz', STEPS,
                     'The saved project lists two notes of the Kicker pattern.', depends=['more'])])

    wf = 'tempo-more'
    add(wf, 'project', [], [
        m.saved_step(wf, 'slow', 'Set the tempo of the project to 60 beats per minute.', 'The tempo display of the toolbar reads 60.',
                     [{'op': 'tempo', 'value': 60}], 't60.mmpz', HEAD, 'The saved project holds the tempo 60.'),
        m.saved_step(wf, 'fast', 'Set the tempo of the project to 300 beats per minute.', 'The tempo display of the toolbar reads 300.',
                     [{'op': 'tempo', 'value': 300}], 't300.mmpz', HEAD, 'The saved project holds the tempo 300.', depends=['slow']),
        s.step('reopened', 'The application was restarted and shows a fresh default project. Open the saved project '
               + s.path(wf, 't60.mmpz') + '.', 'The tempo display of the toolbar reads 60 again and the window title shows t60.',
               [{'op': 'open-project', 'file': 't60.mmpz'}], lifecycle='restart', depends=['fast'])])

    wf = 'toolbar-limits'
    add(wf, 'toolbar', [], [
        m.saved_step(wf, 'silent', 'Lower the master volume slider of the toolbar to its lowest position: 100 steps down, from 100 to 0 (the mouse wheel turns it by one step per notch).',
                     'The master volume slider of the toolbar is at its lowest position, 0.', [{'op': 'master-volume', 'notches': -100}],
                     'silent.mmpz', HEAD, 'The saved project holds the master volume 0.'),
        m.saved_step(wf, 'low', 'Lower the master pitch slider of the toolbar by 12 steps, from 0 to -12.',
                     'The master pitch slider of the toolbar is at its lowest position, -12, and the master volume slider is still at 0.',
                     [{'op': 'master-pitch', 'notches': -12}], 'low.mmpz', HEAD,
                     'The saved project holds the master pitch -12 next to the master volume 0.', depends=['silent']),
        m.saved_step(wf, 'single', 'Lower the numerator of the time signature display by 3, from 4 to 1 (the mouse wheel over the upper number).',
                     'The time signature display shows 1 over 4.', [{'op': 'time-signature', 'notches': -3}],
                     'single.mmpz', HEAD, 'The saved project holds the time signature 1 over 4.', depends=['low'])])

    wf = 'export-beat'
    add(wf, 'export', [], [
        m.exported_step(wf, 'exported', 'Open the Beat+Bassline Editor (the main toolbar has a button for it), switch on the first, fifth, ninth and thirteenth step of its Kicker row, then create a clip at the start of the Beat/Bassline 0 row of the Song-Editor by clicking its empty row with the draw tool.',
                        'The Kicker row shows four steps on, one per beat, and the Beat/Bassline 0 row of the Song-Editor holds a clip at the start of the song.',
                        [{'op': 'beat-step', 'row': 0, 'step': 0}, {'op': 'beat-step', 'row': 0, 'step': 4},
                         {'op': 'beat-step', 'row': 0, 'step': 8}, {'op': 'beat-step', 'row': 0, 'step': 12},
                         {'op': 'clip', 'row': 2, 'bar': 0}],
                        'b1.wav', 'b1.wav is a WAV file that decodes to the rendered beat.'),
        m.exported_step(wf, 'fewer', 'Switch the fifth and the thirteenth step of the Kicker row off again.',
                        'Only the first and the ninth step of the Kicker row are on.',
                        [{'op': 'beat-step', 'row': 0, 'step': 4}, {'op': 'beat-step', 'row': 0, 'step': 12}],
                        'b2.wav', 'b2.wav is a WAV file with two kicks instead of four.', depends=['exported']),
        m.exported_step(wf, 'slower', 'Set the tempo of the project to 70 beats per minute.', 'The tempo display of the toolbar reads 70.',
                        [{'op': 'tempo', 'value': 70}], 'b3.wav', 'b3.wav is a WAV file whose length follows the slower tempo.',
                        depends=['fewer'])])

    wf = 'track-rename-more'
    add(wf, 'song-editor', [], [
        m.saved_step(wf, 'bass', 'Rename the first track of the Song-Editor, the TripleOscillator track, to Bass two (right-click its name, type the new name and confirm with Return).',
                     'The first row of the Song-Editor is named Bass two; the other tracks keep their names.',
                     [{'op': 'rename-track', 'name': 'TripleOscillator', 'text': 'Bass two'}], 'bass.mmpz', TRACKS,
                     'The saved project lists its tracks, the first one named Bass two.'),
        m.saved_step(wf, 'sweep', 'Rename the last track, the Automation track, to Sweep in the same way.',
                     'The last row of the Song-Editor is named Sweep and the first row is still named Bass two.',
                     [{'op': 'rename-track', 'name': 'Automation track', 'text': 'Sweep'}], 'sweep.mmpz', TRACKS,
                     'The saved project lists its tracks, the first one named Bass two and the last one named Sweep.',
                     depends=['bass'])])

    wf = 'sample-export'
    first = s.path(wf, 'tone-880.wav')
    second = s.path(wf, 'tone-440.wav')
    add(wf, 'export', ['tone-880.wav', 'tone-440.wav'], [
        m.exported_step(wf, 'first', 'Put the audio file ' + first + ' on the Sample track: create a clip at the start of its row, then double-click the clip to choose the file.',
                        'The Sample track row shows a clip at the start of the song.',
                        [{'op': 'clip', 'row': 1, 'bar': 0}, {'op': 'clip-sample', 'row': 1, 'bar': 0, 'file': 'tone-880.wav'}],
                        's1.wav', 's1.wav is a WAV file that decodes to the rendered song.'),
        m.exported_step(wf, 'second', 'Put the audio file ' + second + ' on the Sample track as a second clip: create a clip at the start of bar 3 of its row (the song ruler counts bars from 1), then double-click the clip to choose the file.',
                        'The Sample track row shows a second clip starting at bar 3 next to the first one.',
                        [{'op': 'clip', 'row': 1, 'bar': 2}, {'op': 'clip-sample', 'row': 1, 'bar': 2, 'file': 'tone-440.wav'}],
                        's2.wav', 's2.wav is a WAV file that is longer than the first export and holds both tones.',
                        depends=['first']),
        m.exported_step(wf, 'louder', 'Raise the master volume slider of the toolbar by 40 steps, from 100 to 140.',
                        'The master volume slider of the toolbar reads 140.', [{'op': 'master-volume', 'notches': 40}],
                        's3.wav', 's3.wav is a WAV file whose level follows the raised master volume.', depends=['second'])])
    import specification_documents
    out.extend(specification_documents.build())
    return out

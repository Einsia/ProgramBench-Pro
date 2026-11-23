'''Synthesizer coverage of the product command line on generated projects.

Every point renders one generated project with one instrument track (lb302, kicker, Monstro or OPL2) through cli
render and decodes the written file with the verifier FFmpeg. The exit status never decides; the written file does.
The settings of a point are written into the instrument element the way the product saves them and what is not given
is the product default; Monstro points silence the oscillators they do not test. Waves whose output is not
reproducible between runs of the reference are left out, except kicker noise, which uses statistics over 32 notes.
A point returns its signal class and the
signal projection of the render (format, length, level per channel, level per window and spectrum), so every knob,
switch and wave changes the observation.
'''
from __future__ import annotations

import math

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
OVERLAP = [(i * 36, 96, 52 + 3 * i) for i in range(5)]
# A line in the high register (keys 84 to 90): the level scaling of the OPL2 operators acts on high notes.
HIGH = [(i * 48, 48, 84 + 2 * i) for i in range(4)]


def label(value):
    return ('minus-' if value < 0 else '') + str(abs(value)).replace('.', '-')


def point(suite, scenario, description, plugin, params, notes=SEQUENCE, projection=signal_projection):
    def action(ctx):
        project = px.Project(bpm=BPM)
        project.add(px.instrument_track(plugin, plugin, params=params, notes=notes))
        rendered = ctx.render(project.xml(), scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': projection(rendered.audio)}
    suite.add('instrument', scenario, 'render', action, description=description)


def noise_projection(audio):
    '''Noise has random peaks and phase: compare levels and whole-render high-frequency energy over many notes.'''
    result = signal_projection(audio, spectrum=False)
    for index, row in enumerate(result['signals']):
        row.pop('peak')
        for window in row['windows']:
            window.pop('peak')
        samples = audio.channel(index)
        energy = math.fsum(value * value for value in samples)
        differences = math.fsum((right - left) ** 2 for left, right in zip(samples, samples[1:]))
        row['roughness'] = math.sqrt(differences / energy) if energy else 0.0
    return result


def lb302_points(suite):
    def add(scenario, description, notes=SEQUENCE, **params):
        point(suite, 'lb302-' + scenario, description, 'lb302', params, notes)

    for value in (0.1, 0.4, 1.0, 1.4):
        add(f'cutoff-{label(value)}', f'Set the lb302 filter cutoff to {value}', vcf_cut=value)
    for value in (0.2, 0.5, 1.0, 1.25):
        add(f'resonance-{label(value)}', f'Set the lb302 filter resonance to {value}', vcf_res=value)
    for value in (0.0, 0.5, 1.0):
        add(f'envelope-mod-{label(value)}', f'Set the lb302 filter envelope modulation to {value} at a low cutoff',
            vcf_cut=0.4, vcf_mod=value)
    for value in (0.0, 0.5, 1.0):
        add(f'envelope-decay-{label(value)}', f'Set the lb302 filter envelope decay to {value} at a low cutoff',
            vcf_cut=0.4, vcf_mod=0.9, vcf_dec=value)
    for value in (0.3, 0.7, 1.0):
        add(f'distortion-{label(value)}', f'Set the lb302 distortion to {value}', dist=value)
    # Shape 10 (band-limited triangle) renders like shape 1 (triangle) within the observation tolerances.
    for shape in (0, 1, 2, 3, 4, 5, 6, 9, 11):
        add(f'shape-{shape}', f'Play the lb302 wave shape {shape}', shape=shape)
    add('slide', 'Slide between overlapping lb302 notes', OVERLAP, slide=1)
    add('slide-decay-0-1', 'Slide between overlapping lb302 notes with a short slide decay', OVERLAP, slide=1,
        slide_dec=0.1)
    add('slide-decay-1-0', 'Slide between overlapping lb302 notes with a long slide decay', OVERLAP, slide=1,
        slide_dec=1.0)
    add('dead', 'Play overlapping lb302 notes with the dead switch on', OVERLAP, dead=1)
    add('db24', 'Filter the lb302 with 24 dB per octave at a low cutoff', db24=1, vcf_cut=0.4)
    add('db24-resonant', 'Filter the lb302 with 24 dB per octave, a low cutoff and a high resonance', db24=1,
        vcf_cut=0.4, vcf_res=1.0)
    add('acid', 'Play an acid line: low cutoff, high resonance, full envelope, slide and distortion', OVERLAP,
        vcf_cut=0.3, vcf_res=1.0, vcf_mod=1.0, vcf_dec=0.3, slide=1, dist=0.3)


def kicker_points(suite):
    def add(scenario, description, **params):
        # Without a version attribute the product loads a kicker as an old preset (envelope slope 1, frequency slope 1,
        # click 0, start from note off); version 1 makes these controls count.
        point(suite, 'kicker-' + scenario, description, 'kicker', {'version': 1, **params})

    for value in (80, 220, 500):
        add(f'start-frequency-{value}', f'Start the kicker sweep at {value} Hz', startnote=0, startfreq=value)
    for value in (20, 100, 200):
        add(f'end-frequency-{value}', f'End the kicker sweep at {value} Hz from 300 Hz', startnote=0, startfreq=300,
            endfreq=value)
    for value in (100, 300, 1500):
        add(f'length-{value}', f'Set the kicker length to {value} ms', decay=value)
    for value in (20, 60, 100):
        add(f'distortion-{value}', f'Set the kicker distortion to {value} at the start and the end', dist=value,
            distend=value)
    add('distortion-falls', 'Let the kicker distortion fall from 80 to 0', dist=80, distend=0)
    add('distortion-rises', 'Let the kicker distortion rise from 0 to 80', dist=0, distend=80)
    for value in (0.3, 2, 4):
        add(f'gain-{label(value)}', f'Set the kicker gain to {value}', gain=value)
    for value in (0.05, 0.5, 1.0):
        add(f'envelope-slope-{label(value)}', f'Set the kicker envelope slope to {value}', env=value)
    point(suite, 'kicker-noise-0-5', 'Mix noise into the kicker at 0.5 over 32 notes', 'kicker',
          {'version': 1, 'noise': 0.5}, [(i * 48, 48, 57 + 2 * (i % 4)) for i in range(32)],
          projection=noise_projection)
    for value in (0.0, 0.7, 1.0):
        add(f'click-{label(value)}', f'Set the kicker click to {value}', click=value)
    for value in (0.01, 0.3, 1.0):
        add(f'frequency-slope-{label(value)}', f'Set the kicker frequency slope to {value}', slope=value)
    add('start-note-off', 'Play the kicker from its start frequency instead of the note', startnote=0)
    add('end-note-on', 'End the kicker sweep at the note', endnote=1)


SOLO_VOLUME = 100


def solo(number, volume=SOLO_VOLUME, **params):
    values = {f'o{other}vol': 0 for other in (1, 2, 3) if other != number}
    values[f'o{number}vol'] = volume
    values.update(params)
    return values


def monstro_points(suite):
    def add(scenario, description, values, notes=SEQUENCE):
        point(suite, 'monstro-' + scenario, description, 'monstro', values, notes)

    add('default', 'Play four notes on a Monstro track with its default settings', {})
    for volume in (20, 60, 150):
        add(f'osc1-volume-{volume}', f'Set the Monstro oscillator 1 volume to {volume}', solo(1, volume))
    for pan in (-100, -50, 50, 100):
        add(f'osc1-pan-{label(pan)}', f'Pan the Monstro oscillator 1 to {pan}', solo(1, o1pan=pan))
    for coarse in (-12, 12):
        add(f'osc1-coarse-{label(coarse)}', f'Tune the Monstro oscillator 1 by {coarse} semitones',
            solo(1, o1crs=coarse))
    add('osc1-fine-detune', 'Detune the Monstro oscillator 1 by -50 cents on the left and 50 on the right',
        solo(1, o1ftl=-50, o1ftr=50))
    add('osc1-fine-detune-left', 'Detune the left channel of the Monstro oscillator 1 by 100 cents',
        solo(1, o1ftl=100))
    add('osc1-phase-offset', 'Offset the stereo phase of the Monstro oscillator 1 by 90 degrees', solo(1, o1spo=90))
    for width in (10, 30, 70):
        add(f'osc1-pulse-width-{width}', f'Set the Monstro oscillator 1 pulse width to {width}', solo(1, o1pw=width))
    # The ramp wave (3) is the mirror image of the saw wave (2) and renders like it within the observation tolerances.
    for wave in (0, 1, 2, 4, 5, 6, 7, 8):
        add(f'osc2-wave-{wave}', f'Play the Monstro oscillator 2 with wave {wave}', solo(2, o2wav=wave))
    for coarse in (-12, 7):
        add(f'osc2-coarse-{label(coarse)}', f'Tune the Monstro oscillator 2 by {coarse} semitones',
            solo(2, o2crs=coarse))
    add('osc2-detune', 'Detune the Monstro oscillator 2 by -60 cents on the left and 60 on the right',
        solo(2, o2ftl=-60, o2ftr=60))
    add('osc2-pan-minus-50', 'Pan the Monstro oscillator 2 to -50', solo(2, o2pan=-50))
    add('osc2-pan-50', 'Pan the Monstro oscillator 2 to 50', solo(2, o2pan=50))
    add('osc2-pan-100', 'Pan the Monstro oscillator 2 to 100', solo(2, o2pan=100))
    add('osc2-sync-hard', 'Sync the Monstro oscillator 2 hard to oscillator 1',
        solo(2, o1ssr=1, o2syn=1, o2crs=7))
    add('osc2-sync-reverse', 'Sync the Monstro oscillator 2 in reverse to oscillator 1',
        solo(2, o1ssr=1, o1ssf=1, o2synr=1, o2crs=7))
    for wave in (1, 2, 4):
        add(f'osc3-first-wave-{wave}', f'Play the Monstro oscillator 3 with first wave {wave}, tuned up 12 semitones',
            solo(3, o3sub=-100, o3wav1=wave, o3crs=12))
        add(f'osc3-second-wave-{wave}', f'Play the Monstro oscillator 3 with second wave {wave}, tuned down 12 semitones',
            solo(3, o3sub=100, o3wav2=wave, o3crs=-12))
    for sub in (-50, 0, 50):
        add(f'osc3-sub-mix-{label(sub)}', f'Mix the two waves of the Monstro oscillator 3 at {sub}',
            solo(3, o3sub=sub, o3wav1=2, o3wav2=4))
    add('osc3-coarse-12', 'Tune the Monstro oscillator 3 up by 12 semitones', solo(3, o3crs=12))
    for mode in range(4):
        add(f'osc2-modulates-osc3-{mode}', f'Let the Monstro oscillator 2 modulate oscillator 3 in mode {mode}',
            {'o1vol': 0, 'o2vol': 80, 'o3vol': 80, 'o2wav': 0, 'o2crs': 12, 'o23mo': mode})
    add('envelope-attack-400', 'Fade in the Monstro volume with an envelope attack of 400 ms',
        solo(1, v1e1=1.0, e1att=400))
    add('envelope-attack-900', 'Fade in the Monstro volume with an envelope attack of 900 ms',
        solo(1, v1e1=1.0, e1att=900))
    add('envelope-decay', 'Decay the Monstro volume to a sustain of 0.2 in 500 ms',
        solo(1, v1e1=1.0, e1dec=500, e1sus=0.2), [(0, 192, 57)])
    add('envelope-hold-and-decay', 'Hold the Monstro envelope for 300 ms, then decay to a sustain of 0.2',
        solo(1, v1e1=1.0, e1hol=300, e1dec=500, e1sus=0.2), [(0, 192, 57)])
    add('envelope-predelay', 'Delay the Monstro envelope by 300 ms before an attack of 300 ms',
        solo(1, v1e1=1.0, e1pre=300, e1att=300), [(0, 192, 57)])
    add('envelope-release', 'Release the Monstro volume over 800 ms after a short note',
        solo(1, v1e1=1.0, e1rel=800), [(0, 24, 57)])
    for slope in (-0.8, 0.8):
        add(f'envelope-slope-{label(slope)}', f'Curve the Monstro envelope attack of 600 ms with a slope of {slope}',
            solo(1, v1e1=1.0, e1att=600, e1slo=slope))
    for amount, rate in ((0.5, 400), (1.0, 400), (0.5, 1000)):
        add(f'lfo-pitch-{label(amount)}-rate-{rate}',
            f'Modulate the Monstro oscillator 1 pitch with LFO 1 of amount {amount} and a rate of {rate} ms',
            solo(1, f1l1=amount, l1rat=rate), [(0, 192, 57)])
    add('lfo-volume', 'Modulate the Monstro volume with LFO 1 at a rate of 600 ms',
        solo(1, v1l1=1.0, l1rat=600), [(0, 192, 57)])
    add('lfo-volume-wave-4', 'Modulate the Monstro volume with LFO 1 wave 4 at a rate of 600 ms',
        solo(1, v1l1=1.0, l1rat=600, l1wav=4), [(0, 192, 57)])
    add('lfo2-pitch', 'Modulate the Monstro oscillator 1 pitch with LFO 2 of amount 0.5 and a rate of 500 ms',
        solo(1, f1l2=0.5, l2rat=500), [(0, 192, 57)])


def opl2_points(suite):
    def add(scenario, description, notes=SEQUENCE, **params):
        # The plugin is named OPL2 (library libOPL2.so); a project that names opl2 loads no instrument.
        point(suite, 'opl2-' + scenario, description, 'OPL2', params, notes)

    add('default', 'Play four notes on an OPL2 track with its default settings')
    for wave in (1, 2, 3):
        add(f'op1-waveform-{wave}', f'Play operator 1 of the OPL2 with waveform {wave}', op1_waveform=wave)
        add(f'op2-waveform-{wave}', f'Play operator 2 of the OPL2 with waveform {wave}', op2_waveform=wave)
    for value in (2, 5, 9):
        add(f'op1-multiple-{value}', f'Set the frequency multiple of OPL2 operator 1 to {value}', op1_mul=value)
    # A multiple of 4 on operator 2 was not reproducible between two runs of the reference, so it is left out.
    for value in (2, 8):
        add(f'op2-multiple-{value}', f'Set the frequency multiple of OPL2 operator 2 to {value}', op2_mul=value)
    for value in (3, 7):
        add(f'feedback-{value}', f'Set the OPL2 feedback to {value}', feedback=value)
    for value in (30, 50):
        add(f'op1-level-{value}', f'Set the level of OPL2 operator 1 to {value}', op1_lvl=value)
        add(f'op2-level-{value}', f'Set the level of OPL2 operator 2 to {value}', op2_lvl=value)
    for value in (4, 10):
        add(f'op2-attack-{value}', f'Set the attack of OPL2 operator 2 to {value}', op2_a=value)
    for value in (7, 12):
        add(f'op2-decay-{value}', f'Set the decay of OPL2 operator 2 to {value}', op2_d=value)
    for value in (4, 8):
        add(f'op2-sustain-{value}', f'Set the sustain of OPL2 operator 2 to {value}', op2_s=value)
    for value in (4, 8):
        add(f'op2-release-{value}', f'Set the release of OPL2 operator 2 to {value}', op2_r=value)
    add('high-notes', 'Play four high notes on an OPL2 track with its default settings', HIGH)
    # The level scaling of the two OPL2 operators changed nothing in the render, even on the keys 84 to 90.
    add('op1-ksr', 'Switch on key scaling rate for OPL2 operator 1', op1_ksr=1)
    add('op2-ksr', 'Switch on key scaling rate for OPL2 operator 2', op2_ksr=1)
    # The percussive switch of OPL2 operator 1 changed nothing in the render, even in additive mode.
    add('op2-percussive', 'Switch on the percussive envelope of OPL2 operator 2', op2_perc=1)
    add('op1-tremolo-off', 'Switch off the tremolo of OPL2 operator 1', op1_trem=0)
    add('op2-tremolo-on', 'Switch on the tremolo of OPL2 operator 2', op2_trem=1)
    add('op1-vibrato-on', 'Switch on the vibrato of OPL2 operator 1', op1_vib=1)
    add('op2-vibrato-off', 'Switch off the vibrato of OPL2 operator 2', op2_vib=0)
    add('additive', 'Combine the two OPL2 operators additively instead of FM', fm=0, op1_lvl=50)
    add('vibrato-depth', 'Switch on the deep OPL2 vibrato', vib_depth=1)
    add('tremolo-depth', 'Switch on the deep OPL2 tremolo', trem_depth=1)


def build(suite):
    lb302_points(suite)
    kicker_points(suite)
    monstro_points(suite)
    opl2_points(suite)

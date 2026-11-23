"""Saved projects and preference state verified through public reopen and the runtime's restart."""
from __future__ import annotations
import copy, itertools
from semantic import assert_audio_equal, AudioTolerance, compare_observations

FIXTURES=('tone-440','stereo-pair','segments','ramp','noise','dc-positive')
# Track and label values read back from a reopened project compare with the observation tolerance.
TOLERANCE=dict(absolute=1.5/32768,relative=5e-4)

def _needs(key):
    return lambda ctx:ctx.state[key]

def _setup(ctx,name):
    # Removing tracks leaves the previous saved project's filename attached.
    # Each independent save scenario starts with a genuinely new process.
    ctx.restart()
    ctx.new_scenario('persist-'+name)
    ctx.import_audio(name)
    ctx.require('SelectAll')
    ctx.export_audio(channels=2 if 'stereo' in name else 1)
    ctx.state['original']=ctx.last_audio
    return {'fixture':name,'loaded':True}

def _mutate(ctx,kind,value):
    ctx.require('SelectAll')
    if kind=='name':ctx.require('SetTrackStatus',Name=value)
    elif kind=='gain':ctx.require('SetTrackAudio',Gain=value,Pan=20)
    elif kind=='reverse':ctx.require('Reverse')
    elif kind=='fade':ctx.require('FadeIn')
    elif kind=='trim':
        end=max(x['end'] for x in ctx.info('Tracks'))
        ctx.select(end*.15,end*.85);ctx.require('Trim');ctx.require('SelectAll')
    elif kind=='label':
        ctx.require('Select',Start=.1,End=.3,Track=0,TrackCount=1)
        ctx.require('AddLabel');ctx.require('SetLabel',Label=0,Text=value)
        ctx.require('SelectAll')
    return {'kind':kind,'tracks':ctx.info('Tracks'),'clips':ctx.info('Clips'),'labels':ctx.info('Labels')}

def _save(ctx,name,channels):
    ctx.state.pop('project',None)
    ctx.require('SelectAll');ctx.export_audio(channels=channels)
    ctx.state['saved_audio']=ctx.last_audio
    ctx.state['saved_tracks']=copy.deepcopy(ctx.info('Tracks'))
    ctx.state['saved_clips']=copy.deepcopy(ctx.info('Clips'))
    ctx.state['saved_labels']=copy.deepcopy(ctx.info('Labels'))
    # A basename: the runtime places saved projects in its owned project area.
    document=name+'.aup'
    result=ctx.command('SaveProject2',Filename=document,AddToHistory=False)
    assert result['ok'],'saved project was not written'
    assert len(ctx.take(document))>0,'saved project was not written'
    ctx.state['project']=document
    return {'saved':True}

def _reopen(ctx):
    document=ctx.state['project']
    # A new process cannot reuse the currently loaded in-memory project.
    # Opening an already-open .aup in 2.4.2 prompts and blocks the pipe. The
    # runtime acknowledges the product's orphan-block-file notice while the
    # command runs (saving a destructive edit and terminating the process
    # retains blocks used by Undo).
    ctx.restart()
    result=ctx.command('OpenProject2',Filename=document,AddToHistory=False)
    assert result['ok'],'saved project could not be reopened'
    return {'opened':True}

def _inspect(ctx,channels):
    ctx.require('SelectAll');ctx.export_audio(channels=channels)
    wanted=ctx.state['saved_audio']
    assert_audio_equal(ctx.last_audio,wanted,tolerance=AudioTolerance(absolute=1/32768+1e-7))
    tracks=ctx.info('Tracks')
    # Focus/selection flags can differ after reopen; named track values, order,
    # gain/pan, extent and channel semantics must survive.
    fields=('name','kind','start','end','channels','mute','solo','gain','pan')
    projection=lambda rows:[{k:x[k] for k in fields if k in x} for x in rows]
    compare_observations(projection(tracks),projection(ctx.state['saved_tracks']),**TOLERANCE)
    labels=ctx.info('Labels')
    compare_observations(labels,ctx.state['saved_labels'],**TOLERANCE)
    return {'audio_restored':True,'tracks':projection(tracks),'clips':ctx.info('Clips'),'labels':labels}

def _preference_restart(ctx,name,values):
    ctx.restart()
    restored=[]
    for value in values:
        ctx.require('SetPreference',Name=name,Value=value,Reload=False)
        def read():
            actual=ctx.require('GetPreference',Name=name)
            return str(actual).lower() if isinstance(actual,bool) else str(actual)
        assert read()==value, 'preference was not applied'
        ctx.restart()
        assert read()==value, 'preference was lost on process restart'
        restored.append(value)
    return {'name':name,'restored_values':restored}

def build(s):
    # Each mode changes independent state, and every saved file is verified
    # through a new export, never by rereading the old export artifact.
    # Unicode filename/label behavior is driven and read through the GUI.
    # 2.4.2's scripting JSON writer corrupts non-ASCII string fields, so these
    # scripting metadata/restart scenarios use readable ASCII values.
    edits=(('name','Saved track'),('gain',-6),('reverse',None),('fade',None),('trim',None),('label','Saved marker'))
    for fixture,(kind,value) in itertools.product(FIXTURES,edits):
        scenario=fixture+'-'+kind
        channels=2 if 'stereo' in fixture else 1
        s.add('project-fixture',scenario,'import',lambda c,f=fixture:_setup(c,f),channel='setup')
        s.add('project-save',scenario,'edit',lambda c,k=kind,v=value:_mutate(c,k,v))
        s.add('project-save',scenario,'save',lambda c,n=scenario,ch=channels:_save(c,n,ch))
        s.add('project-save',scenario,'reopen',_reopen,needs=_needs('project'))
        s.add('project-save',scenario,'inspect-reopened',lambda c,ch=channels:_inspect(c,ch),needs=_needs('saved_audio'))
        # Restart is expensive but essential; cover different persisted entity
        # types and every waveform/channel class without repeating 36 restarts.
        # open-saved restarts the application (same instance data) and opens the saved project.
        if kind in ('name','reverse'):
            s.add('project-restart',scenario,'open-saved',_reopen,needs=_needs('project'))
            s.add('project-restart',scenario,'new-export',lambda c,ch=channels:_inspect(c,ch),needs=_needs('saved_audio'))
            s.add('project-restart',scenario,'edit-after-reopen',lambda c:_mutate(c,'name','After restart'))
            s.add('project-restart',scenario,'save-again',lambda c,n=scenario,ch=channels:_save(c,n,ch))
            s.add('project-restart',scenario,'reopen-again',_reopen,needs=_needs('project'))
            s.add('project-restart',scenario,'verify-second-save',lambda c,ch=channels:_inspect(c,ch),needs=_needs('saved_audio'))
    for scenario,name,values in (
        ('boolean','/GUI/BeepOnCompletion',('true','false')),
        ('enum','/GUI/EnvdBRange',('72','96')),
        ('text','/GUI/TrackNames/DefaultTrackName',('Saved track name','Audio Track')),
    ):
        s.add('preference-restart',scenario,'set-restart-read',
              lambda c,n=name,v=values:_preference_restart(c,n,v),
              description='Set a public preference, verify it in a new process, change it and verify again.')

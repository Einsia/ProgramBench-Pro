from evaluation.contract import files_path
"""User goals and visible outcomes; operation recipes are reference-only."""


def path(key,name,area='inputs'):
    return files_path(area, name)


def step(key,goal,acceptance,recipe,checks=(),depends=(),lifecycle=None):
    return dict(id=key,goal=goal,acceptance=acceptance,recipe=recipe,checks=list(checks),
                depends_on=list(depends),**({'lifecycle':lifecycle} if lifecycle else {}))


def episode(key,feature,steps,files=('chart.png',)):
    for cp in steps:
        if any(c['kind']=='module' for c in cp['checks']) and feature not in ('history','history-management') and not any(s['op']=='save-edit' for s in cp['recipe']):
            cp['goal']+=' Save the edit to the image\'s XMP sidecar and finish with its editing controls visible.'
            cp['recipe'].append({'op':'save-edit'})
        cp['depends_on']=['setup:documents',*cp['depends_on']]
        cp['assertions']=[{'id':key+'/'+cp['id']+'/visible','channel':'frontend','method':'agent','requirement':cp['acceptance']}]
        for i,check in enumerate(cp.pop('checks')):
            cp['assertions'].append({'id':key+'/'+cp['id']+'/state-'+str(i+1),'channel':'backend','method':'program',
                'requirement':check.get('description','The saved product document contains the requested result.'),'check':check})
    return {'id':key,'feature':feature,'execution':'gui','initial_state':'Fresh library and application settings, with the listed input images available for import.',
        'setup':[{'id':'documents','files':list(files)}],
        'inputs':{'documents':{path(key,name):'A GPX track spanning 2024-01-01 00:00:00 UTC; its midpoint is latitude 51.5 and longitude -0.12.' if name.endswith('.gpx') else 'A public style document named Bright study with exposure +1.5 EV and description Exposure example.' if name.endswith('.dtstyle') else 'Synthetic '+name.split('.')[0]+' image, '+('768 by 576' if '-large' in name else '192 by 144')+' pixels.' for name in files}},
        'session':'Operate the visible photo application. Input images are already present at the specified absolute paths.',
        'allowed_equivalents':['Equivalent controls, shortcuts, menu commands and selection routes are acceptable.',
                              'Judge functional results; layout, wording and control types may differ.'],
        'forbidden_bypasses':['Do not use other applications, commands, private files or pre-edited replacement documents.'],
        'budget':({'calls':400,'tokens':6000000,'seconds':3600} if key=='styles-lifecycle' else
                  {'calls':300,'tokens':4500000,'seconds':3000} if key in ('styles-create','history-lifecycle','view-assistance','collection-rules') else
                  {'calls':220,'tokens':3000000,'seconds':2400}),'checkpoints':steps}


def xm(**expect):return {'kind':'xmp','expect':expect,'keys':list(expect)}
def module_check(name,field,offset,value):
    return {'kind':'module','module':name,'fields':[[field,'f',offset]],'expect':{'enabled':1,field:value}}
def click(name,role='label'):return {'op':'click-match','match':{'name':name,'role':role}}
def desc(text,role='push button'):return {'op':'click-match','match':{'description':text,'role':role}}


def build():
    out=[]
    key='library-rating'
    out.append(episode(key,'library',[
        step('import','Add '+path(key,'chart.png')+' to the image library and select it.',
             'The library contains the color chart as an image thumbnail, and the image is selected.',
             [{'op':'import','files':['chart.png']}],[xm(rating=1)]),
        step('three','Set the selected image rating to three stars.',
             'The selected image has a three-star rating.',[{'op':'press','key':'3'}],[xm(rating=3)],['import']),
        step('five','Change the selected image rating to five stars.',
             'The selected image has a five-star rating.',[{'op':'press','key':'5'}],[xm(rating=5)],['three']),
        step('persist','Verify the image and its five-star rating after the application restarts.',
             'The image remains in the library with its five-star rating.',[{'op':'press','key':'Control+a'}],[xm(rating=5)],['five'],lifecycle='restart')]))
    key='library-labels'
    out.append(episode(key,'color-labels',[
        step('red','Import '+path(key,'chart.png')+' and give it a red color label.',
             'The chart thumbnail visibly carries a red label.',[{'op':'import'},{'op':'press','key':'F1'}],[xm(labels=[0])]),
        step('green','Also give the same image a green color label.',
             'The same image has both red and green labels.',[{'op':'press','key':'F3'}],[xm(labels=[0,2])],['red']),
        step('blue','Remove its red label and add a blue label, keeping green.',
             'The image now carries green and blue labels.',[{'op':'press','key':'F1'},{'op':'press','key':'F4'}],[xm(labels=[2,3])],['green'])]))
    key='library-metadata'
    steps=[]
    for i,(field,value) in enumerate((('title','Coastal colours'),('creator','Zoë García'),('rights','© 2024 Example'),('description','Blue sky & red sand'))):
        ops=([{'op':'import'},{'op':'panel','name':'metadata editor'}] if i==0 else [])+[{'op':'metadata','field':field,'value':value}]
        goal=('Import '+path(key,'chart.png')+' and ' if i==0 else '')+'set its '+field+' to '+repr(value)+'.'
        steps.append(step(field,goal,'The image '+field+' is shown as '+repr(value)+'.',ops,[xm(**{field:value})],[steps[-1]['id']] if steps else []))
    out.append(episode(key,'metadata',steps))
    key='library-tags'
    out.append(episode(key,'tags',[
        step('attach','Import '+path(key,'chart.png')+' and attach the hierarchical tag "places|coast".',
             'The selected image has the attached hierarchical tag places|coast.',
             [{'op':'import'},{'op':'panel','name':'tagging'},{'op':'tag','value':'places|coast'}],[xm(tags=['places|coast'])]),
        step('unicode','Also attach the tag "色彩 study" to the same image.',
             'Both places|coast and 色彩 study are attached to the selected image.',
             [{'op':'tag','value':'色彩 study'}],[xm(tags=['places|coast','色彩 study'])],['attach']),
        step('detach','Detach places|coast from the image, keeping 色彩 study.',
             'The attached-tag list contains 色彩 study and no longer includes places|coast.',
             [click('places|coast','table cell'),click('detach','push button')],[xm(tags=['色彩 study'])],['unicode']),
        step('persist','After restart, select the image and show its attached tags.',
             'The image retains its 色彩 study tag after restarting.',
             [{'op':'press','key':'Control+a'}],[xm(tags=['色彩 study'])],['detach'],lifecycle='restart')]))
    key='library-filter'
    gallery=('chart.png','portrait.png','texture.png')
    out.append(episode(key,'collections',[
        step('gallery','Import the three provided images, and give chart.png a red label while leaving the other two without color labels.',
             'The library shows the three different images; chart.png alone has a red label.',
             [{'op':'import'},{'op':'select-image','file':'chart.png'},{'op':'press','key':'F1'}],
             [xm(labels=[0])]),
        step('filter','Filter the collection to show only images with a red color label.',
             'Only chart.png is shown in the filtered collection.',
             [{'op':'click-match','match':{'description':'filter by images color label','role':'push button','nth':0}}],
             [],['gallery']),
        step('restore','Clear the red color-label filter.',
             'All three images are shown again.',
             [{'op':'click-match','match':{'description':'filter by images color label','role':'push button','nth':0}}],
             [],['filter']),
        step('select','Select portrait.png and texture.png together, leaving chart.png unselected.',
             'Exactly the portrait and texture images are selected.',
             [{'op':'select-image','file':'portrait.png'},{'op':'select-image','file':'texture.png','add':True}],[],['restore'])],files=gallery))
    # The changes are deliberately large enough to be visible, with independently parsed saved parameter values.
    mods=[
      ('exposure','exposure','exposure','adjust the exposure correction',1.5,8,0.0),
      ('colorcontrast','color contrast','green-magenta contrast','steepness of the a* curve',2.5,0,1.0),
      ('colorize','colorize','lightness','lightness of color',75.,12,50.),
      ('velvia','velvia','strength','the strength of saturation boost',70.,0,25.),
      ('vignette','vignetting','brightness','strength of effect on brightness',-.8,8,-.5),
      ('graduatednd','graduated density','density','the density in EV for the filter',3.,0,1.),
      ('bloom','bloom','threshold','the threshold of light',30.,4,90.),
      ('soften','soften','mix','the mix of effect',85.,12,50.),
      ('sharpen','sharpen','amount','strength of the sharpen',1.5,4,.5),
      ('bilat','local contrast','detail','changes the local contrast',180.,12,.25),
      ('colorbalancergb','color balance rgb','hue shift','rotate all hues by an angle',90.,92,0.),
      ('borders','framing','border size','size of the border in percent',20.,40,.1),
    ]
    for internal,display,field,tooltip,value,offset,default in mods:
        key='edit-'+internal
        stored=(value-100)/100 if internal=='bilat' else value/100 if internal=='borders' else value
        source='texture.png' if internal in ('sharpen','soften','bilat','bloom') else 'chart.png'
        check=module_check(internal,field,offset,stored);check['file']=source
        reset=module_check(internal,field,offset,default);reset['file']=source
        out.append(episode(key,'darkroom-processing',[
            step('adjust','Import '+path(key,source)+', open it for editing, and set the '+display+' '+field+' to '+str(value)+'.',
                 'The image is open for editing with '+display+' enabled, and '+field+' shows '+str(value)+'.',
                 [{'op':'import'},{'op':'darkroom'},{'op':'module','name':display},{'op':'slider','description':tooltip,'value':value}],[check]),
            step('reset','Reset the parameters of '+display+' to their defaults.',
                 'The '+display+' controls show their default values again, including '+field+' '+str(default*100+100 if internal=='bilat' else default*100 if internal=='borders' else default)+'.',
                 [desc('reset parameters')],[reset],['adjust'])],files=(source,)))
    key='edit-orientation'
    out.append(episode(key,'orientation',[
        step('rotate','Import '+path(key,'chart.png')+' and rotate the image 90 degrees clockwise in the editor.',
             'The rectangular chart is rotated clockwise into portrait orientation.',
             [{'op':'import'},{'op':'darkroom'},{'op':'module','name':'orientation'},desc('rotate 90 degrees CW')],
             [{'kind':'module','module':'flip','fields':[['orientation','i',0]],'expect':{'orientation':5}}]),
        step('mirror','Flip the rotated image horizontally.',
             'The portrait chart is mirrored horizontally relative to the preceding state.',[desc('flip horizontally')],
             [{'kind':'module','module':'flip','fields':[['orientation','i',0]]}],['rotate']),
        step('reset','Reset the image orientation to the original.',
             'The chart returns to its original landscape orientation.',[desc('reset parameters')],
             [{'kind':'module','module':'flip','fields':[['orientation','i',0]],'expect':{'orientation':-1}}],['mirror'])]))
    key='edit-monochrome'
    out.append(episode(key,'monochrome',[
        step('mono','Import '+path(key,'chart.png')+' and turn on the monochrome module in the image editor.',
             'The editor shows a black-and-white version of the chart, with monochrome enabled.',
             [{'op':'import'},{'op':'darkroom'},{'op':'module','name':'monochrome'},desc("'monochrome' is switched off",'toggle button')],
             [{'kind':'module','module':'monochrome','expect':{'enabled':1}}]),
        step('color','Disable monochrome while keeping the module available.',
             'The chart is colored again, and monochrome is disabled.',
             [desc("'monochrome' is switched on",'toggle button')],[{'kind':'module','module':'monochrome','expect':{'enabled':0}}],['mono'])]))
    key='edit-history'
    out.append(episode(key,'history',[
        step('bright','Import '+path(key,'chart.png')+', open it for editing and set exposure to +2 EV.',
             'The chart is brighter and the enabled exposure module shows +2 EV.',
             [{'op':'import'},{'op':'darkroom'},{'op':'module','name':'exposure'},{'op':'slider','description':'adjust the exposure correction','value':2.}],
             []),
        step('lower','Change exposure to -1 EV.',
             'The chart becomes darker and exposure shows -1 EV.',
             [{'op':'slider','description':'adjust the exposure correction','value':-1.}],[],['bright']),
        step('undo','Undo the last exposure change.',
             'Exposure returns to +2 EV and the brighter chart is restored.',[{'op':'press','key':'Control+z'},
              {'op':'fill','target':{'role':'text','name':'Search'},'value':'exposure'}],
             [],['lower']),
        step('redo','Redo the exposure change and save the edit to its XMP sidecar, finishing in the editor.',
             'Exposure is -1 EV again and the darker chart is restored.',[{'op':'press','key':'Control+y'},
              {'op':'fill','target':{'role':'text','name':'Search'},'value':'exposure'},{'op':'save-edit'}],
             [module_check('exposure','exposure',8,-1.)],['undo'])]))
    for fmt,suffix in (('JPEG','.jpg'),('PNG','.png'),('TIFF','.tif'),('WebP','.webp')):
        key='export-'+suffix[1:];name='chart-export'+suffix
        out.append(episode(key,'export',[
            step('export','Import '+path(key,'chart.png')+' and export it as '+fmt+' to '+path(key,name,'outputs')+'. Leave the export settings visible.',
                 'The export panel is configured for '+fmt+' and the specified output destination.',
                 [{'op':'import'},{'op':'export','file':path(key,name,'outputs'),'format':fmt}],
                 [{'kind':'export','file':name}]),
            step('resized','Export the image again as '+fmt+' with maximum width 96 pixels to '+path(key,'small'+suffix,'outputs')+'. Leave the export settings visible.',
                 'The export settings show '+fmt+' and a maximum width of 96 pixels.',
                 [{'op':'export','file':path(key,'small'+suffix,'outputs'),'format':fmt,'width':96}],
                 [{'kind':'export','file':'small'+suffix}],['export'])]))
    key='library-duplicate'
    out.append(episode(key,'duplicates',[
        step('duplicate','Import '+path(key,'chart.png')+' and create a duplicate image version.',
             'The library contains two versions of the chart image.',
             [{'op':'import'},{'op':'panel','name':'actions on selection'},click('duplicate','push button')],
             [{'kind':'duplicate','count':2}]),
        step('rate','Select all versions of the chart and rate them four stars.',
             'Both chart versions have a four-star rating.',[{'op':'press','key':'Control+a'},{'op':'press','key':'4'}],
             [{'kind':'duplicate','count':2,'rating':4}],['duplicate'])]))
    key='styles-create'
    out.append(episode(key,'styles',[
        step('create','Import '+path(key,'chart.png')+', set exposure to +1.5 EV, and save the edit as a style named "Bright study" with description "Exposure example". Export the style to '+path(key,'styles','outputs')+' and show it in the style list.',
             'Bright study is available in the style list.',
             [{'op':'import'},{'op':'darkroom'},{'op':'module','name':'exposure'},{'op':'slider','description':'adjust the exposure correction','value':1.5},
              click('lighttable'),{'op':'panel','name':'styles'},{'op':'create-style','name':'Bright study','description':'Exposure example'},
              {'op':'export-style','name':'Bright study','directory':path(key,'styles','outputs')}],
             [{'kind':'style','file':'styles/Bright study.dtstyle','expect':{'name':'Bright study','description':'Exposure example','exposures':[1.5]}}]),
        step('persist','After restarting, select the image and export the saved Bright study style to '+path(key,'reopened','outputs')+'. Leave the style list visible.',
             'Bright study remains available after restarting.',
             [{'op':'press','key':'Control+a'},{'op':'fill','target':{'role':'text','name':'filter style names'},'value':'Bright study'},
              {'op':'export-style','name':'Bright study','directory':path(key,'reopened','outputs')}],
             [{'kind':'style','file':'reopened/Bright study.dtstyle','expect':{'name':'Bright study','description':'Exposure example','exposures':[1.5]}}],['create'],lifecycle='restart')]))
    out[-1]['setup'][0]['directories']=['outputs/styles','outputs/reopened']
    key='edit-crop'
    out.append(episode(key,'crop',[
        step('crop','Import '+path(key,'chart.png')+' and crop 20 percent from the left edge using the crop margins.',
             'The crop controls show a left margin of 20 percent, and the selected crop excludes the left fifth of the image.',
             [{'op':'import'},{'op':'darkroom'},{'op':'module','name':'crop'},click('margins'),
              {'op':'slider','description':'the left margin cannot','value':20.}],
             [module_check('crop','left',0,.2)]),
        step('reset','Reset the crop to the full image.',
             'The full chart is visible again and the crop margins are reset.',[desc('reset parameters')],
             [{'kind':'module','module':'crop','fields':[['left','f',0]],'expect':{'left':0.}}],['crop'])]))
    key='preferences-persistence'
    out.append(episode(key,'preferences',[
        step('enabled','Enable the lighttable preference to show image time with milliseconds. Leave that preference visible.',
             'The preference for displaying image times with milliseconds is enabled.',
             [{'op':'preferences'},{'op':'check','target':{'role':'check box','name':'defines whether time should be displayed with milliseconds'},'checked':True}],
             []),
        step('persist','After restarting, show the same lighttable preference.',
             'The preference for displaying image times with milliseconds remains enabled after restarting.',
             [{'op':'preferences'}],[],['enabled'],lifecycle='restart')],files=()))
    key='library-culling'
    out.append(episode(key,'viewing',[
        step('compare','Import all three provided images, select them all, and show them together in a culling view for comparison.',
             'All three images are presented together at a useful comparison size.',
             [{'op':'import'},desc('click to enter culling layout in dynamic mode.','toggle button')]),
        step('grid','Return to the thumbnail grid and display three thumbnails per row.',
             'The library is back in the thumbnail grid with the three images arranged in one row.',
             [desc('click to enter filemanager layout.','toggle button'),{'op':'fill','target':{'role':'spin button','name':'set the number of thumbnails per row','exact':False},'value':'3'}],[],['compare'])],files=gallery))
    key='geotag-track'
    out.append(episode(key,'geotagging',[
        step('locate','Import '+path(key,'chart.png')+' and geotag it using '+path(key,'walk.gpx')+' with camera time zone UTC. Show the resulting location in image information.',
             'Image information shows latitude 51.5 north and longitude 0.12 west (equivalent coordinate formats are acceptable).',
             [{'op':'import','files':['chart.png']},{'op':'panel','name':'geotagging'},click('apply GPX track file...','push button'),
              {'op':'chooser','path':path(key,'walk.gpx')},
              {'op':'wait','seconds':2},click('image information')],
             [{'kind':'gps','latitude':51.5,'longitude':-.12}])],files=('chart.png','walk.gpx')))
    import lifecycle
    out.extend(lifecycle.build())
    return out

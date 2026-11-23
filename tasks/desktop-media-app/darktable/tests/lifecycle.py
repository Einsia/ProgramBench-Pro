"""Local asset, history, style and view lifecycle episodes."""


def build():
    from specification import episode,step,path,click,desc,module_check
    out=[]
    def files(*present,absent=()):return {'kind':'files','present':list(present),'absent':list(absent)}
    def history(file,ev):return {**module_check('exposure','exposure',8,ev),'file':file}
    key='library-copy-import'
    out.append(episode(key,'file-management',[
        step('copy-import','Copy and import '+path(key,'chart.png')+' into '+path(key,'incoming/batch','outputs')+' under the new filename copied-chart.png, keeping the original source file.',
             'The library contains copied-chart.png from the batch folder.',
             [{'op':'copy-import','directory':path(key,'incoming','outputs')}],
             [files('inputs/chart.png','outputs/incoming/batch/copied-chart.png'),
              {'kind':'file-copy','file':'outputs/incoming/batch/copied-chart.png','source':'chart.png'}])]))
    out[-1]['setup'][0]['directories']=['outputs/incoming']
    key='library-file-transfer'
    out.append(episode(key,'file-management',[
        step('copy','Import '+path(key,'chart.png')+' and copy it to '+path(key,'copied','outputs')+' using the library file-copy command.',
             'The library shows the copied chart from the copied folder.',
             [{'op':'import'},{'op':'panel','name':'actions on selection'},click('copy...','push button'),{'op':'chooser','path':path(key,'copied','outputs')},{'op':'confirm-dialog'},click('collections')],
             [files('inputs/chart.png','outputs/copied/chart.png'),{'kind':'file-copy','file':'outputs/copied/chart.png','source':'chart.png'}]),
        step('move','Select the copied image in the copied folder and move it to '+path(key,'moved','outputs')+', keeping the original in the inputs folder.',
             'The chart is now associated with the moved folder.',
             [{'op':'select-image','file':'chart.png'},click('move...','push button'),{'op':'chooser','path':path(key,'moved','outputs')},{'op':'confirm-dialog'}],
             [files('inputs/chart.png','outputs/moved/chart.png',absent=['outputs/copied/chart.png'])],['copy'])]))
    out[-1]['setup'][0]['directories']=['outputs/copied','outputs/moved']
    key='library-remove-delete'
    out.append(episode(key,'file-management',[
        step('remove','Import '+path(key,'chart.png')+' and remove the image from the library while keeping its original file.',
             'The library collection is empty after removing the image.',
             [{'op':'import'},{'op':'panel','name':'actions on selection'},click('remove','push button'),{'op':'confirm-dialog'}],
             [files('inputs/chart.png')]),
        step('reimport','Import the same original image again.',
             'The chart appears in the library again.',[{'op':'import'}],[files('inputs/chart.png')],['remove']),
        step('delete','Delete the reimported chart from disk using the application.',
             'The chart is removed from the collection after the deletion.',
             [click('delete (trash)','push button'),{'op':'confirm-dialog'}],[files(absent=['inputs/chart.png'])],['reimport'])]))
    key='library-grouping'
    gallery=('chart.png','portrait.png','texture.png')
    out.append(episode(key,'grouping',[
        step('group','Import the three supplied images and group chart.png with portrait.png, keeping texture.png separate. Collapse the group.',
             'The chart and portrait belong to one collapsible group; the texture remains separate.',
             [{'op':'import'},{'op':'select-image','file':'chart.png'},{'op':'select-image','file':'portrait.png','add':True},
              {'op':'panel','name':'actions on selection'},click('group','push button'),{'op':'grouping','enabled':True}]),
        step('expand','Expand the group to show both members.',
             'Both grouped images and the separate texture image are visible.',[{'op':'grouping','enabled':False}],[],['group']),
        step('ungroup','Ungroup the chart and portrait images.',
             'The chart, portrait and texture are independent images again.',
             [{'op':'press','key':'Control+a'},click('ungroup','push button'),{'op':'grouping','enabled':True}],[],['expand'])],files=gallery))
    key='history-lifecycle'
    out.append(episode(key,'history-management',[
        step('edit','Import both supplied images. On chart.png set exposure to -0.5 EV, color contrast green-magenta contrast to 2.5, then exposure to +1 EV. Return to the library.',
             'The chart thumbnail is visibly brighter; texture is unchanged.',
             [{'op':'import'},{'op':'select-image','file':'chart.png'},{'op':'darkroom'},{'op':'module','name':'exposure'},
              {'op':'slider','description':'adjust the exposure correction','value':-.5},{'op':'module','name':'color contrast'},
              {'op':'slider','description':'steepness of the a* curve','value':2.5},
              {'op':'module','name':'exposure'},
              {'op':'slider','description':'adjust the exposure correction','value':1.},click('lighttable')],
             [history('chart.png',1.)]),
        step('paste','Copy the chart history and paste it to texture.png.',
             'The texture image now has the same exposure edit.',
             [{'op':'panel','name':'history stack'},click('copy','push button'),{'op':'select-image','file':'texture.png'},click('paste','push button')],
             [history('texture.png',1.)],['edit']),
        step('compress','Compress the texture image history, preserving the exposure and color contrast edits. Show the compact history in the editor.',
             'The edited texture remains visible and the history contains the current edits without superseded exposure entries.',
             [click('compress history','push button'),{'op':'darkroom'},click('history')],
             [{'kind':'history-compressed','file':'texture.png'}],['paste']),
        step('discard','Discard the texture image history.',
             'The texture returns to its original appearance.',[click('lighttable'),click('discard history','push button'),{'op':'confirm-dialog'}],
             [{'kind':'history-discarded','file':'texture.png','module':'exposure'}],['compress'])],files=('chart.png','texture.png')))
    key='styles-lifecycle'
    style_check={'kind':'style','file':'styles/Bright study.dtstyle','expect':{'name':'Bright study','description':'Exposure example','exposures':[1.5]}}
    out.append(episode(key,'styles-lifecycle',[
        step('import','Import '+path(key,'bright.dtstyle')+' as a style, then export it to '+path(key,'styles','outputs')+'.',
             'Bright study is available in the style list.',
             [{'op':'panel','name':'styles'},desc('import styles from','push button'),{'op':'chooser','path':path(key,'bright.dtstyle')},
              {'op':'export-style','name':'Bright study','directory':path(key,'styles','outputs')}],[style_check]),
        step('apply','Import '+path(key,'texture.png')+' and apply Bright study to it. Save the edit and show its exposure controls.',
             'The texture has Bright study applied with exposure +1.5 EV.',
             [click('styles'),{'op':'import','files':['texture.png']},{'op':'panel','name':'styles'},
              {'op':'select-style','name':'Bright study'},click('apply','push button'),{'op':'darkroom'},{'op':'module','name':'exposure'}],
             [history('texture.png',1.5)],['import']),
        step('edit','Change the style description to "Revised exposure" and export the updated style to '+path(key,'revised','outputs')+'. Leave the revised description visible.',
             'The style retains its name and has the revised description.',
             [click('lighttable'),{'op':'panel','name':'styles'},{'op':'select-style','name':'Bright study'},click('edit...','push button'),
              {'op':'style-description','value':'Revised exposure'},
              {'op':'export-style','name':'Bright study','directory':path(key,'revised','outputs')},click('edit...','push button')],
             [{'kind':'style','file':'revised/Bright study.dtstyle','expect':{'name':'Bright study','description':'Revised exposure','exposures':[1.5]}}],['apply']),
        step('remove','Remove Bright study from the style library.',
             'The style list no longer contains Bright study.',[{'op':'press','key':'Escape'},{'op':'select-style','name':'Bright study'},desc('removes the selected styles','push button'),{'op':'confirm-dialog'}],[],['edit'])],files=('texture.png','bright.dtstyle')))
    out[-1]['setup'][0]['directories']=['outputs/styles','outputs/revised']
    key='snapshot-restore'
    out.append(episode(key,'snapshots',[
        step('snapshot','Import '+path(key,'chart.png')+', set exposure to +1.5 EV and take a snapshot of that edit.',
             'A snapshot of the bright chart is listed.',
             [{'op':'import'},{'op':'darkroom'},{'op':'module','name':'exposure'},{'op':'slider','description':'adjust the exposure correction','value':1.5},
              click('snapshots'),click('take snapshot','push button')]),
        step('compare','Change exposure to -1 EV and compare it with the saved snapshot.',
             'The saved bright edit and the current darker edit are visible together for comparison.',
             [{'op':'slider','description':'adjust the exposure correction','value':-1.},{'op':'snapshot-select'}],[],['snapshot']),
        step('restore','Restore the saved bright snapshot and save its history to XMP.',
             'The image returns to the saved bright state.',[{'op':'snapshot-restore'},{'op':'save-edit'}],
             [history('chart.png',1.5)],['compare'])]))
    key='collection-sort'
    out.append(episode(key,'collection-sort',[
        step('name','Import the three images and sort the library by filename in ascending order.',
             'The displayed order is chart.png, portrait.png, texture.png.',[{'op':'import'},{'op':'sort','name':'filename'}]),
        step('descending','Reverse the filename sort order.',
             'The displayed order is texture.png, portrait.png, chart.png.',[{'op':'sort-reverse'}],[],['name']),
        step('invert','Select portrait.png and invert the selection.',
             'Chart and texture are selected, while portrait is not.',[{'op':'select-image','file':'portrait.png'},{'op':'press','key':'Control+i'}],[],['descending'])],files=gallery))
    key='collection-rules'
    out.append(episode(key,'collection-rules',[
        step('filename','Import the three supplied images and make a collection of filenames containing "chart".',
             'Only chart.png is displayed.',
             [{'op':'import'},click('collections'),{'op':'collection-rule','query':'%chart%'}]),
        step('union','Add images whose filename contains "texture" to this collection, retaining the chart criterion.',
             'The collection shows chart.png and texture.png, with portrait.png excluded.',
             [{'op':'collection-rule','query':'%texture%','combine':'add more images'}],[],['filename']),
        step('exclude','Add an exclusion for filenames containing "texture" while keeping the preceding inclusion rules.',
             'The collection again displays only chart.png, with the texture exclusion visible.',
             [{'op':'collection-rule','query':'%texture%','combine':'exclude images'}],[],['union'])],files=gallery))
    key='view-assistance'
    out.append(episode(key,'view-assistance',[
        step('zoom','Import '+path(key,'texture-large.png')+', open it for editing and zoom the image to 400 percent.',
             'The image is magnified to 400 percent, showing a cropped detail view with navigation available.',
             [{'op':'import'},{'op':'darkroom'},{'op':'image-zoom','value':'400%'}]),
        step('fit','Fit the complete image into the editor view.',
             'The entire texture image is visible again and the view indicates a fit zoom.',
             [{'op':'image-zoom','value':'fit'}],[],['zoom']),
        step('focus','Enable focus peaking for the texture image.',
             'Focus peaking is active, with edge detail highlighted on the image.',
             [desc('toggle focus-peaking mode','toggle button')],[],['fit']),
        step('clipping','Disable focus peaking, set exposure to +3 EV, and enable clipping indication.',
             'Clipping indication is active and highlights clipped areas of the brightened image.',
             [desc('toggle focus-peaking mode','toggle button'),{'op':'module','name':'exposure'},
              {'op':'slider','description':'adjust the exposure correction','value':3.},desc('toggle clipping indication','toggle button')],[],['focus']),
        step('proof','Turn off clipping indication and enable soft proofing.',
             'The editing view indicates that soft proofing is active.',
             [desc('toggle clipping indication','toggle button'),desc('toggle softproofing','toggle button')],[],['clipping'])],files=('texture-large.png',)))
    key='view-raw-clipping'
    out.append(episode(key,'raw-viewing',[
        step('warning','Import '+path(key,'chart.dng')+', open it for editing, and enable the raw overexposure warning.',
             'The raw overexposure warning is active and marks saturated sensor areas on the chart.',
             [{'op':'import'},{'op':'darkroom'},desc('toggle indication of raw overexposure','toggle button')])],files=('chart.dng',)))
    return out

from specification import episode,step,go,click
from program import request


def press(key):return {'op':'press','key':key}


def progress(page):return request('/api/v1/books/${modebook.id}',fields=['readProgress.page'],want={'readProgress':{'page':page}})


def build():
    result=[];path='/book/${modebook.id}/read'
    for key,label,nextkey in [('r','Right to left','ArrowLeft'),('v','Vertical','ArrowDown'),('w','Webtoon',None)]:
        steps=[step('mode','Open Modes in Reader Lab, switch the reader to '+label+' and view the first page.','The reader displays the red first page in '+label+' mode.',[go(path),press(key),press('Home'),{'op':'wait','seconds':.5}],progress(1))]
        action=[press(nextkey)] if nextkey else [{'op':'wheel-reader','delta':1700}]
        steps.append(step('advance','Advance to the second page using the selected reading mode.','The blue second page is visible in the reader.',action+[{'op':'wait','seconds':.8}],progress(2),depends=['mode']))
        steps.append(step('last','Navigate to the final page of Modes.','The final teal page is visible at the end of the document.',[press('End'),{'op':'wait','seconds':.8},press('m')],({'kind':'extension','family':'reader-progress','action':'end','minimum':5} if key=='w' else progress(6)),depends=['advance']))
        steps.append(step('first','Return to the first page of Modes.','The red first page is displayed again.',[press('Home'),{'op':'wait','seconds':.8}],progress(1),depends=['last']))
        result.append(episode('gui-reader-'+key,'reader-modes',steps,library=False,setup=[{'id':'reader-pages','kind':'reader-pages'}]))
    result.append(episode('gui-reader-layout','reader-layout',[
        step('double','Read Modes in Reader Lab with a double-page layout, showing the purple fourth page and orange fifth page together.','Two consecutive page images are shown together.',[go(path),press('d'),go(path+'?page=4'),{'op':'wait','seconds':1}]),
        step('single','Switch back to single-page layout and display page 1.','Only the red first page is displayed.',[{'op':'reader-setting','current':'Double pages','value':'Single page'},press('Home'),{'op':'wait','seconds':.5}],progress(1),depends=['double']),
        step('width','Fit the first page to the reader width.','The page fills the available width and extends beyond the viewport vertically.',[{'op':'reader-setting','current':'Screen','value':'Fit width'}],depends=['single']),
        step('height','Fit the first page to the reader height.','The whole page fits vertically with horizontal margins.',[{'op':'reader-setting','current':'Fit width','value':'Fit height'}],depends=['width']),
        step('thumbnails','Use thumbnail navigation to open page 3.','The green wide third page is displayed and reading progress is page 3.',[press('t'),{'op':'reader-thumbnail','page':3},{'op':'wait','seconds':.5}],progress(3),depends=['height']),
    ],library=False,setup=[{'id':'reader-pages','kind':'reader-pages'}]))
    for kind in ['book','series']:
        result.append(episode('gui-poster-from-page-'+kind,'poster-selection',[
            step('poster','Use page 2 of Atlas chapter 1 as the '+kind+' poster.','The '+kind+' details show the selected page as its poster.',[go('/book/${b01.id}/read'),press('ArrowRight'),{'op':'wait','seconds':.5},press('m'),{'op':'reader-poster','kind':kind},go('/'+kind+'/${'+('b01' if kind=='book' else 's0')+'.id}')],{'kind':'extension','family':'page-poster','action':'check','path':'/api/v1/'+('books' if kind=='book' else 'series')+'/${'+('b01' if kind=='book' else 's0')+'.id}/thumbnail'}),
            step('reload','Refresh the details and inspect the selected poster.','The chosen page poster persists after refresh.',[{'op':'reload'}],depends=['poster'])
        ]))
    return result

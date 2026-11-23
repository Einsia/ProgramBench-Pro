"""Search scope and relative-time boundaries over explicit positive/negative controls."""
import time
from harness import Ref, Suite, project, resolve


def build():
    s=Suite('protocol-search-edges','search scope and time boundaries')
    corpus=[('root','Parent note','apple apple needle','parent',1768435200000),
            ('child','Child note','pear needle','child',1768348800000),
            ('other','Other note','apple pear needle','other',1768262400000),
            ('old','Old note','literal unknown:value needle','parent',1735689600000)]
    def prepare(c):
        c.call('POST','/folders',body={'title':'Parent'},save='book-parent')
        c.call('POST','/folders',body={'title':'Child','parent_id':Ref('book-parent')},save='book-child')
        c.call('POST','/folders',body={'title':'Other'},save='book-other')
        for key,title,body,book,date in corpus:
            c.call('POST','/notes',body={'title':title,'body':body,'parent_id':Ref('book-'+book),
                   'user_created_time':date,'user_updated_time':date},save=key)
        end=time.monotonic()+90
        while len(c.all('/search',fields='id',query={'query':'needle'}))!=len(corpus):
            if time.monotonic()>=end:raise AssertionError('search edge corpus did not settle')
            time.sleep(.5)
    s.setup('scope-corpus',prepare)
    queries=['notebook:Parent','notebook:Child','notebook:Other','notebook:Parent notebook:Other',
             '-notebook:Parent needle','notebook:Parent pear','notebook:Par*','id:{child}',
             'id:{child} pear','-id:{child} needle','created:day-1','-created:day-1',
             'created:day-2 -created:day','updated:day-1','updated:year-1','created:20260114 -created:20260115',
             'any:1 notebook:Other title:Child','any:0 apple pear','any:1 apple pear','apple -pear',
             'unknown:value','unknown:absent','/"unknown:value"','need*','title:Ch*','body:"apple pear"']
    for i,query in enumerate(queries):
        def search(c,query=query):
            rows=c.all('/search',fields='id,title',query={'query':resolve(query,c.values)})
            return {'matches':project(rows,['id','title'],c)}
        s.add('scope-'+str(i).zfill(2),'Search for '+query,search,
              {'matches':'The query distinguishes the explicit corpus members.'})
    return s

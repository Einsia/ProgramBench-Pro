"""Behavioral projections and requests through the public black-box API only."""
from __future__ import annotations
import base64
import dataclasses
import hashlib
import json
import math
import re
import urllib.parse
from evaluation.broker import BrokerError

CREDS = {'admin': 'admin'}
API = '/api/'

class MissingDependency(AssertionError):
    pass

class State(dict):
    def __missing__(self, key):
        raise MissingDependency('missing successful prerequisite ' + str(key))

@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object
    needs: tuple = ()
    requires: tuple = ()
    references: tuple = ()
    save: str | None = None

class Ref:
    def __init__(self, key, *path):
        self.key, self.path = key, path
    def get(self, ctx):
        value = ctx.state[self.key]
        try:
            for part in self.path:
                value = value[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise MissingDependency('prerequisite lacks ' + str(self.path)) from exc
        if self.path and self.path[-1] == 'created_object_id' and isinstance(value,str) and value.isdigit():return int(value)
        return value

def resolve(value, ctx):
    if isinstance(value, Ref):return value.get(ctx)
    if callable(value):return value(ctx)
    if isinstance(value, dict):return {k:resolve(v,ctx) for k,v in value.items()}
    if isinstance(value, (tuple,list)):return [resolve(v,ctx) for v in value]
    return value

def pathref(template, **values):
    return lambda c: template.format(**{k:urllib.parse.quote(str(resolve(v,c)),safe='') for k,v in values.items()})

def referenced_keys(value,seen=None):
    """References captured by request factories; does not execute product actions."""
    seen=set() if seen is None else seen
    if id(value) in seen:return set()
    seen.add(id(value))
    if isinstance(value,Ref):return {value.key}
    if isinstance(value,dict):items=value.values()
    elif isinstance(value,(tuple,list,set)):items=value
    elif callable(value):
        items=[*(getattr(value,'__defaults__',None) or ()),*(getattr(value,'__kwdefaults__',None) or {}).values()]
        for cell in getattr(value,'__closure__',None) or ():
            try:items.append(cell.cell_contents)
            except ValueError:pass
    else:return set()
    return set().union(*(referenced_keys(x,seen) for x in items)) if items else set()


def b64(data):
    return base64.b64encode(data.encode() if isinstance(data,str) else data).decode()

def unordered(values):
    return {'@unordered': list(values)}

def numeric(value):
    return isinstance(value,(int,float,str)) and not isinstance(value,bool) and re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',str(value)) is not None


def semantic(value,key='',path=''):
    """Field-aware comparison within one instance; identity values stay exact here."""
    if isinstance(value,dict):return {k:semantic(v,k,path) for k,v in value.items()}
    if isinstance(value,list):return [semantic(v,key,path) for v in value]
    leaf=key.rsplit('.',1)[-1]
    if leaf in Normalize.IDS or leaf in ('id','created_object_id'):
        if numeric(value):return str(int(float(value)))
        return value
    if leaf in Normalize.NUMBERS|Normalize.FLAGS or (leaf=='value' and '/settings/' in '/'+path):
        if numeric(value) or isinstance(value,bool):return float(value)
    return value.replace('\r\n','\n') if isinstance(value,str) else value


def semantic_equal(actual,expected,key='',path=''):
    try:AliasGraph().compare(semantic(actual,key,path),semantic(expected,key,path));return True
    except AssertionError:return False


def subset(got,want,path=''):
    assert isinstance(got,dict), 'expected object'
    for k,v in want.items():
        assert k in got, 'missing '+k
        assert semantic_equal(got[k],v,k,path),k+': different requested value'


class Normalize:
    # Only generated bookkeeping times are ignored. Explicit behavioral dates stay.
    CLOCK = {'row_created_timestamp','last_used','undone_timestamp'}
    IDS = {'product_id':'products','parent_product_id':'products','product_group_id':'product_groups',
           'location_id':'locations','default_consume_location_id':'locations',
           'shopping_location_id':'shopping_locations','chore_id':'chores','battery_id':'batteries',
           'child_recipe_id':'recipes','recipe_pos_id':'recipes_pos','product_id_effective':'products',
           'recipe_id':'recipes','includes_recipe_id':'recipes','task_id':'tasks','category_id':'task_categories',
           'user_id':'users','done_by_user_id':'users','assigned_to_user_id':'users',
           'next_execution_assigned_to_user_id':'users','rescheduled_next_execution_assigned_to_user_id':'users',
           'qu_id':'quantity_units','qu_id_stock':'quantity_units','qu_id_purchase':'quantity_units',
           'qu_id_consume':'quantity_units','qu_id_price':'quantity_units','from_qu_id':'quantity_units',
           'to_qu_id':'quantity_units','shopping_list_id':'shopping_lists','userentity_id':'userentities',
           'permission_id':'permission_hierarchy','section_id':'meal_plan_sections','stock_row_id':'stock','stock_id':'stock-batch',
           'transaction_id':'transaction','correlation_id':'correlation'}
    NUMBERS = {'amount','amount_opened','amount_aggregated','amount_opened_aggregated','amount_missing',
               'amount_possible','stock_amount','stock_amount_opened','product_amount','price','last_price',
               'average_price','last_price_per_stock_qu','factor','price_factor','calories','tare_weight',
               'min_stock_amount','quick_consume_amount','quick_open_amount','default_best_before_days',
               'default_best_before_days_after_open','default_best_before_days_after_freezing',
               'default_best_before_days_after_thawing','base_servings','desired_servings','servings',
               'recipe_servings','period_days','period_interval','charge_interval_days','sort_number',
               'days_since_last_charge','days_since_last_execution','due_type','default_stock_label_type',
               'default_purchase_price_type','last_stock_amount','stock_value','missing_amount',
               'costs','calories_per_serving','costs_per_serving','current_stock_amount','recipe_amount','missing_products_count','stock_amount_aggregated',
               'stock_amount_opened_aggregated','tracked_count','charge_cycles_count'}
    FLAGS = {'active','is_freezer','done','open','undone','spoiled','skipped','track_date_only','rollover',
             'consume_product_on_execution','enable_tare_weight_handling','not_check_stock_fulfillment_for_recipes',
             'cumulate_min_stock_amount_of_sub_products','hide_on_stock_overview','should_not_be_frozen',
             'treat_opened_as_out_of_stock','no_own_stock','move_on_open','auto_reprint_stock_label','disable_open',
             'only_check_single_unit_in_stock','not_check_stock_fulfillment','round_up','not_check_shoppinglist',
             'show_as_column_in_tables','input_required','show_in_sidebar_menu','is_partly_in_stock',
             'is_fully_in_stock','need_fulfilled','need_fulfilled_with_shopping_list','is_aggregated_amount'}
    def __init__(self):self.ids={};self.next={}
    def identity(self,kind,value):
        if value in (None,'',0,'0',-1,'-1'):return None if value is None else (int(value) if value not in ('',) else '')
        if numeric(value):value=str(int(float(value)))
        key=(kind,str(value))
        if key not in self.ids:
            self.next[kind]=self.next.get(kind,0)+1;self.ids[key]='@'+kind+':'+str(self.next[kind])
        return self.ids[key]
    def clean(self,value,key='',hint='object'):
        if isinstance(value,dict):
            return {k:self.clean(v,k, 'users' if k in ('last_done_by','next_execution_assigned_user','assigned_to_user') else (hint if k not in ('product','chore','battery','recipe','user') else k+'s'))
                    for k,v in sorted(value.items()) if k not in self.CLOCK}
        if isinstance(value,list):
            values=[self.clean(v,'',hint) for v in value]
            return unordered(values) if key in {'due_products','expired_products','overdue_products','missing_products'} else values
        if key in ('id','created_object_id'):return self.identity(hint,value)
        if key in self.IDS:return self.identity(self.IDS[key],value)
        if key=='value' and hint=='numeric-setting' and (numeric(value) or isinstance(value,bool)):return float(value)
        if key in self.NUMBERS|self.FLAGS and value not in (None,''):
            try:return float(value)
            except (TypeError,ValueError):pass
        if key in ('used_date','opened_date') and isinstance(value,str):return value[:10]
        if isinstance(value,str):return value.replace('\r\n','\n')
        return value

class AliasGraph:
    '''Compare opaque identities by a persistent typed bijection, not counters. Response objects may carry fields the
    reference does not have; every reference field must be present and equal. Data-keyed maps and empty objects stay
    exact: an extra entry there is different data.'''

    TOKEN = re.compile(r'@[A-Za-z][A-Za-z0-9_.%+-]*:[0-9]+')
    FIELD = re.compile(r'^[a-z_][a-z0-9_]*$')
    MAPS = {'headers', 'userfields'}

    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def compare(self, actual, expected):
        forward, reverse = dict(self.forward), dict(self.reverse)

        def walk(a, e, path, parent=None):
            if type(a) in (int, float) and type(e) in (int, float):
                assert math.isclose(a, e, rel_tol=1e-8, abs_tol=1e-8), path + ': different numeric value'
                return
            assert type(a) is type(e), path + ': different value type'
            if isinstance(e, dict):
                if e.keys() == {'@unordered'}:
                    assert a.keys() == e.keys() and isinstance(a['@unordered'], list), path + ': different collection'
                    av, ev = a['@unordered'], e['@unordered']
                    assert len(av) == len(ev), path + ': different collection length'
                    todo = sorted(ev, key=lambda x: -sum(m[0] in forward for m in self.TOKEN.finditer(json.dumps(x))))

                    def match(index, remaining):
                        if index == len(todo):
                            return True
                        for pos in remaining:
                            saved = (dict(forward), dict(reverse))
                            try:
                                walk(av[pos], todo[index], path + '{member}')
                                if match(index + 1, [x for x in remaining if x != pos]):
                                    return True
                            except AssertionError:
                                pass
                            forward.clear()
                            forward.update(saved[0])
                            reverse.clear()
                            reverse.update(saved[1])
                        return False
                    assert match(0, list(range(len(av)))), path + ': unordered membership or identity relationships differ'
                    return
                if not e or parent in self.MAPS or not all(self.FIELD.match(k) for k in e):
                    assert a.keys() == e.keys(), path + ': different fields'
                else:
                    missing = sorted(set(e) - set(a))
                    assert not missing, path + ': missing fields ' + ', '.join(missing[:5])
                for k in e:
                    walk(a[k], e[k], path + '.' + k, k)
            elif isinstance(e, list):
                assert len(a) == len(e), path + ': different collection length'
                for i, (x, y) in enumerate(zip(a, e)):
                    walk(x, y, path + '[' + str(i) + ']', parent)
            elif isinstance(e, str):
                at, et = list(self.TOKEN.finditer(a)), list(self.TOKEN.finditer(e))
                assert self.TOKEN.split(a) == self.TOKEN.split(e) and len(at) == len(et), path + ': different text'
                for am, em in zip(at, et):
                    got, want = am[0], em[0]
                    assert got.rsplit(':', 1)[0] == want.rsplit(':', 1)[0], path + ': different identity namespace'
                    assert forward.get(want, got) == got and reverse.get(got, want) == want, path + ': inconsistent identity relationship'
                    forward[want] = got
                    reverse[got] = want
            else:
                assert a == e, path + ': different value'

        walk(actual, expected, '$')
        self.forward, self.reverse = forward, reverse


class Response:
    def __init__(self,answer):
        self.status_code=answer['status'];self.headers={k.lower():v for k,v in answer.get('headers',{}).items()}
        self.content=base64.b64decode(answer.get('body_base64') or '')
    @property
    def text(self):return self.content.decode('utf-8','replace')
    def json(self):return json.loads(self.content)

class Context:
    def __init__(self,broker,out=None):
        self.broker=broker;self.out=out;self.state=State();self.norm=Normalize();self.aliases=AliasGraph();self.creds=dict(CREDS)
    def close(self):pass
    def request(self,method,path,actor='admin',body=None,params=None,headers=None,raw=None,multipart=None,content_type=None,fresh_auth=False):
        path=path if path.startswith('/') else API+path
        if params:path+=('&' if '?' in path else '?')+urllib.parse.urlencode(params,doseq=True)
        rpc={'op':'api','method':method,'path':path,'binary':True}
        if isinstance(actor,(tuple,list)):rpc['auth']=list(actor)
        elif actor and actor.startswith('token:'):rpc['token']=self.state[actor[6:]]
        elif actor:rpc['auth']=[actor,self.creds[actor]]
        if fresh_auth:rpc['fresh_auth']=True
        if headers:rpc['headers']=headers
        if content_type:rpc['content_type']=content_type
        if raw is not None:rpc['body_base64']=b64(raw)
        elif multipart is not None:rpc['multipart']=multipart
        elif body is not None:rpc['json']=body
        try:answer=self.broker.call(rpc)
        except BrokerError as exc:raise AssertionError('candidate request failed: '+exc.detail[:300]) from None
        assert not answer.get('truncated'),'response exceeds black-box limit'
        return Response(answer),answer['body']
    def observe(self,r,p,hint='object',fields=None,ordered=False):
        if r.status_code>=400:return {'status':r.status_code}
        if hint=='bytes':return {'status':r.status_code,'size':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest()}
        if fields is not None:
            def project(x):
                assert isinstance(x,dict),'expected an object to project'
                assert set(fields)<=x.keys(),'response missing fields '+str(set(fields)-x.keys())
                return {k:x[k] for k in fields}
            p=[project(x) for x in p] if isinstance(p,list) else project(p)
        p=self.norm.clean(p,hint=hint)
        if isinstance(p,list) and not ordered:p=unordered(p)
        return {'status':r.status_code,'body':p}

class Suite:
    def __init__(self):self.cases=[];self.ids=set();self.needs=[]
    def add(self,family,scenario,step,action,channel='api',description='',needs=None,requires=()):
        if family.endswith('fixture'):channel='setup'
        cid=channel+'.'+family+'.'+scenario+'.'+step
        assert cid not in self.ids,'duplicate '+cid
        self.ids.add(cid);self.cases.append(Case(cid,family,scenario,channel,description or step,action,
                                               tuple(self.needs if needs is None else needs),tuple(requires),
                                               tuple(sorted(referenced_keys(action)))))
        return cid
    def api(self,family,scenario,step,method,path,actor='admin',body=None,params=None,save=None,status=200,
            want=None,check=None,hint='object',headers=None,raw=None,multipart=None,content_type=None,
            before=None,fields=None,ordered=False,needs=None,requires=(),after=None,fresh_auth=False):
        def action(c,relaxed=False):
            if before:before(c)
            r,p=c.request(method,resolve(path,c),resolve(actor,c),resolve(body,c),resolve(params,c),
                          resolve(headers,c),resolve(raw,c),resolve(multipart,c),content_type,fresh_auth)
            if relaxed:
                assert 200<=r.status_code<300,'fixture refused: '+str(r.status_code)+' '+str(p)[:250]
            elif status is not None:
                assert r.status_code in ([status] if isinstance(status,int) else status), 'unexpected HTTP '+str(r.status_code)+' '+str(p)[:250]
            if save and 200<=r.status_code<300:c.state[save]=p
            if relaxed:return None
            if want is not None:subset(p,resolve(want,c),resolve(path,c))
            if check:check(c,r,p)
            observation=c.observe(r,p,'numeric-setting' if '/settings/' in '/'+resolve(path,c) else hint,fields,ordered)
            if isinstance(status,(tuple,list)):observation['status']=min(status)
            if after:observation['state']=after(c)
            return observation
        cid=self.add(family,scenario,step,action,description=method+' '+(path if isinstance(path,str) else 'related resource')+'; '+step,
                        needs=needs,requires=requires)
        self.cases[-1].save=save
        return cid

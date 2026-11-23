"""Legacy protocol inventories may declare GUI boundaries, never execute them.

Candidate GUI evaluation uses the reviewed specification and generic browser.
The pinned standard's deterministic recipes live separately in this package.
"""
from evaluation.contract import InfrastructureError


def add(suite,family,scenario,step,fn):
    def unavailable(context):
        raise InfrastructureError('reference-only GUI registration cannot operate a candidate')
    suite.add(family,scenario,step,unavailable,channel='ui')


def view(suite,family,scenario,step,path,*args,**kwargs):
    add(suite,family,scenario,step,None)

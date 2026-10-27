#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only model of rectangular nonuniform threadgroup decomposition.

This is a geometry planner, not an encoder or a Metal implementation. In
particular, its origins and group bases are NOT qualified NVIDIA packet fields.
"""
import argparse,itertools,json,math
MAX_U32=2**32-1

def _vector(value,name):
    if not isinstance(value,(list,tuple)) or len(value)!=3 or any(type(x)!=int or x<1 or x>MAX_U32 for x in value):raise ValueError(name+' must contain three positive uint32 values')
    return tuple(value)

def plan(grid,local,max_invocations):
    grid=_vector(grid,'grid');local=_vector(local,'local')
    if type(max_invocations)!=int or not 1<=max_invocations<=MAX_U32:raise ValueError('A positive uint32 invocation bound is required')
    if local[0]>1024 or local[1]>1024 or local[2]>64 or math.prod(local)>1024:raise ValueError('Local geometry exceeds the documented project profile')
    if math.prod(grid)>max_invocations:raise ValueError('Grid exceeds the caller-provided invocation bound')
    logical_groups=tuple((g+l-1)//l for g,l in zip(grid,local))
    if logical_groups[0]>0x7fffffff or logical_groups[1]>65535 or logical_groups[2]>65535:raise ValueError('Logical group geometry exceeds the documented project profile')
    axes=[]
    for g,l in zip(grid,local):
        q,r=divmod(g,l);axis=[]
        if q:axis.append({'group_base':0,'group_count':q,'thread_origin':0,'actual_local':l})
        if r:axis.append({'group_base':q,'group_count':1,'thread_origin':q*l,'actual_local':r})
        axes.append(axis)
    segments=[]
    for combo in itertools.product(*axes):
        segments.append({'group_base':[a['group_base'] for a in combo],
                         'physical_group_count':[a['group_count'] for a in combo],
                         'thread_origin':[a['thread_origin'] for a in combo],
                         'actual_local':[a['actual_local'] for a in combo],
                         'logical_grid':list(grid),'nominal_local':list(local),'logical_group_count':list(logical_groups)})
    assert 1<=len(segments)<=8
    return {'schema':1,'grid':list(grid),'nominal_local':list(local),'logical_group_count':list(logical_groups),
            'invocations':math.prod(grid),'segments':segments,'encoder_implemented':False,'safe_to_dispatch':False,
            'scope':'CPU geometry only; NVIDIA origin, group-ID, builtins, memory and cross-dispatch behavior require separate qualification'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--grid',type=int,nargs=3,required=True);p.add_argument('--local',type=int,nargs=3,required=True);p.add_argument('--max-invocations',type=int,required=True);a=p.parse_args();print(json.dumps(plan(a.grid,a.local,a.max_invocations),indent=2,sort_keys=True))

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Classify a separately captured class-list byte array without dereferencing pointers."""
import argparse,hashlib,json,struct
from pathlib import Path

# This limit is an analysis bound, not an NVIDIA or hardware limit.
MAX_CLASSES=65536
PRIORITY={'BSP':['0x95b1','0x90b1'],'VP':['0x95b2','0x90b2'],'PPP':['0x90b3']}
def classify(data,count):
 if type(count) is not int or not 0<=count<=MAX_CLASSES:raise ValueError('count outside offline bound')
 if len(data)!=count*4:raise ValueError('capture must contain exactly count little-endian words')
 values=struct.unpack('<'+str(count)+'I',data) if count else ()
 selected={name:next((v for v in choices if int(v,16) in values),None) for name,choices in PRIORITY.items()}
 return {'status':'OFFLINE_CLASSLIST_CLASSIFICATION','count':count,'capture_SHA256':hashlib.sha256(data).hexdigest(),'candidate_selection':selected,'GPU_or_driver_query_performed':False,'actual_classlist_attested':False,'scope':'Classification assumes the input is an authentic complete matching-device class list; provenance and runtime activity are not established.'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--words',type=Path,required=True);p.add_argument('--count',type=int,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.words.stat().st_size>MAX_CLASSES*4:raise ValueError('capture exceeds offline bound')
 result=classify(a.words.read_bytes(),a.count)
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()

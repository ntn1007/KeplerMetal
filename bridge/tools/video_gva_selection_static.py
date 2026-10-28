#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pin and inspect a bounded AppleGVA selection branch without executing it."""
import argparse, hashlib, json, re, struct
from pathlib import Path
from inspect_video_cache import Cache
from analyze_video_dependency import constant_string
UUID='ca5414f369373c059ea2d82b35afd4f0'
INNER='4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564'
BOARD='d5a78812a5224dc620e0b9fddd2c2c4422a2399e18f994d67a10885f0b88a15b'
META=('89b06b0d824d424fe52e4f6a3fed085bdb514c51a5a81cc41df6d1304cf50afe','f561d00c34dcf3368cd1497c7241b7b9ec455a76af649a1808e12fb633b4e41f')
MAPS=('f4e9911d1e64dd0a6590c17b41563ff3ab9f7d8540ed966a4729d1e0ddfc3c45','0f2b6abc8fb7e26af4581a08c4be347eba5fd6279bb2c44df66de69d7354f2f9')
def need(x,msg):
 if not x: raise ValueError(msg)
def digest(b): return hashlib.sha256(b).hexdigest()
def relative(b,start,site,opcode):
 off=site-start;need(off>=0 and off+len(opcode)+4<=len(b),'instruction outside capture');need(b[off:off+len(opcode)]==opcode,'instruction opcode differs');return site+len(opcode)+4+struct.unpack_from('<i',b,off+len(opcode))[0]
def cstring(c,addr):
 raw=c.read(addr,64);end=raw.find(b'\0');need(0<end<64,'unterminated string');return raw[:end].decode('ascii')
def capture(p,expected_meta,expected_region,cache):
 meta=p/'metadata.json';need(digest(meta.read_bytes())==expected_meta,'metadata changed');m=json.loads(meta.read_text());r=m['region'];data=(p/'function-region.private.bin').read_bytes();need(m['image']['UUID']==UUID and r['SHA256']==expected_region and digest(data)==expected_region and len(data)==r['bytes'] and r['boundary_source']=='LC_FUNCTION_STARTS','capture identity differs');need(digest(cache.read(r['start_VM'],r['bytes']))==expected_region,'current cache region differs');return m,data
def mapped(p,expected,region,entries):
 need(digest(p.read_bytes())==expected,'map changed');m=json.loads(p.read_text());need(m['status']=='STATIC_ONLY' and m['source_region_SHA256']==region and not m['runtime_target_proved'],'map identity differs');rows={r['caller_offset']:r for r in m['rows']}
 for off,name in entries:need(name in rows[off]['exact_defined_symbols'] and not rows[off]['runtime_target_proved'],'stub mapping differs')
def inspect(inner,board,inner_map,board_map,cache,host_board):
 need(re.fullmatch(r'Mac-[0-9A-F]{8,32}',host_board) is not None,'board identifier malformed')
 im,data=capture(inner,META[0],INNER,cache);bm,board_data=capture(board,META[1],BOARD,cache);base=im['image_base_VM'];need(base==bm['image_base_VM'],'image bases differ');start=im['region']['target_image_offset'];need(start==146348 and bm['region']['target_image_offset']==151999,'region offsets differ')
 mapped(inner_map,MAPS[0],INNER,[(146933,'__platform_strcmp'),(146956,'__platform_strcmp'),(146979,'__platform_strcmp')]);mapped(board_map,MAPS[1],BOARD,[(152041,'_IORegistryGetRootEntry'),(152080,'_IORegistryEntrySearchCFProperty'),(152096,'_CFDataGetBytePtr'),(152107,'_CFDataGetLength')])
 board_start=151999;plane=relative(board_data,board_start,152056,b'\x48\x8d\x35');key=relative(board_data,board_start,152063,b'\x48\x8d\x15');need(cstring(cache,base+plane)=='IOService' and constant_string(cache,base+key)=='board-id','registry query constants differ');need(board_data[152072-board_start:152080-board_start]==b'\x31\xc9\x41\xb8\x01\x00\x00\x00','registry query arguments differ')
 rows=[]
 for lea,call,test in ((146923,146933,146938),(146946,146956,146961),(146969,146979,146984)):
  target=relative(data,start,lea,b'\x48\x8d\x35');call_target=relative(data,start,call,b'\xe8');need(call_target==811572,'comparison call target differs');off=test-start;need(data[off:off+2]==b'\x85\xc0','comparison test differs');branch=relative(data,start,test+2,b'\x0f\x84');label=cstring(cache,base+target);need(re.fullmatch(r'Mac-[0-9A-F]{16}',label) is not None,'comparison string differs');rows.append({'string':label,'compare_call_offset':call,'equal_branch_offset':branch})
 need(len({r['string'] for r in rows})==3,'duplicate board cases');off=146992-start;need(data[off:off+3]==b'\x4d\x85\xf6','fallback candidate check differs');fallback=relative(data,start,146995,b'\x0f\x84');append=relative(data,start,147011,b'\xe8');need(fallback==147429 and append==151776,'fallback branch targets differ')
 return {'status':'STATIC_ONLY','image_UUID':UUID,'inner_region_SHA256':INNER,'board_reader_region_SHA256':BOARD,'candidate_comparisons':rows,'input_board':host_board,'input_board_matches_special_case':any(x['string']==host_board for x in rows),'conditional_fallback_candidate_test_offset':146992,'candidate_absent_branch_offset':fallback,'candidate_present_append_call_offset':147011,'append_target_offset':append,'board_query_call_offset':152080,'board_query_plane':'IOService','board_query_key':'board-id','board_query_options':1,'board_query_static_target':'IORegistryEntrySearchCFProperty','runtime_board_value_observed':False,'selection_branch_observed':False,'hardware_decode_proved':False,'vendor_program_executed':False,'system_modified':False}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('cache','inner','board','inner-map','board-map','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--host-board',required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');result=inspect(a.inner,a.board,a.inner_map,a.board_map,Cache(a.cache.resolve()),a.host_board)
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()

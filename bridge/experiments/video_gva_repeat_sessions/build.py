#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a three-request own-process variant from a pinned laboratory host."""
import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_SHA = '907a641110d0e0c1ae3e677722aa84f9fe34011ef40622b585cc703e1c5cc2ef'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, message):
    if not ok: raise ValueError(message)


def command(label, argv, out):
    argv = list(map(str, argv)); p = subprocess.run(argv, capture_output=True, timeout=90)
    (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode == 0, label+' failed; inspect retained stderr')
    return {'label':label, 'argv':argv, 'status':p.returncode}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for x in ('lab','base','witness-build','out'): p.add_argument('--'+x, required=True, type=Path)
    a = p.parse_args(); lab, base, witness, out = (getattr(a,n).resolve() for n in ('lab','base','witness_build','out'))
    for x in (base,witness,out): x.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh output required')
    base_rec = json.loads((base/'inputs.json').read_text()); w = json.loads((witness/'build.json').read_text())
    need(w['status']=='PREPARED_ONLY' and w['base_inputs_sha256']==sha(base/'inputs.json'), 'witness base differs')
    for name,h in base_rec['frozen'].items(): need(sha(base/name)==h, 'base changed: '+name)
    for name,h in w['frozen'].items(): need(sha(witness/name)==h, 'witness changed: '+name)
    factory=Path(base_rec['base_build']); need(sha(factory/'inputs.json')==base_rec['base_inputs_SHA256'], 'factory profile differs')
    f=json.loads((factory/'inputs.json').read_text())
    for name,h in f['reused_objects_and_libraries_SHA256'].items(): need(sha(name)==h,'dependency differs')
    for name,h in f['new_objects_SHA256'].items(): need(sha(factory/name)==h,'factory object differs')
    need(sha(factory/'libVideoFactoryResolver.dylib')==f['resolver_library_SHA256'], 'factory library differs')
    source=ROOT/'tools/video_registry_client.mm'; need(sha(source)==SOURCE_SHA, 'registry source differs')
    original=source.read_text()
    old='''    NSDictionary *decoded=inspect?nil:KPRegistryPublicDecode([[assets stringByAppendingPathComponent:@"fixtures"]
        stringByAppendingPathComponent:codec],mode,out);if(!inspect&&!decoded)return 6;
    NSDictionary *trace=KPRegistrySnapshot();'''
    new='''    NSString *fixture=[[assets stringByAppendingPathComponent:@"fixtures"] stringByAppendingPathComponent:codec];
    fprintf(stderr,"KP_REPEAT_BEGIN request=1\\n"); fflush(stderr);
    NSDictionary *decoded=inspect?nil:KPRegistryPublicDecode(fixture,mode,out);
    fprintf(stderr,"KP_REPEAT_END request=1\\n"); fflush(stderr);
    if(!inspect&&!decoded)return 6;
    NSMutableArray *additional=[NSMutableArray array];
    for(unsigned n=2;!inspect && n<=3;n++) {
        NSString *dir=[out stringByAppendingPathComponent:[NSString stringWithFormat:@"repeat-%u",n]];
        if(![[NSFileManager defaultManager]createDirectoryAtPath:dir withIntermediateDirectories:NO attributes:nil error:nil])return 9;
        fprintf(stderr,"KP_REPEAT_BEGIN request=%u\\n",n); fflush(stderr);
        NSDictionary *extra=KPRegistryPublicDecode(fixture,mode,dir);
        fprintf(stderr,"KP_REPEAT_END request=%u\\n",n); fflush(stderr);
        if(!extra){[additional addObject:[NSNull null]];break;}[additional addObject:extra];
    }
    NSDictionary *trace=KPRegistrySnapshot();'''
    need(original.count(old)==1,'original decode block differs')
    modified=original.replace(old,new).replace('    record[@"library_kind"]=kind;', '    record[@"additional_public_decodes"]=additional;\n    record[@"library_kind"]=kind;')
    # `additional` is declared only in the real-client branch; compilation is intentionally non-calibration.
    need(modified.count('record[@"additional_public_decodes"]')==1, 'record insertion differs')
    commands=json.loads((factory/'commands.json').read_text()); link=next(x['argv'] for x in commands if x['label']=='application')
    target=next(k for k in f['reused_objects_and_libraries_SHA256'] if Path(k).name=='qualified-host-renamed.o')
    olddep=next(k for k in f['reused_objects_and_libraries_SHA256'] if Path(k).name=='libVideoDependency-both.dylib')
    need(link.count(target)==1 and link.count(olddep)==1 and link[-2:]==['-o',str(factory/'application')], 'link plan differs')
    out.mkdir(); (out/'registry-repeated.mm').write_text(modified); shutil.copyfile(ROOT/'tools/video_registry_observer.h',out/'video_registry_observer.h')
    need(sha(out/'video_registry_observer.h')==f['source_hashes']['video_registry_observer.h'],'header differs')
    metadata=lab/'results/video-registry-metadata-build-20261016'
    metadata_info=json.loads((metadata/'inputs.json').read_text())
    names=('video_registry_metadata_decoder.mm','video_registry_decoder.mm','video_va_vt_client.mm',
           'video_engine_probe.mm','video_registry_observer.h','video_registry_metadata.h')
    for name in names:
        need(sha(metadata/name)==metadata_info['source_hashes'][name], 'decoder source differs: '+name)
        shutil.copyfile(metadata/name,out/name)
    mp=out/'video_registry_metadata_decoder.mm'
    ms=mp.read_text()
    before='    if(!KPRegistryMetadataBegin((uintptr_t)KPRegistryOriginal(1)+27,(uintptr_t)KPRegistryOriginal(3)+27))return nil;'
    after='''    bool metadataBegin=KPRegistryMetadataBegin((uintptr_t)KPRegistryOriginal(1)+27,(uintptr_t)KPRegistryOriginal(3)+27);
    fprintf(stderr,"KP_METADATA_BEGIN success=%d\\n",metadataBegin?1:0);fflush(stderr);
    if(!metadataBegin)return nil;'''
    need(ms.count(before)==1,'metadata call differs')
    mp.write_text(ms.replace(before,after))
    records=[];obj=out/'registry-repeated.o';host=out/'application'
    h264=out/'H264-diagnostic.o'
    records.append(command('decoder-diagnostic',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17',
      '-fno-objc-arc','-fno-omit-frame-pointer','-Wno-deprecated-declarations','-Wno-frame-address',
      '-DKPREG_MPEG2=0','-c',mp,'-o',h264],out))
    records.append(command('compile',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-fblocks','-Wno-deprecated-declarations','-DKPREG_CALIBRATION=0','-Dmain=KPRegistryQualifiedMain','-c',out/'registry-repeated.mm','-o',obj],out))
    h264old=next(k for k in f['reused_objects_and_libraries_SHA256'] if Path(k).name=='H264.o')
    need(link.count(h264old)==1, 'decoder object differs')
    link = [str(obj) if v==target else str(base/'libDependency.dylib') if v==olddep else str(h264) if v==h264old else v for v in link[:-2]]
    records.append(command('link',link+['-o',host],out))
    shutil.copyfile(witness/'entitlements.plist',out/'entitlements.plist')
    records.append(command('sign',['codesign','--force','--sign','-','--entitlements',out/'entitlements.plist',host],out))
    records.append(command('verify',['codesign','--verify','--strict',host],out))
    for name in ('marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py','marker.dylib'):
        shutil.copyfile(witness/name,out/name)
    frozen={name:sha(out/name) for name in w['frozen'] if (out/name).is_file()}
    need(set(frozen)==set(w['frozen']), 'frozen witness files incomplete')
    build={**w,'frozen':frozen,'repeat_variant':True,'baseline_witness_build_sha256':sha(witness/'build.json'),
           'base_source_sha256':SOURCE_SHA,'variant_source_sha256':sha(out/'registry-repeated.mm'),
           'variant_object_sha256':sha(obj),'diagnostic_decoder_sha256':sha(h264),'diagnostic_decoder_source_sha256':sha(mp),'factory_inputs_sha256':sha(factory/'inputs.json'),
           'builder_sha256':sha(Path(__file__)),'GPU_execution':False,'vendor_execution':False}
    (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
    (out/'build.json').write_text(json.dumps(build,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED_THREE_REQUESTS','host_sha256':sha(host),'GPU_execution':False}))


if __name__=='__main__': main()

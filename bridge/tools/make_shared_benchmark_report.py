#!/usr/bin/env python3
"""Recompute GPU counters/raw captures and summarize paired wall-time trials."""
from pathlib import Path
import argparse,hashlib,json,math,statistics,struct
root=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/shared-benchmark-final');folder=parser.parse_args().input.resolve();folder.relative_to(root/'results');m=json.loads((folder/'manifest.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not m['quick'] and m['driver_unchanged'] and len(m['cases'])==12
for a in m['source_snapshot']+m['shaders']:assert sha(root/a['path'])==a['sha256']
assert sha(folder/'carrier.metallib')==m['carrier_sha256'] and sha(folder/'libKeplerProgramImport.dylib')==m['library_sha256']
MASK=0xffffffff;records=[];checked_words=0;finished_groups=0
def checksum(kind,seed,local,groups):
    return sum((((7*0x9e3779b9)&MASK)^(seed^(g*0x100001))) if kind=='capacity' else (seed+g*0x100001+local)&MASK for g in range(groups))&MASK
for c in m['cases']:
    d=json.loads((root/c['result']).read_text());kind=c['kind'];groups=c['groups'];local=c['local'];batch=c['batch']
    assert d['kind']==kind and d['groups']==groups and d['local']==local and d['batch']==batch
    assert d['device']=='NVIDIA GeForce GTX 880M' and d['mismatches']==d['guard_mismatches']==0 and d['import']['contract_verified']
    assert d['warmups_per_path']==3 and d['trials_per_path']==9 and len(d['samples'])==18
    assert d['static_shared_bytes_metal']==d['static_shared_bytes_nak'] and d['actual_occupancy_measured'] is False
    paths={};pairs={}
    for path in ('metal','nak'):
        samples=sorted((s for s in d['samples'] if s['path']==path),key=lambda s:s['round']);assert [s['round'] for s in samples]==list(range(9))
        for s in samples:
            seed=(0xfffffc00+(s['round']+3)*0x9e3779b9)&MASK;assert seed==s['seed']
            assert s['GPU_completed_groups']==groups*batch and s['GPU_result_checksum']==(checksum(kind,seed,local,groups)*batch)&MASK
            for metric in ('compute_submit_wait_wall_ms','readback_wall_ms','compute_plus_readback_wall_ms','compute_host_cpu_ms','readback_host_cpu_ms'):assert math.isfinite(s[metric]) and s[metric]>=0
            assert abs(s['compute_plus_readback_wall_ms']-s['compute_submit_wait_wall_ms']-s['readback_wall_ms'])<1e-9
            finished_groups+=groups*batch;pairs[(path,s['round'])]=s['compute_plus_readback_wall_ms']
        timing={}
        for metric in ('compute_submit_wait_wall_ms','readback_wall_ms','compute_plus_readback_wall_ms','compute_host_cpu_ms','readback_host_cpu_ms','reported_GPU_command_ms'):
            values=[s[metric] for s in samples];q=statistics.quantiles(values,n=4,method='inclusive');timing[metric]={'median':statistics.median(values),'minimum':min(values),'maximum':max(values),'IQR':q[2]-q[0]}
        timing['effective_ms_per_dispatch_with_readback']=timing['compute_plus_readback_wall_ms']['median']/batch
        timing['effective_completed_groups_per_second']=groups*batch*1000/timing['compute_plus_readback_wall_ms']['median']
        prefix=(root/c['result']).with_suffix('');dataPath=Path(str(prefix)+'-'+path+'.output.bin');progressPath=Path(str(prefix)+'-'+path+'.progress.bin');raw=dataPath.read_bytes();pr=progressPath.read_bytes()
        seed=(0xfffffc00+12*0x9e3779b9)&MASK;words=d['shared_bytes']//4;count=groups*words*2 if kind=='capacity' else groups*(local+1)
        assert len(raw)==count*4+128 and len(pr)==136 and raw[:64]==raw[-64:]==pr[:64]==pr[-64:]==bytes([0xa5])*64
        values=list(struct.unpack('<'+'I'*count,raw[64:-64]))
        for g in range(groups):
            if kind=='capacity':
                for phase in range(2):
                    for i in range(words):
                        index=(i*(7 if phase else 5)+(13 if phase else 7))%words;expected=((index*0x9e3779b9)&MASK)^(seed^(g*0x100001))^(0x6a09e667 if phase else 0)
                        assert values[g*words*2+phase*words+i]==expected
            else:
                init=(seed+g*0x100001)&MASK;assert sorted(values[g*(local+1):g*(local+1)+local])==sorted((init+i)&MASK for i in range(local));assert values[g*(local+1)+local]==(init+local)&MASK
        assert struct.unpack_from('<2I',pr,64)==(groups*batch,(checksum(kind,seed,local,groups)*batch)&MASK)
        checked_words+=count;timing['final_capture_sha256']={'output':sha(dataPath),'progress':sha(progressPath)};paths[path]=timing
    assert all(next(s for s in d['samples'] if s['path']=='metal' and s['round']==r)['order']!=next(s for s in d['samples']if s['path']=='nak' and s['round']==r)['order'] for r in range(9))
    ratio=statistics.median(pairs[('nak',r)]/pairs[('metal',r)]for r in range(9))
    records.append({**c,'paths':paths,'paired_median_NAK_over_Metal_wall_ratio':ratio,'native_registers':next(p['compiler_metadata_registers']for p in m['native_compiler_profiles']if p['kind']==kind and p['role']=='reference'),'NAK_registers':next(s['info']['registers']for s in m['shaders']if s['kind']==kind)})
summary={'collected_at':m['collected_at'],'cases':12,'measured_samples':216,'GPU_completed_groups_verified_in_measured_samples':finished_groups,'final_capture_uint32_words_verified':checked_words,'independent_counter_and_raw_oracles_passed':True,'records':records,'driver_unchanged':True,'driver_sha256':m['driver_sha256'],'GPU_timestamps_qualified':False,'actual_occupancy_measured':False,'register_count_scope':'Declared constructor counts; NAK fixtures request at least24 per qualified import profile, not a measurement of registers actually used or achieved occupancy','pipeline_setup_excluded_from_timing':True,'limits':'Equivalent hand-built NIR and native MSL kernels with matched GPU count/checksum instrumentation; per-dispatch wall includes readback amortized by batch. These measurements do not establish general compiler/application or Metal-family performance.'}
(root/'results/shared-benchmark-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['KEPLERMETAL — comparaison Metal natif / NAK, kernels instrumentés','',
 'Deux calculs équivalents : échanges en mémoire partagée48Kio et ADD partagé',
 'uint32 sous contention128threads. Le chemin NAK part d’un NIR construit',
 'explicitement ; le chemin natif compile le MSL équivalent. Ce benchmark',
 'ne mesure pas une traduction AIR automatique de programmes arbitraires.',
 'Chaque groupe met à jour deux compteurs GPU : terminaison et checksum d’un',
 'résultat global relu après barrière shared/device. Les deux chemins possèdent',
 'la même instrumentation ; elle fait partie du coût mesuré.',
 'Groupes8/64, répétitions1/16/64 par commande ; local128.3échauffements puis',
 '9essais par chemin, alternance de l’ordre, mêmes graines/données/ressources.',
 'Un dispatch répété est compté sur GPU ; tous les résultats passent la',
 'validation en direct, puis une capture supplémentaire hors mesure est',
 'relue par Python. Les temps de compilation/création des pipelines et la',
 'validation CPU sont exclus. Ressources Private et lecture Managed synchronisée.', '',
 'Mesure principale : durée murale compute-submit-wait + readback, divisée par',
 'le nombre de dispatches. Elle comprend le coût de l’API/pilote et amortit la',
 'copie finale du lot ; ce n’est pas une latence de kernel GPU isolée.',
 'Compute, readback, reset et CPU consommé sont enregistrés séparément.',
 'Les timestamps GPU du pilote sont conservés sans être qualifiés. Aucune',
 'occupation GPU réelle ni fréquence/thermique contrôlée n’est mesurée.',
 'Les GPR sont des comptes statiques du programme, pas une mesure d’occupation.', '',
 'KERNEL     GROUPES BATCH  METAL ms/dispatch NAK ms/dispatch  RATIO NAK/METAL']
for r in records:lines.append(f'{r["kind"]:10} {r["groups"]:5} {r["batch"]:5} {r["paths"]["metal"]["effective_ms_per_dispatch_with_readback"]:17.6f} {r["paths"]["nak"]["effective_ms_per_dispatch_with_readback"]:15.6f} {r["paired_median_NAK_over_Metal_wall_ratio"]:16.3f}')
lines+=['','Ratio >1 : NAK prend davantage de temps sur ces essais ; ratio <1 : moins.',
 'Les médianes/IQR/min/max et les216mesures sont dans les fichiers JSON.',
 'Un résultat sur ces kernels instrumentés ne vaut pas gain général sous Tahoe,',
 'dans un LLM ou WindowServer. Aucune nouvelle famille Metal déclarée.', '',
 'REGISTRES DÉCLARÉS AU PILOTE (occupation réelle non mesurée) :',
 'Le chemin NAK conserve un plancher24 hérité du profil d’import qualifié ;',
 'le compte24 n’est donc pas une mesure du nombre de registres effectivement',
 'utilisés par le programme. Ce plancher est une piste à investiguer, sans',
 'le présenter comme cause démontrée des écarts de temps.']
for kind in ('capacity','add'):
    r=next(r for r in records if r['kind']==kind);lines.append(f'{kind}: Metal natif {r["native_registers"]} GPR ; NAK {r["NAK_registers"]} GPR.')
lines+=['',f'Groupes terminés vérifiés pendant les mesures : {finished_groups}.',f'Mots bruts des captures finales vérifiés : {checked_words}.','Pilote inchangé : '+m['driver_sha256'],'',
 'REPRODUCTION — bibliothèque auditée àbuild/import-audit/libKeplerProgramImport.dylib',
 'python3 tools/reproduce_shared_benchmark.py --out results/shared-benchmark-reproduction',
 'python3 tools/make_shared_benchmark_report.py --input results/shared-benchmark-reproduction',
 str(folder.relative_to(root))+'/commands.json et manifest.json : commandes, sources et hashes.',
 'Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2.']
(root/'COMPARAISON_METAL_NAK.txt').write_text('\n'.join(lines)+'\n');print(json.dumps({'cases':12,'GPU_groups':finished_groups,'raw_words':checked_words,'selected':[{'kind':r['kind'],'batch':r['batch'],'metal_ms_per_dispatch':r['paths']['metal']['effective_ms_per_dispatch_with_readback'],'NAK_ms_per_dispatch':r['paths']['nak']['effective_ms_per_dispatch_with_readback'],'ratio':r['paired_median_NAK_over_Metal_wall_ratio'],'GPR':[r['native_registers'],r['NAK_registers']]}for r in records if r['groups']==64]},indent=2))

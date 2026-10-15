#!/usr/bin/env python3
"""Verify shared-memory and atomic raw outputs without trusting probe counters."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/shared-units-final');parser.add_argument('--check-only',action='store_true')
args=parser.parse_args();folder=args.input.resolve();folder.relative_to(root/'results');manifest=json.loads((folder/'manifest.json').read_text())
assert manifest['driver_unchanged'] and (not manifest['quick'] or args.check_only)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(folder/'libKeplerProgramImport.dylib')==manifest['library_sha256']
for artifact in manifest['source_snapshot']+manifest['carriers']+manifest['shaders']:assert sha(root/artifact['path'])==artifact['sha256']
source=(folder/'source-snapshot/shared_units_carrier.metal').read_text()
assert 'atomic_compare_exchange_weak_explicit' not in source and 'previous=atomic_load_explicit' in source
MASK=0xffffffff;GKEY=0x00100001;PKEY=0x6a09e667;CKEY=0xabad1dea
records=[];fixtures=set();paired={};capacity_words=dict.fromkeys(('nak','reference','control'),0);atomic_threads=dict.fromkeys(capacity_words,0);capacity_bytes=set();operations=set();reused=0
for case in manifest['cases']:
    d=json.loads((root/case['result']).read_text());kind=d['kind'];mode=d['mode'];local=d['local'];groups=d['groups'];active=d['active'];variant=d['variant'];staging=d['staging'];shared=d['shared_bytes']
    config={k:d[k] for k in ('mode','local','groups','active','variant','staging')};assert config==case['configuration']
    key=(kind,shared,local,groups,active,variant,staging,mode);assert key not in fixtures;fixtures.add(key)
    assert d['device']=='NVIDIA GeForce GTX 880M' and d['command_status']==4
    assert d['mismatches']==d['guard_mismatches']==0
    assert shared<=d['static_threadgroup_bytes']<=d['reported_max_threadgroup_bytes']==49152 and local<=d['pipeline_max_threads']
    seed=0xfffffff0 if variant else 0xf00d5000;assert seed==d['seed'] and d['operand']==0x12345678
    if mode=='nak':
        proof=d['import'];assert proof['contract_verified'] and proof['device']==d['device'] and proof['registry_id']==d['registry_id']
        assert len(proof['events'])==1;e=proof['events'][0]
        shader=next(s for s in manifest['shaders'] if s['kind']==kind and s['info']['shared_bytes']==shared)
        assert e['code_replaced'] and e['imported_code_identical'] and e['valid_container'] and e['stage']==5
        assert e['decoded_code_bytes']==shader['info']['code_bytes'] and e['decoded_registers']==shader['info']['registers']
        assert e['launch_words_9_11']==[576,576]
    dump=root/case['dump'];raw=dump.read_bytes();count=groups*(shared//4)*2 if kind=='capacity' else groups*(local+1)
    assert count==d['output_words'] and len(raw)==count*4+128
    assert raw[:64]==raw[-64:]==bytes([0xa5])*64
    values=list(struct.unpack('<'+'I'*count,raw[64:-64]));control=CKEY if mode=='control' else 0
    if kind=='capacity':
        words=shared//4;capacity_bytes.add(shared)
        for group in range(groups):
            for phase in range(2):
                multiplier,offset=(7,13) if phase else (5,7)
                for i in range(words):
                    index=(i*multiplier+offset)%words
                    expected=((index*0x9e3779b9)&MASK)^(seed^((group*GKEY)&MASK))^(PKEY if phase else 0)^control
                    assert values[group*words*2+phase*words+i]==expected,(case['label'],group,phase,i)
        capacity_words[mode]+=count
    else:
        assert kind in ('add','exchange','cas') and 0<active<=local
        operations.add(kind)
        for group in range(groups):
            initial=(seed+group*GKEY)&MASK;returned=values[group*(local+1):group*(local+1)+active];final=values[group*(local+1)+local]
            assert values[group*(local+1)+active:group*(local+1)+local]==[0xa5a5a5a5]*(local-active)
            if kind=='add':
                step=2 if mode=='control' else 1;assert final==(initial+step*active)&MASK
                assert sorted(returned)==sorted((initial+step*i)&MASK for i in range(active))
            elif kind=='exchange':
                assert sorted(returned+[final])==sorted([initial]+[(d['operand']^i)^control for i in range(active)])
            else:
                replacement=d['operand']^control;assert final==(initial if variant else replacement)
                expected=[initial]*active if variant else [initial]+[replacement]*(active-1)
                assert sorted(returned)==sorted(expected)
        atomic_threads[mode]+=groups*active
    reused+=d['pipeline_reused'];paired[key[:-1]+(mode,)]=values
    records.append({**case,'kind':kind,'shared_bytes':shared,**config,'output_words':count,'pipeline_reused':d['pipeline_reused'],'sha256':sha(dump)})
sizes=(16384,) if manifest['quick'] else (16384,32768,49152);expected_keys=set()
if manifest['kinds'] in ('all','capacity'):
    for shared in sizes:
        configurations=[(128,1,0,0,'nocopy')] if manifest['quick'] else [(local,groups,0,0,staging) for local in (128,1024) for groups in (1,3) for staging in ('managed','nocopy')]
        expected_keys.update(('capacity',shared,*c,mode) for c in configurations for mode in capacity_words)
if manifest['kinds'] in ('all','atomics'):
    configurations=[(32,1,31,0,'nocopy')] if manifest['quick'] else [(local,groups,active,variant,staging) for local,active in ((32,31),(128,33),(1024,1024)) for groups in (1,3) for variant in (0,1) for staging in ('managed','nocopy')]
    expected_keys.update((kind,4,*c,mode) for kind in ('add','exchange','cas') for c in configurations for mode in capacity_words)
assert fixtures==expected_keys
for key,values in paired.items():
    if key[-1]!='nak':continue
    reference=paired[key[:-1]+('reference',)];control=paired[key[:-1]+('control',)]
    # Atomics impose no thread order; their CPU multiset invariants are above.
    if key[0]=='capacity':assert values==reference
    if key[0]=='cas' and key[5]==1:assert values==reference==control
    else:assert values!=control
compact={'cases':len(records),'capacity_output_words_by_mode':capacity_words,'active_atomic_threads_by_mode':atomic_threads,'shared_bytes_qualified':sorted(capacity_bytes),'atomic_operations':sorted(operations),'pipeline_reuse_cases':reused,'independent_raw_byte_oracle_passed':True}
if args.check_only:print(json.dumps(compact,indent=2));sys.exit(0)
assert manifest['kinds']=='all' and len(records)==288 and max(capacity_bytes)==49152
assert capacity_words['nak']==786432 and atomic_threads['nak']==52224
failures=[]
for path in ('results/shared-atomics-first-gpu/failure-manifest.json','results/shared-atomics-serial-reference/failure-manifest.json'):
    f=root/path;assert f.exists();data=json.loads(f.read_text());assert data['terminal_exit_code']==8
    for a in data['source_snapshot']:assert sha(root/a['path'])==a['sha256']
    failures.append({'path':path,'sha256':sha(f)})
isolated=root/'results/shared-cas-reference-isolated/managed-reference.json';isolation=json.loads(isolated.read_text());assert isolation['command_status']==4 and isolation['readback_status']==5 and isolation['readback_error_code']==9
failed_launcher=json.loads((isolated.parent/'execution/manifest.json').read_text());assert failed_launcher['exit_code']==8 and not failed_launcher['authoritative_ps_status']
failure={'manifests':failures,'fresh_process_managed_reference':str(isolated.relative_to(root)),'error':isolation['readback_error'],'error_domain':isolation['readback_error_domain'],'error_code':9,'cause_established':False,'native_Metal_weak_shared_CAS_qualified':False,'CAS_oracle':'Serialized atomic load/compare/store with one writer and uniform workgroup barriers; it is a valid sequential reference, not a native CAS API test; NAK CAS remains contended'}
ledger_path=root/'results/hardware-coverage.json';ledger=json.loads(ledger_path.read_text());updates=[]
additions={
 'Shared memory and workgroup barriers':'Full-span16/32/48KiB shared arrays, two writes and cross-thread permutations with three uniform barriers;128/1024-thread groups,1/3groups,Managed/NoCopy;24 NAK capacity fixtures and786432 exact output words; shared uint32 ADD/EXCH/CAS via SM30 ld-lock/st-unlock loops,72 NAK fixtures,31/33/1024 active threads including partial warps,52224 active atomic thread operations; wrap, CAS success/miss, exact exchange return-chain multisets; independent Python raw-byte oracle; native/reference/control fixtures; Metal weak shared-CAS reference InvalidResource retained separately',
 'Application-local native program import':'Six shared-unit SM30 programs with original carrier shared-memory allocations preserved; immutable pipelines reused across varying uniforms/local sizes/staging; controls have distinct function names; imported-code identity/size/GPR verified;288 capacity/atomic/reference/control fixtures',
 'Metal API coverage':'Native shared capacity up to48KiB and selected contended uint32 shared ADD/EXCH fixtures pass CPU oracles; native weak shared-CAS readback fails InvalidResource in fresh process/Managed; no cause or full API conformance established; NAK provides independently verified shared-CAS implementation'
}
for category,addition in additions.items():
    row=next(r for r in ledger['coverage'] if r['category']==category)
    if addition not in row['tested_scope']:row['tested_scope']+='; '+addition
    if category=='Shared memory and workgroup barriers':row['remaining_requirements']='Bank-mode selection/throughput, further atomic types/operations including64bit and float, explicit ordering/scope/contention corner cases and sustained/concurrent lifecycle; native Metal weak-CAS InvalidResource cause remains open; no full API atomics/shared-memory conformance'
    if category=='Metal API coverage':row['status']='partially_available'
    for evidence in ('results/shared-units-summary.json',str((folder/'manifest.json').relative_to(root)),'tools/shared_units_compile.c','tools/shared_units_probe.mm','tools/make_shared_units_report.py','MEMOIRE_PARTAGEE.txt',str(isolated.relative_to(root))):
        if evidence not in row['evidence']:row['evidence'].append(evidence)
    updates.append(row)
summary={**compact,'collected_at':manifest['collected_at'],'driver_unchanged':True,'driver_sha256':manifest['driver_sha256'],'performance_benchmark':False,'raw_mismatches':0,'guard_mismatches':0,'records':records,'shaders':manifest['shaders'],'native_weak_CAS_reference_failure':failure,'coverage_updates':updates,'oracle_source_sha256':sha(Path(__file__)),'global_hardware_goal_complete':False}
ledger['complete']=False;ledger_path.write_text(json.dumps(ledger,indent=2)+'\n');(root/'results/shared-units-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['KEPLERMETAL — mémoire partagée et atomiques uint32 sur GTX880M','',
 '288 essais passent :96 NAK,96 références Metal et96 témoins distincts.',
 'La mémoire partagée est parcourue entièrement à16,32et48Kio par groupe.',
 'Chaque mot est écrit, lu par une permutation entre threads, puis réécrit et',
 'lu par une seconde permutation ; trois barrières de groupe ordonnent les phases.',
 'Les permutations sont bijectives pour chacune de ces tailles.128ou1024threads',
 'et1ou3groupes : les valeurs dépendent du groupe pour détecter les interférences.',
 '786432 mots uint32 de sortie NAK contrôlés exactement par Python, après blit',
 'de buffers Private vers des buffers Managed ou NoCopy. Gardes64B intactes.',
 'La capacité48Kio est prouvée par des résultats sur tout le span, au-delà du',
 'simple maxThreadgroupMemoryLength annoncé49152B. Le pilote reste propriétaire',
 'de la configuration physique ; aucun registre ni mode de banque modifié.', '',
 'Atomiques NAK : ADD, EXCH et CAS uint32 en mémoire partagée. Kepler utilise',
 'des boucles de verrouillage : NAK émet ld lock / st unlock, reconnues par',
 'Envytools, et des barrières CTA. Aucun opcode SASS édité manuellement.',
 '31/33/1024threads actifs dans des groupes32/128/1024, avec1ou3groupes :',
 'contention réelle sur un compteur partagé par groupe.72 essais NAK et',
 '52224 opérations logiques de threads ; les retries internes ne sont pas comptés.',
 'ADD : retours multiset exacts, report/wrap modulo2^32. CAS : un succès unique',
 'ou comparaison manquée. EXCH : retours+final égale initial+toutes les écritures.',
 'L’ordre des threads n’est pas imposé. Les retours inactifs restent A5.', '',
 'ÉCHEC NATIF CONSERVÉ — AUCUN SUPPORT COMPLET METAL CAS REVENDIQUÉ',
 'Le shader Metal avec atomic_compare_exchange_weak_explicit échoue au readback',
 'Invalid Resource, code9 / kIOAccelCommandBufferCallbackErrorInvalidResource.',
 'Cela se reproduit avec un CAS séquentiel, puis sans import NAK préalable dans',
 'un processus neuf et avec Managed. Le compute annonçait Completed ; la sortie',
 'n’est donc pas acceptée comme preuve. Les sources et erreurs restent figées.',
 'La cause exacte n’est pas établie : aucune panne matérielle n’est déduite.',
 'Dans la série réussie, la référence CAS utilise lecture/comparaison/écriture',
 'séquentielles avec un seul writer par tour et une barrière uniforme. Elle',
 'vérifie un ordre total valide ; elle ne qualifie pas l’intrinsèque Metal CAS.',
 'Le CAS NAK testé reste concurrent et utilise les locks matériels Kepler.',
 'L’oracle CPU Python vérifie séparément chaque buffer brut, compteur, multiset',
 'et garde. Un témoin produit des valeurs différentes sauf le cas CAS manqué,',
 'où l’absence de mutation est précisément le résultat attendu.', '',
 'LIMITES',
 'Aucun benchmark de gain. Modes4/8B de banques et autres atomiques/types/scopes',
 'non qualifiés. Aucun support général Metal3/4 ou pilote système livré.',
 'Le matériel complet, la vidéo et l’intégration système restent ouverts.', '',
 'REPRODUCTION — depuis bridge, Mesa et libKeplerProgramImport déjà construits',
 'python3 tools/reproduce_shared_units.py --out results/shared-units-reproduction',
 'python3 tools/make_shared_units_report.py --input results/shared-units-reproduction',
 'Le dossier doit être nouveau. Les essais GPU sont regroupés dans des processus',
 'signés isolés, avec un arrêt au premier échec et un suivi explicite des PID.',
 'Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2 ; archive NAK',
 'inchangée depuis le correctif atomic64. Les passes de shared atomics existent',
 'déjà dans Mesa ; aucun nouveau correctif de compilateur nécessaire ici.',
 str(folder.relative_to(root))+'/manifest.json : sources/codes/carriers et hashes.',
 str(folder.relative_to(root))+'/commands.json : compilation et exécution exactes.',
 'Les diagnostics faibles CAS précédents sont conservés sous',
 'results/shared-atomics-first-gpu/, shared-atomics-serial-reference/ et',
 'shared-cas-reference-isolated/. Leurs échecs ne sont pas relancés par la recette.', '',
 'Programmes SM30 / SHA256 :']
for shader in manifest['shaders']:lines.append(shader['kind']+' '+str(shader['info']['shared_bytes'])+'B : '+shader['sha256'])
lines+=['','Pilote GeForceMTLDriver inchangé : '+manifest['driver_sha256'],
 'Ni macOS,ni OCLP,ni protections,VBIOS,horloges ou registres système modifiés.',
 'Objectif complet toujours ouvert : results/hardware-coverage.json.','',
 'Sources primaires sur la capacité et le mécanisme Kepler :',
 'https://docs.nvidia.com/cuda/archive/11.8.0/kepler-tuning-guide/index.html',
 'https://developer.nvidia.com/blog/gpu-pro-tip-fast-histograms-using-shared-atomics-maxwell/',
 'vendor/mesa-26.2.4/src/nouveau/compiler/nak_nir_lower_shared_atomics.c',
 'vendor/mesa-26.2.4/src/nouveau/compiler/nak/sm20.rs']
(root/'MEMOIRE_PARTAGEE.txt').write_text('\n'.join(lines)+'\n');print(json.dumps(compact,indent=2))

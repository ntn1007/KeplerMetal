#!/usr/bin/env python3
"""Independently verify raw uint64 outputs and record restricted hardware coverage."""
from pathlib import Path
import argparse,hashlib,json,struct
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/atomic64-final')
folder=parser.parse_args().input.resolve();folder.relative_to(root/'results');manifest=json.loads((folder/'manifest.json').read_text())
assert manifest['driver_unchanged'] and not manifest['quick']
assert hashlib.sha256((folder/'kepler_carrier.metallib').read_bytes()).hexdigest()==manifest['carrier_sha256']
assert hashlib.sha256((folder/'libKeplerProgramImport.dylib').read_bytes()).hexdigest()==manifest['library_sha256']
for a in manifest['source_snapshot']+manifest['shaders']:
    assert hashlib.sha256((root/a['path']).read_bytes()).hexdigest()==a['sha256']
MASK=(1<<64)-1;STEP=0x100000003;COMPARE=0x2fffffff0;REPLACEMENT=0x12345678abcdef00;BASE=0x12340000fffffff0;EXSTEP=0x100000009
records=[];operations=0;returnedChecked=0
for case in manifest['cases']:
    assert case['exit_code']==0;d=json.loads((root/case['result']).read_text());info=d['shader_info'];operation=info['operation'];count=d['count'];variant=d['variant'];rounds=d['rounds'];returns=info['return_values']
    assert d['mismatches']==d['guard_mismatches']==0 and d['command_status']==4
    assert d['invocation_counter_enabled'] and d['invocations_counted']==count*rounds and d['import']['contract_verified']
    assert all(e['imported_code_identical'] for e in d['import']['events'])
    if operation=='add':initial=0x2ffffff00 if variant==0 else 0xffffffffffffff00
    elif operation=='cas':initial=(COMPARE,0x5fffffff0,0x2fffffff8)[variant]
    else:initial=COMPARE if variant==0 else 0xffffffffffffff00
    assert d['initial']==initial
    counter=(folder/(case['label']+'-data.counter.bin')).read_bytes();raw=(folder/(case['label']+'-data.returned.bin')).read_bytes()
    actual=struct.unpack_from('<Q',counter,64)[0];values=[v[0] for v in struct.iter_unpack('<Q',raw[64:64+count*8])]
    assert actual==d['final'];assert all(b==0xa5 for b in counter[:64]+counter[72:]);assert all(b==0xa5 for b in raw[:64]+raw[64+count*8:])
    if operation=='add':
        assert actual==(initial+count*rounds*STEP)&MASK
        expected=[(initial+(count*(rounds-1)+i)*STEP)&MASK for i in range(count)]
        if returns:assert sorted(values)==sorted(expected)
    elif operation=='cas':
        matched=initial==COMPARE;assert actual==(REPLACEMENT if matched else initial)
        if returns:assert sorted(values)==sorted([initial]+[REPLACEMENT]*(count-1) if matched else [initial]*count)
    else:
        writes=[(BASE+i*EXSTEP)&MASK for i in range(count)]
        if returns:assert sorted(values+[actual])==sorted([initial]+writes)
        else:assert actual in writes
    if not returns:assert all(b==0xa5 for b in raw)
    operations+=count*rounds;returnedChecked+=count if returns else 0
    records.append({**case,'operation':operation,'return_values':returns,'count':count,'variant':variant,'rounds':rounds,'staging':d['staging'],'initial':initial,'final':actual,'invocations_counted':d['invocations_counted']})
assert len(records)==72 and {r['operation'] for r in records}=={'add','cas','exchange'}
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text());row=next(r for r in ledger['coverage'] if r['category']=='Global atomic arithmetic')
addition='Native SM30 global uint64 ADD/EXCH/CAS with returned and discarded values;72fixtures,1..1025threads, low-word carry/full64wrap, compare misses in each32bit half, exact exchange return-chain multisets; Managed/NoCopy staging and Private buffers; independent Python raw-byte oracles; GPU uint32 invocation counter verifies35610operations'
if addition not in row['tested_scope']:row['tested_scope']+='; '+addition
row['remaining_requirements']='Further unsigned/signed/float operations and explicit ordering/contention cases, shared atomics; hardware3.0 lacks native full64bit min/max/bitwise and double-add families, which require separate implementation/conformance; no Metal/Vulkan full atomic64 feature qualified'
for evidence in ('results/atomic64-summary.json',str((folder/'manifest.json').relative_to(root)),'src/mesa-26.2.4-atomic64-import.patch','tools/atomic64_compile.c','tools/atomic64_probe.mm','ATOMIQUES_64.txt'):
    if evidence not in row['evidence']:row['evidence'].append(evidence)
ledger['complete']=False;ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n')
summary={'collected_at':manifest['collected_at'],'cases':len(records),'uint64_atomic_operations_counted':operations,'returned_values_checked':returnedChecked,'mismatches':0,'guard_mismatches':0,'independent_raw_byte_oracle_passed':True,'driver_sha256':manifest['driver_sha256'],'driver_unchanged':True,'performance_benchmark':False,'records':records,'shaders':manifest['shaders'],'coverage_updates':[row],'global_hardware_goal_complete':False}
regression=root/'results/atomic64-regression/gpu32/execution.stdout'
if regression.exists():
    r=json.loads(regression.read_text());assert r['mismatches']==r['changed_guards']==0 and r['expected_atomic_total']==4100 and r['import']['contract_verified']
    newer=root/'results/atomic64-regression/atomic32.sass';older=root/'build/atomic32.sass';assert newer.read_bytes()==older.read_bytes()
    summary['atomic32_regression']={'result':str(regression.relative_to(root)),'expected_total':4100,'mismatches':0,'changed_guards':0,'code_unchanged':True,'sha256':hashlib.sha256(newer.read_bytes()).hexdigest()}
assert operations==35610
(root/'results/atomic64-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['KEPLERMETAL — atomiques globales64bits sur GTX880M','',
 'NAK SM20/SM30 refusait tous les types atomiques64bits. Le premier essai de',
 'compilation a terminé avec2 et le message64-bit atomics are not supported.',
 'Le correctif isolé autorise seulement uint64 ADD/EXCH/CAS, dont les encodages',
 'figurent dans Nouveau NVC0 et sont documentés par NVIDIA pour GK104.',
 'Exch/CAS utilisent la forme qui retourne une valeur, avec rZ si elle est ignorée ;',
 'la forme réduction ne peut pas représenter ces deux opérations.',
 'Les autres types/ops64 restent refusés. Aucun identifiant de famille/API changé.','',
 f'{len(records)} cas GPU passent ; {operations} opérations atomiques64 comptées sur GPU.',
 f'{returnedChecked} valeurs retournées sont vérifiées, en plus des compteurs et gardes.',
 'Six kernels : add/cas/exchange, puis mêmes opérations avec valeur ignorée.',
 'Un atomic add32 séparé vérifie le nombre exact d’invocations actives.',
 '1/31/32/33/257/1025threads selon fixture ; groupes32, masques partiels.',
 'Addition : valeur >32bits, report entre deux mots et wrap modulo2^64 ;1ou4',
 'dispatches. Les valeurs retournées forment la progression attendue dans un',
 'ordre quelconque, comparée comme multiset (aucun ordre de thread imposé).',
 'CAS : une réussite parmi les threads ; aucun succès si seul le mot haut ou',
 'le mot bas diffère. Les retours exacts et le compteur final sont vérifiés.',
 'Exchange : retours+final égale initial+toutes les écritures. Le dernier writer',
 'est indéterministe : aucune valeur finale unique n’est prétendue prédite au CPU.',
 'Sans valeur retournée, la zone de retour reste entièrement àA5, le compteur',
 'd’invocations et le résultat/membership du compteur64 sont vérifiés.',
 'Le script Python relit les dumps de buffers et recalcule les invariants',
 'indépendamment des champs mismatches/expected_final de la sonde C++.',
 'Counter/retours dans des buffers Private ; copiesGPU aller/retour ; staging',
 'Managed ouNoCopy. Prefix64B, suffix et toute zone inutilisée inchangés.',
 'Le counter réserve également le span du shader natif, pour borner l’échec',
 'd’un import : le statutCompleted seul n’aurait pas été une preuve de calcul.',
 'Registres24, scratch/CRS0 ; metadata576/576. Bytecode importé identique,',
 'stage5, deviceGTX880M. Envytools reconnaît les encodages64bits sans unknown.',
 'Aucun opcode SASS n’est patché à la main. Le compilateur produit le binaire.',
 'Aucune mesure de gain ; aucun support général Metal3/4 ou atomics64 API déclaré.','',
 'PROVENANCE ET REPRODUCTION',
 'Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2 ;',
 'correctif src/mesa-26.2.4-atomic64-import.patch. Les trois modifications',
 'texture/embedding antérieures sont conservées.',
 'Rebuild uniquement libnak_rs.a ; versions/commands et archive avant/après :',
 'results/atomic64-build-tools/rebuild-command.json et rebuild-result.json.',
 'Rust1.99.0 : copie signée àresults/signed-rust-prefix/bin/rustc ; lib symlink',
 'vers le prefix original inchangé, pour préserver @loader_path/../lib.',
 'Ninja1.13.2 : tranche x86_64 signée, sans installation système.',
 'Préconditions : Mesa et bibliothèque de raccordement construits ; correctif',
 'appliqué et libnak_rs.a reconstruit (le script vérifie leurs hashes).',
 'Depuis bridge : python3 tools/reproduce_atomic64.py --out results/atomic64-reproduction',
 'puis python3 tools/make_atomic64_report.py --input results/atomic64-reproduction',
 f'Sources/binaires/codes/captures et commandes exactes : {folder.relative_to(root)}/manifest.json',
 f'Commandes : {folder.relative_to(root)}/commands.json',
 'SHA256 de chacun des six programmes :']
for shader in manifest['shaders']:lines.append(shader['kind']+' : '+shader['sha256'])
if summary.get('atomic32_regression'):
    lines+=['','Non-régression : atomic32 compilé avec le nouvel archive est identique',
            'octet par octet à l’ancien shader.4dispatches de1025threads : compteur4100',
            'exact et gardes intactes. Result : results/atomic64-regression/gpu32/.']
lines+=['','Pilote GeForceMTLDriver inchangé : '+manifest['driver_sha256'],
 'macOS/OCLP/protections/VBIOS/horloges/registres système inchangés.',
 'Anciennes sondes bloquées non relancées ; exécution via copies signées isolées.',
 'Objectif complet toujours ouvert : results/hardware-coverage.json.','',
 'Références primaires, capacitésGK104 et distinctionGK110 :',
 'https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/documents/NVIDIA-Kepler-GK110-GK210-Architecture-Whitepaper.pdf',
 'https://docs.nvidia.com/cuda/archive/10.2/cuda-c-programming-guide/index.html#atomic-functions']
(root/'ATOMIQUES_64.txt').write_text('\n'.join(lines)+'\n');print('Raw outputs independently verified;72cases;',operations,'uint64 atomics')

#!/usr/bin/env python3
"""Validate resource evidence, report precision limits and update coverage."""
from pathlib import Path
import argparse
import hashlib
import json

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/resource-final')
folder=parser.parse_args().input.resolve();manifest=json.loads((folder/'manifest.json').read_text());assert manifest['driver_unchanged'] and not manifest['quick']
for artifact in manifest['source_snapshot']+manifest['runtime_snapshot']+manifest['shaders']+manifest.get('native_captures',[]):
    assert hashlib.sha256((root/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
records=[]
for case in manifest['cases']:
    assert case['exit_code']==0,case
    data=json.loads((root/case['result']).read_text());assert data['device']=='NVIDIA GeForce GTX 880M'
    assert data['mismatches']==0 and data['changed_guards']==0 and data['command_status']==4
    if data['mode']=='nak':assert data['import']['contract_verified'] and all(e['imported_code_identical'] for e in data['import']['events'])
    if data['format']=='rgba16f':assert data['half_truncation_model_mismatches']==0
    records.append({**case,'kind':data['kind'],'mode':data['mode'],'memory':data['memory'],'shape':data['shape'],
                    'local_size':data['local_size'],'uniform_variant':data['uniform_variant'],'format':data['format'],
                    'values_checked':data['values_checked'],'maximum_error':data['maximum_error'],
                    'half_nearest_model_mismatches':data['half_nearest_model_mismatches']})
assert len(records)==112
assert {r['kind'] for r in records}=={'buffers_a','buffers_b','image'}
assert {r['format'] for r in records if r['kind']=='image'}=={'rgba32f','rgba16f','rgba8','r32f'}
assert {(32,32,1),(1,1,64),(8,4,2),(4,4,4)}.issubset({tuple(r['local_size']) for r in records if r['mode']=='nak'})
byFormat={name:[r for r in records if r['format']==name] for name in ('none','rgba32f','rgba16f','rgba8','r32f')}
metrics={name:{'cases':len(rows),'values':sum(r['values_checked'] for r in rows),'maximum_error':max(r['maximum_error'] for r in rows)} for name,rows in byFormat.items()}
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text());existing={r['category']:r for r in ledger['coverage']}
evidence=['results/resource-summary.json',str((folder/'manifest.json').relative_to(root)),'src/KeplerResourceABI.h','tools/resource_compile.c','tools/resource_probe.mm']
definitions=[
 ('Application-local native program import','Observed CB1 resource entries:32-byte stride,64-bit GPU address at+8; constant uniforms copied to CB2; two layouts and nonzero buffer offsets qualified; CB1 workgroup size/origin and80-byte surface descriptors used by NAK',
  'General metadata/resource ABI beyond this driver/profile, further stage/binding combinations, scratch/control-stack configurations, sustained/concurrent lifecycle and incompatible-driver handling'),
 ('CPU/GPU memory and DMA','Direct Metal resource bindings for Managed/NoCopy/Private buffers with read/write offsets128/64 and unchanged prefix/suffix guards; typed surface writes followed by GPU readback',
  'Full8GiB coverage, aliasing, memory pressure/eviction, larger spans, lifecycle stress and general synchronization/coherency'),
 ('Grid geometry and control flow','1D/2D/3D grids with partial groups; same NAK binary accepts variable local dimensions1x1x1/4x8x1/32x1x1/8x4x2/4x4x4/1x1x64/32x32x1; tested1024-thread group and64-thread Z extent; dynamic uniform/bounds values',
  'Broader grid limits and origins, deeper control stacks, local/scratch memory and register spilling; divergent synchronization and indirect dispatch'),
 ('Texture/sampler/surface units','SM30 SUCLAMP/IMADSP/SUBFM/SUEAU/SUSTGA writes to2D surfaces; RGBA32Float/RGBA16Float/RGBA8Unorm/R32Float,64x48 and33x17; hardware out-of-bounds suppression on padded dispatches; positive FP16 storage truncation empirically matched',
  'Further binding slots/dimensions/mips/formats, image loads/atomics, gather/compression/coherency; signed/special/subnormal/overflow conversion cases and general format conformance')]
updates=[]
for category,addition,remaining in definitions:
    row=dict(existing[category]);row['status']='sample_qualified'
    if addition not in row['tested_scope']:row['tested_scope']+='; '+addition
    row['remaining_requirements']=remaining;row['evidence']=list(dict.fromkeys(row['evidence']+evidence));updates.append(row)
tessPath=root/'results/tessellation-summary.json'
if tessPath.exists():
    tessUpdates={r['category']:r for r in json.loads(tessPath.read_text()).get('coverage_updates',[])}
    updates=[tessUpdates.get(r['category'],r) for r in updates]
summary={'collected_at':manifest['collected_at'],'cases':len(records),'native_cases':sum(r['mode']=='native' for r in records),
         'nak_cases':sum(r['mode']=='nak' for r in records),'values_checked':sum(r['values_checked'] for r in records),
         'metrics_by_format':metrics,'mismatches':0,'changed_guards':0,'records':records,'coverage_updates':updates,
         'driver_sha256':manifest['driver_sha256'],'driver_unchanged':True,'performance_benchmark':False,'global_hardware_goal_complete':False}
(root/'results/resource-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
byCategory={r['category']:r for r in updates};ledger['coverage']=[byCategory.get(r['category'],r) for r in ledger['coverage']];ledger['complete']=False;ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n')
report=f'''KEPLERMETAL — uniformes, buffers, grilles et écritures d’images
Relevé : {manifest['collected_at']}

112 cas passent (56 NAK et56 témoins natifs), {summary['values_checked']} valeurs CPU/GPU
comparées ; aucune différence hors tolérance et aucune garde modifiée.
Cette étape ne mesure pas les performances ni un gain d’inférence.

BINDINGS RÉUTILISABLES
src/KeplerResourceABI.h décrit le profil observé du driver installé, pas une
ABI générale Apple. CB1 : un entry32B par buffer, adresse64 à offset8+32*binding.
CB2 : copie du seul bloc constant scale/bias/shape de48B. LayoutA : input0,
uniform3, output7 ; layoutB : input5, uniform11, output2. Les offsets buffer
input128/output64 sont inclus par le driver. Aucun pointeur GPU fourni à la main.
Les captures natives, dont un kernel RW avec des LD/ST globaux, établissent
ce contrat. Source/captures figées : {str((folder/'manifest.json').relative_to(root))}
Deux jeux d’uniformes différents passent sans recompilation. Managed, NoCopy
Shared et Private passent, avec copies et synchronisation Managed explicites.
Le résultat NAK ajoute un marqueur différent du programme natif.
Buffers FP32 : erreur maximale {metrics['none']['maximum_error']} dans cette fixture dyadique.

GÉOMÉTRIE COMPUTE VARIABLE
Grilles257x1x1,17x13x3,32x24x2 ; groupes partiels protégés par les bornes.
CB1[0x6f0..0x6f8] fournit les dimensions locales ; CB1[0x710..0x718] l’origine.
Un seul binaire NAK calcule les IDs pour les sept géométries locales :
1x1x1,4x8x1,32x1x1,8x4x2,4x4x4,1x1x64 et32x32x1 (1024 threads).
Les trois axes et les uniformes changent sans reconstruire le programme.
Origines nulles seulement : les origines non nulles ne sont pas qualifiées.

UNITÉS SURFACE
Handle texture0 à CB1[0x400], tableGPU à CB1[0x6e8], stride80B. Les cinq mots
nécessaires sont base>>8/format/clampX/pitch/clampY, offsets0/4/8/12/16.
NAK émet SUCLAMP, IMADSP, SUBFM, SUEAU et SUSTGA ; aucun patch du pilote.
RGBA32Float,RGBA16Float,RGBA8Unorm,R32Float : 64x48 et33x17. Les derniers
groupes débordent les dimensions ; les prédicats surface suppriment ces stores.
Le readback est une copie GPU, avec guard64B après l’image. La couleur NAK
est différente de celle du carrier : blue .75 au lieu de .25, coordonnées+5/+3.

PRÉCISION
RGBA32Float erreur maximale {metrics['rgba32f']['maximum_error']:.9g}, R32Float
{metrics['r32f']['maximum_error']:.9g} ; tolérance absolue1e-6.
RGBA8 erreur maximale {metrics['rgba8']['maximum_error']} LSB ; tolérance1 LSB.
RGBA16Float : égalité exacte au modèle de troncature vers zéro sur les valeurs
positives testées. L’arrondi au plus proche échouait, avec le shader natif aussi.
Le comparatif séparé conserve960/1024 différences sur64x48 et132/165 sur33x17
(natif/NAK) ; zéro différence au modèle tronqué. Écart maximal observé au plus
proche : .0009765625. Preuves : results/half-model-comparison/ et resource-qualified/.
Cette précision est rapportée telle qu’observée ; ce n’est pas une qualification
générale IEEE/MSL, ni de l’arithmétique FP16 native, ni un arrondi au plus proche.

VERSIONS ET REPRODUCTION
Mesa26.2.4 commit {manifest['mesa_commit']}, SM30. Les trois kernels utilisent24 GPR,
sans scratch/CRS. NAK garde le correctif local texture déjà décrit dans GRAPHIQUE.txt.
Le compilateur/runtime/sonde, leurs sources, les SASS et les empreintes sont figés
dans {str((folder/'manifest.json').relative_to(root))} ; les captures natives sont archivées.
SHA256 pilote avant/après : {manifest['driver_sha256']}
Aucun pilote système, OCLP, VBIOS, fréquence ou registre matériel modifié.
Depuis bridge :
python3 tools/reproduce_resources.py --out results/resource-final
python3 tools/make_resource_report.py --input results/resource-final
python3 tools/provenance.py
python3 tools/make_resume.py
Commandes complètes : {str((folder/'commands.json').relative_to(root))}
Préconditions : archives Mesa/NAK et correctifs déjà préparés, envydis,
libKeplerProgramImport et toolchain Xcode. Pas d’installateur système.

RESTANT
Le registre results/hardware-coverage.json garde le but complet ouvert :
formats/bindings/dimensions supplémentaires, lectures/atomiques d’images,
tessellation, scratch/spills, mémoire sous pression, vidéo/énergie/intégration
système et backend tensoriel/LLM. Aucune nouvelle famille Metal qualifiée.
'''
(root/'RESSOURCES_IMAGES.txt').write_text(report);print('Saved RESSOURCES_IMAGES.txt, resource-summary.json and coverage.')

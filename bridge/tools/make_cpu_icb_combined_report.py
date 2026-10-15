#!/usr/bin/env python3
"""Reconcile integrated vertex/index/fragment evidence without completing the goal."""
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];R=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-combined-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
names=['cpu-icb-combined-prepared','cpu-icb-combined-gpu-qualified','cpu-icb-combined-fragment-regression-prepared','cpu-icb-combined-fragment-regression-gpu-qualified','cpu-icb-combined-indexed-regression-prepared','cpu-icb-combined-indexed-regression-gpu-qualified','cpu-icb-combined-mixed-regression-prepared','cpu-icb-combined-mixed-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for n in names:
 p=ROOT/'results'/n;m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and not any(m['signed_executable'] in x for x in ps.splitlines())
 for f,h in read(p/'inputs.json')['source_hashes'].items():
  assert sha(p/f)==h;folder='src' if f.startswith('Kepler') or f.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/f)==h
 v=read(p/('independent-verification.json' if 'mixed-' in n else 'verification.json'));assert v['status']=='PASS';history.append({'cohort':n,'pid':m['pid'],'exit_code':0,'terminal':True})
gpu=read(ROOT/'results/cpu-icb-combined-gpu-qualified/verification.json');fg=read(ROOT/'results/cpu-icb-combined-fragment-regression-gpu-qualified/verification.json');idx=read(ROOT/'results/cpu-icb-combined-indexed-regression-gpu-qualified/verification.json');mix=read(ROOT/'results/cpu-icb-combined-mixed-regression-gpu-qualified/independent-verification.json');assert gpu['correct_float32_channels']==147456 and gpu['GPU_compute_invocations_counted']==128
system=read(OUT/'system-check.json');assert system['system_files_unchanged']==83 and system['rootpatch_unchanged']
for row in system['system_files']:assert sha(Path(row['path']))==row['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256']
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'indexed_fragment_resources_qualified':True,'shader_result':'native texture sample × interpolated vertex/instance color × parameter scale + bias','argument_buffer_encoded_length':24,'fragment_argument_buffers_CPU_accessible_only':True,'GPU_generated_argument_buffers_qualified':False,'Private_argument_buffers_qualified':False,'full_ICB_contract':False,'GPU_generated_ICB':False,'pressure_concurrency_conformance':False,'ordinary_application_integration_complete':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'fragment_regression_float32_channels':fg['correct_float32_channels'],'indexed_regression_float32_channels':idx['correct_float32_channels'],'legacy_mixed_regression_float32_channels':mix['correct_float32_channels'],'legacy_mixed_regression_compute_invocations':mix['GPU_compute_invocations_counted'],'library_SHA256':sha(ROOT/'results/cpu-icb-combined-gpu-qualified/combined_render_resources.metallib'),'manifest_SHA256':sha(ROOT/'src/cpu_icb_combined_profiles.json'),'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current source copy on MrWhite not verified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'machine':system,'current_source_hashes':gpu['source_sha256'],'verifier_SHA256':sha(ROOT/'tools/verify_cpu_icb_combined.py'),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[]})
coverage=read(ROOT/'results/hardware-coverage.json');assert not coverage['complete'] and len(coverage['coverage'])==30
addition=' Integrated indexed stage-in and fragment argument buffers:12CB/15 native copied records/147456 float32 within2e-6, output texture×interpolated vertex+instance color×scale+bias.16/32 indices, baseVertex5/-2, instances2/17/64, smooth/linear/flat, Private vertex/index/texture and native24-byte fragment argument buffer. Native compute128 counted invocations emits UInt32 indices consumed in the same CB with no CPU index read. Caller pipeline+vertex+fragment/bulk/offset/inline states, copies/reset and pre-commit scope release qualified. Separate paths remain qualified by regression. CPU-accessible certified argument buffers only; GPU-resident/generated ICB and general conformance/performance/system integration remain open.'
for row in coverage['coverage']:
 if row['category'] in ('Texture/sampler/surface units','Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
  if addition not in row['tested_scope']:row['tested_scope']+=addition
  for e in ['CPU_ICB_RENDU_COMBINE.txt','results/cpu-icb-combined-progress/summary.json','results/cpu-icb-combined-gpu-qualified/verification.json']:
   if e not in row['evidence']:row['evidence'].append(e)
for p in [ROOT/'results/hardware-coverage.json',R/'inventory/hardware-coverage.json',R/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(R/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
 if row['id'] in ('B10','B10C'):
  row['pipeline_execution_justesse']+=' Pipeline combiné stage-in/indexé+fragmentresources:12CB/15records/147456float32, erreur max4.661e-7; texture×couleur interpolée×scale+bias.16/32 indices etUInt32GPUproduits,128invocationscompute, callerV/F etlifetime/copies/reset PASS.'
  row['modification_necessaire']='Argument buffers Private/écritsGPU, autres formats/ressources/états/cibles, mélange legacy/stage-in, ranges/timeline, ICBGPU-résident/génération, pression/concurrence/conformance globale, benchmark etL2/L3 restent ouverts.'
  row['preuve']+='; ../bridge/CPU_ICB_RENDU_COMBINE.txt; ../bridge/results/cpu-icb-combined-gpu-qualified/verification.json'
dump(R/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (R/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
plans=read(R/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in plans:
 if row['id']=='B2':row['etat']='Stage-in/indexé et fragment argumentbuffer natif réunis enL1,12CB/147456float32 et128invocationsGPUproducer; régressions etcaller/lifetime PASS.';row['travail']='Raccorder argumentbuffersPrivate/GPUécrits au même contrat de référence/résidence/cohérence, puis états/cibles/pression/concurrence. FormatICBGPU-résident/génération, benchmark etL2/L3 restent distincts.'
dump(R/'reports/EXPERIMENTATIONS_PRIORISEES.json',plans)
(ROOT/'CPU_ICB_RENDU_COMBINE.txt').write_text(f'''KEPLERMETAL — PIPELINE NATIF VERTEX/INDEX/FRAGMENT RÉUNI

PROGRESS, objectif global encore incomplet. Branche B : extension applicative
du contrat CPU ICB. Aucune nouvelle modernisation Linux/pilote déployée.

GTX880M :12CB,15 records indexés copiés,147456 float32 corrects,23040pixels
colorés, erreur max {gpu['maximum_float_error']:.12g}, tolérance2e-6.
Le shader calcule texture × couleur vertex/instance interpolée × scale + bias.
Smooth perspective, linear sans perspective, flat; texture read/nearest/linear,
paramètres via pointeur dans argument buffer natif24octets. Les propriétés
vérifiées séparément fonctionnent donc ensemble dans les scénarios du banc.

Indices16/32, baseVertex5 et-2, baseInstance3/5, instances2/17/64. Les Private
vertex/index/textures et paramètres ont des offsets et gardes vérifiés.
128invocations compute natives comptées produisent des indicesUInt32 dans
le même buffer Private consommé par le renderer; aucune lectureCPU entre
compute et render. Contrôles producteur/consommateur absent et dégénérescence,
copies/reset, réutilisation et changement des données privées : sorties attendues.

Compilation/capture :trois pipelines du même module natif. Reflection vertex
deux buffers et fragment ABI24octets/alignment256; encoder natif alignment8.
Macro indexée0x3aa8, indexstate0x1644/0x17c8, directstage-in0x3aa0 observés.
Les setters natifs restent en place. Une amorce indexCount1 sans triangle
matérialise l'état, puis le record natif60octets remplace index+draw seulement.
Lecteur Mach distinct recapture les bytes; oracleCPU interpole puis filtre,
multiplie et ajoute les paramètres. Aucune sortieGPU utilisée comme référence.
Ces macro IDs ne sont pas une équivalence avec les slots MME Nouveau.

L'argument buffer est encodé par MTLArgumentEncoder de la fonction vérifiée,
certifié par identité/ABI/payload/références; lease exact des ressources
indirectes jusqu'àcompletion. Caller après ICB :PSO et bindings vertex/fragment,
arrays, offsets et bytes inline restaurés et dessin ordinaire vérifié au CPU.
DernierCB :scope/classes/ICB et refs locales fermés avantcommit, image correcte.

Régressions avec les mêmes sources :fragment98304float32; indexé147456float32
et128compute; ancien calcul→rendu110592float32/192compute PASS. Huit processus
terminalexit0, sansSIGKILL.83fichiers système/rootpatch OCLP inchangés.
L'erreur de syntaxe du premier générateur d'oracle (quote) est conservée comme
erreur d'outillage; aucune soumissionGPU avant l'oracle prepare réussi.

Bibliothèque :{summary['library_SHA256']}
Manifeste :{summary['manifest_SHA256']}
Driver :2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Git mainUNBORN, aucun commit; versions macOS/clang/SDK et SHA sources :
results/cpu-icb-combined-progress/provenance.json.

Reproduction depuis bridge, dossiers neufs :
python3 tools/reproduce_cpu_icb_combined.py --out results/repro-combined-prepare
python3 tools/verify_cpu_icb_combined.py results/repro-combined-prepare --current
python3 tools/reproduce_cpu_icb_combined.py --execute --out results/repro-combined-gpu
python3 tools/verify_cpu_icb_combined.py results/repro-combined-gpu --current
Scripts :sources/library/manifest, argvclang, binaireshôtes originaux/signés
avecSHA, PID/status et donnéesbrutes conservés. Les anciennes cohortes intactes.

Limites :L1, CPUmaterialisation/copie etamorce parrecord; argumentbuffers
CPU-accessibles certifiés seulement. Domaine post-baseVertex d'indices valides
déclaré5..10 et vérifié aprèsGPU; pas enforcement général d'indicesPrivate.
ArgumentbuffersPrivate/GPUécrits, autres formats/ressources/états/cibles,
pression/concurrence/conformance générale, formatICBGPU-résident/génération,
benchmark et intégrationL2/L3 restent ouverts. Aucun gainCPU/GPU annoncé.
Qwen :deux MCP/moteurs disponibles; job_ids=[] / revueNOTRUN, copie actuelle
des sources surMrWhite non vérifiée. ExécutionsGPU suriMac uniquement.
Prochaineaction :étendre mémoire/références d'argumentbuffers puis qualifier
leur synchronisation, états de rendu et intégration aux applications.
''')
print(json.dumps(summary,ensure_ascii=False,indent=2))

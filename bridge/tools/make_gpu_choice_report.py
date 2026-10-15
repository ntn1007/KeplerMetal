#!/usr/bin/env python3
"""Record dynamic GPU choice and preserve the larger hardware/driver goal."""
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];R=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/gpu-choice-progress';assert not OUT.exists();OUT.mkdir()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['native-gpu-argument-choice-degenerate-prepared','native-gpu-argument-choice-degenerate-gpu-qualified','cpu-icb-gpu-choice-prepared','cpu-icb-gpu-choice-gpu-qualified','cpu-icb-gpu-choice-private-regression-prepared','cpu-icb-gpu-choice-private-regression-gpu-qualified','cpu-icb-gpu-choice-combined-regression-prepared','cpu-icb-gpu-choice-combined-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for name in cohorts:
 p=ROOT/'results'/name;m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and not any(m['signed_executable'] in line for line in ps.splitlines());assert read(p/'verification.json')['status']=='PASS'
 for n,h in read(p/'inputs.json')['source_hashes'].items():assert sha(p/n)==h and sha(ROOT/('src' if n.startswith('Kepler') or n.endswith(('.metal','.json')) else 'tools')/n)==h
 history.append({'cohort':name,'pid':m['pid'],'exit_code':0,'terminal':True})
capture=read(ROOT/'results/gpu-argument-selector-passive/capture.json');assert capture['GPU_submissions']==0 and capture['library_SHA256']=='463dabbbb9538a9aef9baa6e421fe3d0d9783d3823acf12177225c3ad1c47494';m=read(ROOT/'results/gpu-argument-selector-passive/execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
gpu=read(ROOT/'results/cpu-icb-gpu-choice-gpu-qualified/verification.json');native=read(ROOT/'results/native-gpu-argument-choice-degenerate-gpu-qualified/verification.json');private=read(ROOT/'results/cpu-icb-gpu-choice-private-regression-gpu-qualified/verification.json');combined=read(ROOT/'results/cpu-icb-gpu-choice-combined-regression-gpu-qualified/verification.json');assert gpu['correct_float32_channels']==110592 and gpu['counted_producer_threads']==224 and gpu['counted_selector_word_writes']==54
system=read(ROOT/'results/private-arguments-progress/system-check.json')
for row in system['system_files']:assert sha(Path(row['path']))==row['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256'];system['observed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(OUT/'system-check.json',system)
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':system['observed_at'],'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'native_reference_exact_UInt32_words':native['exact_UInt32_words'],'native_reference_counted_threads':native['counted_producer_threads'],'native_reference_counted_word_writes':native['counted_selector_word_writes'],'private_regression_float32_channels':private['correct_float32_channels'],'private_regression_counted_word_writes':private['counted_GPU_word_writes'],'combined_regression_float32_channels':combined['correct_float32_channels'],'combined_regression_compute_invocations':combined['GPU_compute_invocations_counted'],'CPU_bank_value_argument_required':False,'selector_library_independent_of_render_library':True,'selector_library_SHA256':capture['library_SHA256'],'render_library_SHA256':'3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775','private_result_client_must_not_write':True,'general_GPU_handle_generation':False,'ordinary_application_integration_complete':False,'full_ICB_contract':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current source copy on MrWhite unverified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'machine':system,'current_source_sha256':gpu['source_sha256'],'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[],'source_baseline':'results/gpu-choice-source-baseline/SHA256.json','native_strengthening':'Initial native reference used valid indices as the seed and passed numeric checks. Preserved unchanged. A new cohort seeds degenerate indices so actual GPU index writes cause a distinct result; only this stronger cohort is used as the causal reference.'})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete'];addition=' GPU-computed bank choice now drives Private resource tables in indexed CPU ICB:10CB(9render),110592float32 within2e-6, max9.024e-7;224counted producer threads and54selector word writes. Shared-memory reduction of32Private inputs computes a bank, sum/signature and6UInt32indices. Separate SHA-qualified selector library consumes the Private choice, copies one of two native encoded texture/sampler/parameter tables, and render uses it without CPU choice or readback. Smooth/linear/flat, indices16/32, signedbaseVertex5/-2, instances2/17/64, caller/copy/reset/complete reuse/lifetime qualified; omission controls distinguish bank and geometry failures. GPU-produced indices/choice are not GPU-generated ICB; cooperative Private-write restriction and L1 remain.'
for row in coverage['coverage']:
 if row['category'] in ('CPU/GPU memory and DMA','Shared memory and workgroup barriers','Texture/sampler/surface units','Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
  row['tested_scope']+=addition;row['evidence']+=['GPU_CHOIX_RENDU_INDEXE.txt','results/gpu-choice-progress/summary.json','results/cpu-icb-gpu-choice-gpu-qualified/verification.json','results/native-gpu-argument-choice-degenerate-gpu-qualified/verification.json']
for p in [ROOT/'results/hardware-coverage.json',R/'inventory/hardware-coverage.json',R/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(R/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
 if row['id'] in ('B07','B10','B10C'):
  row['pipeline_execution_justesse']+=' Choix de table calculé GPU puis consommé en rendu indexé:10CB/110592float32, erreurmax9.024e-7;224producerthreads/54tablewordwrites. Deux tables natives de ressources, Privatechoice/indices produits et consommés sanslectureCPU. Bibliothèque selector indépendante desPSO; controls absence, copies/reset, caller, completedreuse/lifetime PASS.'
  row['preuve']+='; ../bridge/GPU_CHOIX_RENDU_INDEXE.txt; ../bridge/results/gpu-choice-progress/summary.json'
  row['modification_necessaire']+=' ChoixGPU ettablePrivate raccordés au scopeL1 indexé; autresABI/cibles/états/pression/concurrence/conformance etL2/L3 restent à réaliser. Ni génération générale de handles niICBGPU-résident.'
dump(R/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (R/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
experiments=read(R/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in experiments:
 if row.get('id')=='B2':row['prochaine_action']='Qualifi er autres ABI de tables, états/cibles/formats et cohérence/pression/concurrence; construire une interface L2 documentée et testable par une application adaptée. Choix réellement produit GPU + indices + tables Private raccordés au scope indexé L1. Benchmark et intégration transparente L3 restent distincts.'.replace('Qualifi er','Qualifier')
dump(R/'reports/EXPERIMENTATIONS_PRIORISEES.json',experiments)
report='''KEPLERMETAL — CHOIX GPU DE RESSOURCES ET RENDU INDEXÉ

PROGRESS. Branche B : extension du scope CPU ICB, niveau L1. Objectif global
matériel/pile NVIDIA toujours ouvert. Aucun nouveau pilote Linux/macOS déployé.

Nouveau chemin :10CB dont9rendu,8records indexés copiés,110592float32 corrects,
erreurmax9.024015028558097e-7≤2e-6.224threads producteurs et54écritures de mots
de tables comptés. Le GPU réduit32valeurs Private (128B de données,256B shared
réfléchis), produit uint4(bank,sum,signature,seed) et6indicesUInt32. Un autre
kernel lit ce choix Private, masque bank&1 et copie6mots natifs de la table
sélectionnée. Le renderer consomme cette table et les indices dans le mêmeCB.
Le CPU fournit les données de travail, pas une valeur selectedBank; il ne lit
ni choice ni indices ni payloadPrivate entre les kernels et le rendu.

Les2tables sont encodées par MTLArgumentEncoder :textures2D, samplersnearest/
linear etparamètresPrivate. Aucun handle inventé. Le choixCPU/fragmentshader
est découplé :la bibliothèque de kernels selector est SHA qualifiée, avec
reflections de ses4/5buffers contrôlées, et enregistrée indépendamment du
module vertex/fragment. L'ancienne API selectedBank reste fonctionnelle.
Le producteur lui-même utilise32threads, mémoire partagée etbarrière natives.

PSO smooth/linear/flat; index16CPU etindex32GPU, baseVertex5/-2, baseInstance3/5,
instances2/17/64. Images :texture×couleur interpolée/instance×scale+bias.
Contrôle sansproducteur avec index16valide:tableA, alors que le dataset aurait
sélectionnéB. Sansproducteur/index32dégénéré:aucuntriangle. Sansconsommateur:
imagevide mais les compteurs des kernels avancent. Gardes/inputs/readbacks,
sourceCPUmuté aprèssnapshot, copy/reset, callerV/F etclasse restaurée avant
commit, producercompleted réutilisé dansautreCB :sorties attendues.
Quatre refus :selector non enregistré, alignment/range duchoice etconsommation
d'un autreproducteurCB encore en attente. Tickets faibles etleases exactes des
deux candidats conservés jusqu’àcompletion. L'ABI table24/offset256 reste bornée.

Référence nativeCompute seule :4CB/2824UInt32 exacts,96producerthreads et18
écrituresselector; absenceproducteur et absenceselector contrôlées. Le premier
test utilisait desindices initiaux déjàval ides :résultats numériques corrects,
mais preuve causale moinsforte. Il estconservé. Le test retenu initialise des
indices dégénérés; leur remplacement par leGPU est maintenant observable.

Régressions mêmes sources :ancien PrivateICB98304float32 exacts/30wordwrites;
renducombiné147456float32/128compute, erreurmax4.6609758275195645e-7. Tous les
processus qualifiés terminalexit0 sansSIGKILL.83fichiers système etrootpatchOCLP
rehashés inchangés après les essais. Aucune modification macOS/OCLP/firmware.

Versions :macOS26.7.1/25G241,SDK26.2,clang17; Git mainUNBORN,aucuncommit.
Sources/SHA/binaires originaux+signés/PID/argv/résultatsbruts :cohortes inputs,
commands etexecution/manifest; results/gpu-choice-progress/provenance.json.
Selector463dabbbb9538a9aef9baa6e421fe3d0d9783d3823acf12177225c3ad1c47494
Rendu3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054

Reproduction depuisbridge, dossiers neufs :
python3 tools/reproduce_gpu_argument_selector.py --out results/repro-selector-capture
python3 tools/reproduce_native_gpu_argument_choice.py --out results/repro-choice-native-prepare
python3 tools/verify_native_gpu_argument_choice.py results/repro-choice-native-prepare --current
python3 tools/reproduce_native_gpu_argument_choice.py --execute --out results/repro-choice-native-gpu
python3 tools/verify_native_gpu_argument_choice.py results/repro-choice-native-gpu --current
python3 tools/reproduce_cpu_icb_gpu_choice.py --out results/repro-choice-icb-prepare
python3 tools/verify_cpu_icb_gpu_choice.py results/repro-choice-icb-prepare --current
python3 tools/reproduce_cpu_icb_gpu_choice.py --execute --out results/repro-choice-icb-gpu
python3 tools/verify_cpu_icb_gpu_choice.py results/repro-choice-icb-gpu --current
Les helpers copient les bibliothèques SHA épinglées duworkspace existant; aucun
fichier source ou binaire de cohorte gelée n'est modifié pendant la reproduction.

Limites :L1. Client ne doit pas écrire la tablePrivate retournée (contrat
coopératif, pas détection générale de mutations privées). Deux tables natives
certifiées, uneABI24/alignment256, raster64x48RGBA32F; aucun ICBrésident/généré
parGPU, aucun nouvelhandleGPU arbitraire. AutresABI/états/formats/cibles,
concurrence/pression/conformance etinterfacesL2/L3 restent à réaliser.
Les commandes sont encore matérialisées/copiéesCPU avec amorce native parrecord.
Aucun gain de performance annoncé. Réparation nativeCAS/pisteLinux brancheA
restent des chantiers distincts; aucune correction générale du pilote installée.
Qwen :MCP disponibles/authentifiés, job_ids=[] /revue NOTRUN; copie exacte
actuelle surMrWhite nonconfirmée. ObservationsGPU réalisées suriMac uniquement.

Prochaineaction :élargir ABI/ressources etétats/cibles, qualifier les durées de
vie/résidence/cohérence/concurrence, puis une interface L2 exploitable par une
application adaptée; intégration transparente L3 etbenchmark toujours ouverts.
'''.replace('déjàval ides','déjà valides')
(ROOT/'GPU_CHOIX_RENDU_INDEXE.txt').write_text(report)
print(json.dumps(summary,indent=2))

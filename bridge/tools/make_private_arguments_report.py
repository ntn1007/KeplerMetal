#!/usr/bin/env python3
"""Reconcile Private argument-table evidence and preserve the full objective."""
from pathlib import Path
import csv, datetime, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/private-arguments-progress'
assert not OUT.exists();OUT.mkdir()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['native-private-arguments-prepared-v2','native-private-arguments-gpu-qualified','cpu-icb-private-arguments-prepared','cpu-icb-private-arguments-gpu-qualified','cpu-icb-private-combined-regression-prepared','cpu-icb-private-combined-regression-gpu-qualified','cpu-icb-private-fragment-regression-prepared','cpu-icb-private-fragment-regression-gpu-qualified']
history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for name in cohorts+['native-private-arguments-prepared','native-private-arguments-prepared-diagnostic']:
 root=ROOT/'results'/name;m=read(root/'execution/manifest.json');failed=name in ('native-private-arguments-prepared','native-private-arguments-prepared-diagnostic');assert m['exit_code']==(8 if failed else 0) and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert not any(m['signed_executable'] in line for line in ps.splitlines())
 for n,h in read(root/'inputs.json')['source_hashes'].items():
  assert sha(root/n)==h
  if not failed:assert sha(ROOT/('src' if n.startswith('Kepler') or n.endswith(('.metal','.json')) else 'tools')/n)==h
 if not failed:assert read(root/'verification.json')['status']=='PASS'
 history.append({'cohort':name,'pid':m['pid'],'exit_code':m['exit_code'],'terminal':True,'GPU_submission':not failed and 'gpu-qualified' in name,'failed_guard_not_GPU_execution':failed})
native=read(ROOT/'results/native-private-arguments-gpu-qualified/verification.json');icb=read(ROOT/'results/cpu-icb-private-arguments-gpu-qualified/verification.json');combined=read(ROOT/'results/cpu-icb-private-combined-regression-gpu-qualified/verification.json');fragment=read(ROOT/'results/cpu-icb-private-fragment-regression-gpu-qualified/verification.json')
assert native['correct_float32_channels']==86016 and native['counted_GPU_word_writes']==24 and icb['correct_float32_channels']==98304 and icb['counted_GPU_word_writes']==30
system=read(ROOT/'results/cpu-icb-combined-progress/system-check.json')
for r in system['system_files']:assert sha(Path(r['path']))==r['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256'];system['observed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(OUT/'system-check.json',system)
summary={k:v for k,v in icb.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':system['observed_at'],'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'native_baseline_float32_channels':86016,'native_baseline_counted_GPU_word_writes':24,'combined_regression_float32_channels':combined['correct_float32_channels'],'combined_regression_compute_invocations':combined['GPU_compute_invocations_counted'],'fragment_regression_float32_channels':fragment['correct_float32_channels'],'native_argument_encoding_retained':True,'general_GPU_handle_generation':False,'Private_contents_pointer_exposed_on_this_driver':True,'CPU_access_to_Private_contents':False,'private_result_client_must_not_write':True,'private_factory_current_ABI':{'bytes':24,'alignment':256,'offset':256,'source_tables':[1,2]},'GPU_selector_library_SHA256':'16fb242714c00ac7390a923fc4953ea3b94ae7623431d79c18e354beb616c77f','library_SHA256':sha(ROOT/'results/cpu-icb-private-arguments-gpu-qualified/private_fragment_resources.metallib'),'manifest_SHA256':sha(ROOT/'src/cpu_icb_private_argument_profiles.json'),'ordinary_application_integration_complete':False,'full_ICB_contract':False,'GPU_generated_ICB':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current source copy on MrWhite not verified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'machine':system,'source_sha256':icb['source_sha256'],'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[],'source_baseline':'results/private-arguments-source-baseline/SHA256.json','preparation_failures':'Private buffer unexpectedly exposes a contents pointer. Initial CPU assumption exit8, repeated with diagnostic; corrected by checking storageMode and never dereferencing Private contents. No GPU submissions in either failed cohort. A premature verifier invocation before the build completed reported missing results.json; the same running session was polled and completed normally, without restart.'})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete']
addition=' Private argument tables now consumed through scoped CPU render ICB: native baseline7CB/86016float32 exact/24countedGPUwordwrites; scoped9CB(8render)/98304float32 exact/30GPUwordwrites. NativeMTLArgumentEncoder textures/samplers/Privateparameter references, immutable CPU source snapshots, nativeblit or SHA-qualifiedGPUselector, no CPU Private-payload read. Pending foreign CB refused; completed producer reused; copies/reset, caller state, source mutation and precommit scope restoration qualified. Native Private buffers expose a contents pointer on this driver; CPU encoding now rejects that storage mode explicitly. Cooperative contract forbids client writes to returned tables; arbitrary Private contents/GPU handles and full ICB conformance are not qualified.'
for row in coverage['coverage']:
 if row['category'] in ('CPU/GPU memory and DMA','Texture/sampler/surface units','Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
  row['tested_scope']+=addition;row['evidence']+=['ARGUMENT_BUFFERS_PRIVES.txt','results/private-arguments-progress/summary.json','results/native-private-arguments-gpu-qualified/verification.json','results/cpu-icb-private-arguments-gpu-qualified/verification.json'];row['remaining_requirements']=row['remaining_requirements'].replace('argumentbuffersPrivate/GPU-written','broader Private/GPU-written argument-buffer ABIs').replace('Private/GPUwritten argbuffers','broader Private/GPUwritten argument-buffer ABIs')
for p in [ROOT/'results/hardware-coverage.json',RESEARCH/'inventory/hardware-coverage.json',RESEARCH/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
 if row['id'] in ('B07','B10','B10C'):
  row['pipeline_execution_justesse']+=' Argument tables Private:baseline native7CB/86016float32 exacts/24GPUwordwrites; raccordement CPU ICB9CB/98304float32 exacts/30wordwrites. Blit et sélection GPU de deux tables natives encodées; snapshots CPU immuables, pending-foreign-CB refusé, completed reuse, copies/reset/caller/lifetime PASS.'
  row['preuve']+='; ../bridge/ARGUMENT_BUFFERS_PRIVES.txt; ../bridge/results/private-arguments-progress/summary.json'
  row['modification_necessaire']+=' Extension scope L1 réalisée pourABI24/offset256 et1/2tables; tables natives de ressources préencodées, pas génération générale de handlesGPU. Interdire les écritures clientes du résultat, qualifier autresABIs/stages/choixGPU et concurrence/résidence/pression.'
dump(RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
experiments=read(RESEARCH/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in experiments:
 if row.get('id')=='B2':row['prochaine_action']='Étendre la sélection GPU de tables natives certifiées aux pipelines stage-in/indexés et autres ABI; qualifier états/cibles, résidence/cohérence/pression/concurrence et contrat ICB complet. Private24/offset256 raccordé au scope; nativeGPUselection n’est pas GPUgeneratedICB. Mesurer ensuite coût CPU avant toute intégrationL2/L3.'
dump(RESEARCH/'reports/EXPERIMENTATIONS_PRIORISEES.json',experiments)
report='''KEPLERMETAL — ARGUMENT BUFFERS PRIVÉS ET SÉLECTION GPU

PROGRESS. Branche B : raccordement au scope CPU ICB. Aucune mise à jour du
pilote système, aucun portage Linux déployé. Objectif matériel complet ouvert.

Chemin natif de référence :7CB,86016float32 exacts,24écrituresUInt32 comptées.
La table24octets est créée par MTLArgumentEncoder, avec texture2D/sampler et
pointeur de paramètres Private. Blit ou kernel NVIDIA natif sélectionne/cop ie
les6mots d’une table dans un buffer Private. Un fragment shader la consomme
dans le mêmeCB, sans lecture CPU du payload entre producteur et consommateur.
Deux tables distinctes changent texture, sampler nearest/linear et scale/bias.
Contrôles sans producteur/sans consommateur conservés; gardes/readbacks exacts.

Raccordement ICB :9CB dont8rendu,7macros draw copiées,98304float32 exacts,
30écritures GPU comptées. Amorce native un sommet remplacée par macro trois
sommets; recaptureMachdistincte des commandes. Refus Private CPU encoding,
sourcePrivate et producteur en attente sur autreCB. Réutilisation après réussite
du producteur, copy/reset, état caller, mutation tardive du source et fermeture
du scope/classes avantcommit vérifiés. Snapshots/ressources/PSO/counter conservés
jusqu’àcompletion; ticket du producteur faible, aucun cycle de rétention ajouté.

Découverte :NVMTLBuffer en storageModePrivate expose un pointeur contents.
La préparation initiale s’est arrêtée avant toute soumission (exit8), puis
le diagnostic a identifié cette hypothèse erronée. Le test ne déréférence pas
ces pointeurs. Le prototype exige désormais Shared/Managed pour encodage CPU
et traite les tables Private via leurs opérations de production/synchronisation.
Un vérificateur a été lancé trop tôt pendant le build :results.json absent.
Le processus existant a ensuite terminé; aucun redémarrage de son GPU probe.

Régressions sources identiques :rendu combiné147456float32/128compute, erreur
max4.6609758275195645e-7; fragment98304float32 exacts. Huit cohortes PASS et
deux échecs de préparation conservés; tous les processus terminaux sansSIGKILL.
83fichiers système etrootpatch OCLP rehashés inchangés après les essais.

Versions :macOS26.7.1 build25G241, clang17.0.0/SDK26.2; Git mainUNBORN,
aucuncommit. SHA sources/argv/PID/binaires originaux etsignés, résultatsbruts :
results/private-arguments-progress/provenance.json et cohortes inputs.json.
GPUlibrary16fb242714c00ac7390a923fc4953ea3b94ae7623431d79c18e354beb616c77f
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054

Reproduction depuis bridge, dossiers neufs et gate avant soumission :
python3 tools/reproduce_native_private_arguments.py --out results/repro-private-native-prepare
python3 tools/verify_native_private_arguments.py results/repro-private-native-prepare --current
python3 tools/reproduce_native_private_arguments.py --execute --out results/repro-private-native-gpu
python3 tools/verify_native_private_arguments.py results/repro-private-native-gpu --current
python3 tools/reproduce_cpu_icb_private_arguments.py --out results/repro-private-icb-prepare
python3 tools/verify_cpu_icb_private_arguments.py results/repro-private-icb-prepare --current
python3 tools/reproduce_cpu_icb_private_arguments.py --execute --out results/repro-private-icb-gpu
python3 tools/verify_cpu_icb_private_arguments.py results/repro-private-icb-gpu --current

API :newPrivateFragmentArgumentBufferForPipeline:bindingIndex:sources:
selectedBank:commandBuffer:counter:error:.1source :blit;2sources :sélectionGPU
sur bibliothèque SHA qualifiée. Résultat1024B et counter512B, offset256.
Le CPU déclare selectedBank0/1 :la sélection/copie est exécutée par le GPU,
mais le choix lui-même n’est pas produit par un autre kernel dans ce banc.

Limites :L1. Les applications doivent adopter le scope. ABI24/alignment256,
1/2tables natives certifiées, selectorGPU actuellement survs_ref/fs_arg_linear.
Contrat coopératif :le client ne doit pas écrire le résultatPrivate. Aucun
contrôle général de mutations privées arbitraires, aucun handleGPU inventé,
aucun ICB GPU-résident/généré. Concurrence/pression/autresABI/états/formats/
cibles et intégrationL2/L3 restent ouverts. Aucun gain de performance annoncé.
Qwenjob_ids=[] :accès MCP/authentification fonctionnels; revue NOTRUN,
copie actuelle exacte des sources surMrWhite nonconfirmée.

Prochaine action :généraliser la sélection de tables aux pipelines indexés,
aux autresABI et à un choix produit par le GPU; qualifier mémoire et états de
rendu, puis une intégration réellement utilisable par des applications adaptées.
'''.replace('cop ie','copie')
(ROOT/'ARGUMENT_BUFFERS_PRIVES.txt').write_text(report)
print(json.dumps({k:v for k,v in summary.items() if k not in ('source_sha256','raw_sha256')},indent=2))

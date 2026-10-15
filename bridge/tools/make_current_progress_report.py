#!/usr/bin/env python3
"""Reconcile pinned CAS, native resource API and measured submission evidence."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/current-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
repair=[read(ROOT/'results'/s/'independent-verification.json') for s in ['native-cas-repaired','native-cas-repaired-1024']]
air=read(ROOT/'results/air-cas-extended/independent-verification.json')
sync=[read(ROOT/'results'/s/'independent-verification.json') for s in ['resource-sync-initial','resource-sync-alias']]
bench=read(ROOT/'results/submission-benchmark-counted/summary.json')
assert sum(r['repaired_cases_passed'] for r in repair)==10 and sum(r['repaired_logical_CAS_operations'] for r in repair)==21912
assert all(not r['guard_mismatches'] for r in repair) and repair[0]['negative_pin_rejected']
assert repair[0]['known_control_failures']==3 and repair[0]['bad_words_and_invariants_in_controls']==9
assert air['NAK_cases_passed']==24 and air['NAK_logical_CAS_operations']==13896 and air['failed']==6
assert [s['blocked_cases'] for s in sync]==[2,0] and [s['negative_controls_detected'] for s in sync]==[1,0]
assert bench['GPU_dispatches_counted']==1536 and bench['GPU_step_audits_verified']==768
old=read(ROOT.parent/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json')
system=[]
for row in old['system_files']:
 actual=sha(Path(row['path']));assert actual==row['sha256'],row['path'];system.append({'path':row['path'],'sha256':actual})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert sha(rootpatch)==old['rootpatch_sha256']
programs={name:{'bytes':(ROOT/'results/native-cas-repaired'/('native-'+name+'.sass')).stat().st_size,
                'sha256':sha(ROOT/'results/native-cas-repaired'/('native-'+name+'.sass'))} for name in ['replay','repaired','trampoline']}
assert programs['replay']['sha256']=='ea09f179ff169422f6f3ac8c3b1f85f020c52f5853106e68becbb0f408ef85e3'
manifest=read(ROOT/'results/native-cas-repaired/manifest.json')
assert programs['repaired']['sha256']==manifest['code_sha256']['repaired']
repair_summary={'repaired_configurations':10,'repaired_captures':30,'logical_CAS_operations':21912,
 'incorrect_repaired_words':0,'guard_mismatches':0,'negative_original_pin_rejected':True,'known_native_control_failures':3,
 'original_native_driver_still_defective':True,'installed_driver_repaired':False,'code':programs,
 'mechanism':'Byte-pinned native shader repair: 0x2d0 redirects to 0x348; replay membar.cta, mov r0,r4, branch back to 0x2d8. Original schedules/instructions otherwise preserved.',
 'scope':'One exact shared uint32 CAS shader; groups1/3, local1/32/33/128/1024, equal/miss, relaxed. No universal native compiler repair or resident-code attestation.'}
dump(ROOT/'results/native-cas-summary.json',repair_summary)
sync_results=[row for s in sync for row in s['results']]
sync_summary={'functional_configurations':sum(s['functional_cases'] for s in sync),'blocked_ICB_configurations':2,
 'raw_captures':sum(s['captures'] for s in sync),'uint32_words_checked':sum(s['uint32_words_checked'] for s in sync),
 'positive_correct_words':sum(s['uint32_words_checked']-s['negative_control_bad_words'] for s in sync),
 'negative_control_bad_words':33797,'guard_bytes_checked':sum(s['guard_bytes_checked'] for s in sync),'guard_mismatches':0,
 'results':sync_results,'ICB_failure':'NVMTLDevice lacks newIndirectCommandBufferWithDescriptor:maxCount:options:; both factories throw before any GPU dispatch.',
 'scope':'Native heaps, heap alias capacity reuse, explicit fences with untracked resources, event/shared-event cross-queue dependency. Event implementation class _MTLSharedEvent; native semaphore hardware/CPU contribution not independently identified.'}
dump(ROOT/'results/resource-sync-summary.json',sync_summary)
head=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=ROOT,capture_output=True,text=True)
inputs=[]
for suite in ['native-cas-repaired','native-cas-repaired-1024','air-cas-extended','resource-sync-initial','resource-sync-alias','submission-benchmark-counted']:
 for name in ['manifest.json','commands.json','results.json','independent-verification.json','summary.json']:
  p=ROOT/'results'/suite/name
  if p.exists():inputs.append({'path':str(p),'sha256':sha(p)})
provenance={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),
 'Git':{'branch':subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip(),
        'commit':head.stdout.strip() if head.returncode==0 else None,'state':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)},
 'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),
 'OpenNVDA_commit':'da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5','Mesa_version':'26.2.4','Mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2',
 'envytools_commit':'f102b82381f3f11cee113d16374c87091db039d9','local_patches_are_uncommitted':True,
 'system_files_rechecked':len(system),'system_files':system,'rootpatch_sha256':sha(rootpatch),'inputs':inputs,'Qwen_jobs':[],
 'scope':'Solo continuation authorized; reports refer to exact archived executed sources, not to newer canonical files as if they were previously executed.'}
assert len(system)==83;dump(OUT/'provenance.json',provenance)
summary={'native_CAS':repair_summary,'AIR_NAK_multi_lane':{k:v for k,v in air.items() if k!='results'},'native_resources':sync_summary,
         'submission_benchmark':bench,'all_hardware_functions_supported':False,'Metal3_or_4_qualified':False,'system_modifications':False}
dump(OUT/'summary.json',summary)
coverage_path=ROOT/'results/hardware-coverage.json';coverage=read(coverage_path)
new_entries=[
 {'category':'Pinned native shared-CAS shader correction','status':'sample_qualified_application_local',
  'tested_scope':'10 configurations,30 captures,21912 CAS operations, local1..1024/group,3groups, exact old/bool/final/index; original and no-copy controls retain fault.',
  'remaining_requirements':'General repair recognition, other shader/register/ABI shapes, explicit order/scope/progression and supported application integration; system native compiler remains defective.',
  'evidence':['results/native-cas-summary.json','results/native-cas-repaired/manifest.json','results/native-cas-repaired-1024/independent-verification.json']},
 {'category':'Native heaps, aliasing, fences and timeline events','status':'sample_qualified_native_API',
  'tested_scope':'Native NVMTLHeap buffers and capacity-controlled makeAliasable reuse; fences over untracked resources; consumer-first cross-queue event/shared-event waits, signals1/2/3. 202782 correct positive uint32 words; guards intact.',
  'remaining_requirements':'Placement heaps, broader memory pressure/lifecycle/concurrency, native event hardware-vs-host mechanism, full synchronization conformance; ICB factories absent from NVMTLDevice.',
  'evidence':['results/resource-sync-summary.json','results/resource-sync-initial/independent-verification.json','results/resource-sync-alias/independent-verification.json']},
 {'category':'Native application CPU submission cost','status':'measured_workload_only',
  'tested_scope':'Persistent resources,32produce/consume pairs per sample; wait_each vs batch32;3warmups+9alternating measured pairs,1536GPU dispatch counter hits and768per-step traces verified.',
  'remaining_requirements':'Integrate applicable batching into a supported real application and measure its end-to-end workload; no driver modernization or global GPU-exclusive speedup proved.',
  'evidence':['results/submission-benchmark-counted/summary.json','tools/submission_benchmark.mm','src/submission_benchmark.metal']},
 {'category':'Native ICB factory/runtime boundary','status':'not_exposed_by_current_driver',
  'tested_scope':'Compute and render factories both throw unrecognized selector on NVMTLDevice before pipeline or GPU work.',
  'remaining_requirements':'Implement resource/command encoding and execution contracts before exposing an ICB capability; physical GK104 feasibility remains to establish.',
  'evidence':['results/resource-sync-summary.json','results/resource-sync-initial/results.json']}]
names={r['category'] for r in new_entries};coverage['coverage']=[r for r in coverage['coverage'] if r['category'] not in names]+new_entries
for row in coverage['coverage']:
 if row['category']=='Apple AIR compare-exchange translated to SM30':
  row['tested_scope']='Same AIR device/threadgroup uint32 CAS:24multi-lane configurations,72NAK captures,13896logical operations,local32/33/128,3groups,unique/contended equal/miss; corrected i32 return ABI.'
  row['remaining_requirements']='Further order/type/ABI/progression coverage and application integration. Exact native shader repair qualified separately; installed native compiler remains defective.'
  row['evidence'] += ['results/air-cas-extended/independent-verification.json']
coverage['complete']=False;dump(coverage_path,coverage)
s=bench['stats_ms'];v=lambda mode,field:s[mode][field]['median'];iq=lambda mode,field:s[mode][field]['IQR']
report=f'''KEPLERMETAL — CAS NATIF, RESSOURCES ET COÛT CPU, 13 octobre 2026

Résultats exécutés sur la GTX 880M, en solo. macOS26.7.1/build25G241.
Les83fichiers système inventoriés et le plist OCLP restent identiques.
Git: main, aucun commit; sources locales et instantanés hashés dans provenance.json.
Aucun jeton ou job Qwen; aucune configuration MCP modifiée.

1. Correction du CAS partagé natif
Shader NVIDIA original832B, réparé896B; SHA exacts dans native-cas-summary.json.
Le trampoline conserve la membar, les branches existantes et tous les anciens
mots de scheduling. Le MOV old r4→expected r0 corrige le retour erroné.
10configurations,30captures,21912CAS vérifiés sans erreur ni garde altérée,
j usqu'à1024threads/groupe et3groupes. Contrôles original/replay/NOP:
3configurations fautives conservées (9mots); empreinte d'entrée erronée refusée
avant remplacement et avant dispatch. Ce correctif cible un shader exact,
dans notre processus; le compilateur/pilote installé n'est pas réparé.
Le même AIR traduit via NAK passe aussi24configurations multi-lanes/groupes,
13896opérations; ses6échecs natifs partagés de référence restent enregistrés.

2. Fonctions déjà opérationnelles dans l'API native
NVMTLHeap: ressources Private calculées et relues correctement.
Alias: heap263168B, deux ressources remplissent sa capacité; troisième refusée,
puis allocation réussie après makeAliasable de la première encore référencée.
Offset de heap observé0→0; résultat GPU correct, aucun stress prolongé qualifié.
Fence: producteur→consommateur sur ressources explicitement Untracked(1).
Event/SharedEvent: deux queues, consommateur soumis avant producteur;
GPU calcule les données attendues et les valeurs SharedEvent1/2/3 sont observées.
Objets Event et SharedEvent sont tous deux _MTLSharedEvent dans cette pile:
la méthode de synchronisation matérielle ou hôte n'est pas attestée séparément.
6configurations positives dont le contrôle direct et l'alias,21captures totales,
202782mots positifs corrects. Le contrôle sans producteur fait33797mots faux
comme requis;2688octets de garde contrôlés, aucune corruption.
ICB rendu et calcul: exception avant dispatch. NVMTLDevice ne fournit pas
newIndirectCommandBufferWithDescriptor:maxCount:options:. Limitation logicielle
constatée; ce test ne prouve pas une impossibilité du silicium.

3. Mesure du coût de soumission (médianes; IQR entre parenthèses)
Même travail:32paires de kernels natifs ×32768éléments, buffers/pipelines
persistants. Chaque paire change de graine.3échauffements puis9essais appariés,
ordre alterné. CompteurGPU1536dispatchs et768traces d'étape vérifiés; résultats,
compteurs et gardes relus par un oracle CPU indépendant.
                                attendre chaqueCB       grouper32paires
Boucle soumission/attente ms      {v('wait_each','total_wall_ms'):.3f} ({iq('wait_each','total_wall_ms'):.3f})         {v('batch32','total_wall_ms'):.3f} ({iq('batch32','total_wall_ms'):.3f})
CPU processus ms                 {v('wait_each','process_cpu_ms'):.3f} ({iq('wait_each','process_cpu_ms'):.3f})         {v('batch32','process_cpu_ms'):.3f} ({iq('batch32','process_cpu_ms'):.3f})
CPU thread appelant ms           {v('wait_each','thread_cpu_ms'):.3f} ({iq('wait_each','thread_cpu_ms'):.3f})          {v('batch32','thread_cpu_ms'):.3f} ({iq('batch32','thread_cpu_ms'):.3f})
Médiane du ratio apparié murale: {bench['wait_each_over_batch32']['total_wall_ms']['paired_median']:.3f}.
Transfert de préparation mesuré séparément: {v('wait_each','upload_wall_ms'):.3f}/{v('batch32','upload_wall_ms'):.3f}ms;
readback: {v('wait_each','readback_wall_ms'):.3f}/{v('batch32','readback_wall_ms'):.3f}ms.
L'amélioration observée concerne ce regroupement applicatif, pas une version
de pilote, un temps GPU exclusif, une inférence LLM ou WindowServer.
Le premier benchmark sans trace des dispatchs est conservé séparément dans
submission-benchmark-final; seules les mesures COUNTED soutiennent ces chiffres.

Reproduction dans un dossier de sortie inédit, depuis Metal 4:
python3 nvidia-880m-lab/bridge/tools/reproduce_native_cas_repair.py --out nvidia-880m-lab/bridge/results/native-cas-repro
python3 nvidia-880m-lab/bridge/tools/extend_native_cas_repair.py --input nvidia-880m-lab/bridge/results/native-cas-repro --out nvidia-880m-lab/bridge/results/native-cas-repro-1024
python3 nvidia-880m-lab/bridge/tools/verify_native_cas_repair.py --input nvidia-880m-lab/bridge/results/native-cas-repro
La première vérification retourne1 à cause des contrôles volontairement fautifs;
les configurations réparées doivent toutes passer, sans masquer ces contrôles.
python3 nvidia-880m-lab/bridge/tools/reproduce_resource_sync.py --out nvidia-880m-lab/bridge/results/resource-sync-repro
python3 nvidia-880m-lab/bridge/tools/verify_resource_sync.py --input nvidia-880m-lab/bridge/results/resource-sync-repro
python3 nvidia-880m-lab/bridge/tools/reproduce_resource_sync.py --only heap_alias --out nvidia-880m-lab/bridge/results/resource-alias-repro
python3 nvidia-880m-lab/bridge/tools/reproduce_submission_benchmark.py --library-input nvidia-880m-lab/bridge/results/resource-sync-repro --out nvidia-880m-lab/bridge/results/submission-counted-repro
python3 nvidia-880m-lab/bridge/tools/verify_submission_benchmark.py --input nvidia-880m-lab/bridge/results/submission-counted-repro

Versions: Mesa26.2.4/96cb43121031992b85767f9c1be8f3f48e22b1d2;
OpenNVDA da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5;
Envytools f102b82381f3f11cee113d16374c87091db039d9.
Patchs non committés identifiés par SHA; sources EXECUTÉES dans chaque dossier,
distinctes des versions canoniques modifiées depuis les premières captures.

Suite: réutiliser les fonctions natives validées, qualifier l'intégration dans
une vraie application adaptée et auditer le contrat ICB manquant. Vidéo,
conformité shader étendue, gestion matérielle et intégration système restent
incomplètes. Aucun support global Metal3/4 ni de tout le matériel revendiqué.
'''
import re
report=report.replace('j usqu\'à','jusqu\'à');report=re.sub(r'(\d)(fichiers|configurations|captures|opérations|mots|octets|threads|groupes|CAS|échauffements|essais|paires|éléments|traces|dispatchs)',r'\1 \2',report)
(OUT/'RAPPORT.txt').write_text(report);(ROOT/'PROGRES_CAS_RESSOURCES_CPU.txt').write_text(report)
dump(OUT/'delivery.json',{'files':[{'path':str(p),'sha256':sha(p)} for p in [OUT/'RAPPORT.txt',OUT/'summary.json',OUT/'provenance.json',ROOT/'results/native-cas-summary.json',ROOT/'results/resource-sync-summary.json',coverage_path]]})
print(json.dumps({'system_files_unchanged':83,'native_CAS_correct_operations':21912,'native_resource_correct_words':202782,'GPU_dispatches_bench_counted':1536,'full_goal_complete':False},indent=2))

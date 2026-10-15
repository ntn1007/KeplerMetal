#!/usr/bin/env python3
"""Reconcile raw GPU proofs, runtime/static ICB evidence and three-mode timings.
No dispatches; rehash every inventoried system file before delivering.
"""
from pathlib import Path
import datetime,hashlib,json,plistlib,statistics,subprocess
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/cas-icb-refinement';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
cas=read(ROOT/'results/native-cas-semantic-qualification/independent-verification.json')
old=read(ROOT/'results/native-cas-summary.json')
bench=read(ROOT/'results/submission-benchmark-three-modes/summary.json')
bench_records=read(ROOT/'results/submission-benchmark-three-modes/results.json')['records']
icb=read(ROOT/'results/icb-contract-inspection/methods.json')
noops=read(ROOT/'results/icb-contract-inspection/static-recheck/verification.json')
compile_icb=read(ROOT/'results/icb-gpu-encoding-pipeline/summary.json')
assert cas['experiment_contract']=='PASS' and cas['repaired_logical_CAS_operations']==8694 and cas['guard_mismatches']==0
assert old['logical_CAS_operations']==21912 and not old['installed_driver_repaired']
assert bench['GPU_dispatches_counted']==2304 and bench['GPU_dispatches_warmups']==576 and bench['GPU_dispatches_measured']==1728
assert noops['status']=='PASS' and sum(c['six_byte_noop'] for c in noops['checks'])==5
assert compile_icb['frontend']=='PASS' and compile_icb['native_pipeline']=='BLOCKED' and not compile_icb['GPU_dispatch']
assert 'Unsupported indirect argument kind "air.command_buffer"' in compile_icb['observation']['error']
strategy=read(LAB/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json');system=[]
for row in strategy['system_files']:
 p=Path(row['path']);actual=sha(p);assert actual==row['sha256'],str(p);system.append({'path':str(p),'sha256':actual})
assert len(system)==83
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert sha(rootpatch)==strategy['rootpatch_sha256']
patch_info=plistlib.loads(rootpatch.read_bytes())
components=read(LAB/'driver-research-2026-10-13/inventory/components.json')
driver_components=[c for c in components if any(x in c.get('executable','') for x in ['GeForceMTLDriver','GeForceAIRPlugin'])]
metal_old=Path(noops['image_path']);assert sha(metal_old)==noops['image_sha256']
original_packet=ROOT/'KEPLERMETAL_CAS_RESSOURCES_CPU_2026-10-13.zip'
assert sha(original_packet)=='d217b82cf46c6285c884a921641928e16e5824b76ba1d4f770b74ba9637a7c04'
assert sha(ROOT/'build/import-audit/libKeplerProgramImport.dylib')=='7719a27c9b659d6b4d87e1d6015c51b4d2cefb3238c47eae11073c3dd975dcd6'
comparisons={}
for first,second in [('wait_each','submit32_wait_end'),('submit32_wait_end','batch32'),('wait_each','batch32')]:
 fields={}
 for field in ['total_wall_ms','thread_cpu_ms','process_cpu_ms']:
  values=[]
  for pair in range(3,12):
   rows={r['mode']:r for r in bench_records if r['pair']==pair};values.append(rows[first][field]/rows[second][field])
  numerator=bench['stats_ms'][first][field]['median'];denominator=bench['stats_ms'][second][field]['median']
  fields[field]={'paired_median_ratio':statistics.median(values),'ratio_of_medians':numerator/denominator,
                 'percent_reduction_of_medians':100*(1-denominator/numerator),'paired_min':min(values),'paired_max':max(values)}
 comparisons[first+'_over_'+second]=fields
fixtures=read(ROOT/'results/native-cas-semantic-qualification/policies.json')
combined={'branch':'A','qualified_native_shaders':4,'repaired_configurations':22,'repaired_captures':66,
 'repaired_logical_CAS_operations':old['logical_CAS_operations']+cas['repaired_logical_CAS_operations'],
 'general_compiler_patch':False,'Linux_backport':False,'transparent_application_integration':False,
 'scope':'Old minimal shader and three new AIR-aware shader shapes; same relaxed shared uint32 CAS profile, not generic CAS/Metal conformance.'}
head=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=ROOT,capture_output=True,text=True)
inputs=[]
for suite in ['native-cas-semantic-qualification','native-cas-variants-captured','submission-benchmark-three-modes','icb-contract-inspection','icb-gpu-encoding-pipeline']:
 for name in ['manifest.json','commands.json','results.json','independent-verification.json','summary.json','methods.json','static-provenance.json','noop-verification.json']:
  p=ROOT/'results'/suite/name
  if p.exists():inputs.append({'path':str(p),'sha256':sha(p)})
inputs.append({'path':str(ROOT/'results/icb-contract-inspection/static-recheck/verification.json'),
               'sha256':sha(ROOT/'results/icb-contract-inspection/static-recheck/verification.json')})
probe_children=[]
for suite in ['native-cas-semantic-qualification','submission-benchmark-three-modes','icb-contract-inspection','icb-gpu-encoding-pipeline']:
 for p in (ROOT/'results'/suite).rglob('manifest.json'):
  m=read(p)
  if 'signed_executable' not in m:continue
  assert not m['authoritative_ps_status'] and not m['SIGKILL_requested']
  status=subprocess.run(['ps','-o','stat=,command=','-p',str(m['pid'])],capture_output=True,text=True).stdout.strip()
  assert not status or m['signed_executable'] not in status, 'Own signed executable still present'
  probe_children.append({'pid':m['pid'],'exe':m['signed_executable'],'exit_code':m['exit_code'],'terminal_after_run':True,'current_ps':status})
src=Path(__file__).resolve();snapshot=OUT/src.name;snapshot.write_bytes(src.read_bytes())
provenance={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'objective':'Moderniser la pile NVIDIA native et étendre les fonctions Metal applicables; qualification ciblée actuelle, objectif global incomplet.',
 'Git':{'repository':str(LAB.parent),'branch':subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip(),
        'commit':head.stdout.strip() if head.returncode==0 else None,'unborn':head.returncode!=0,
        'local_changes':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)},
 'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),
 'hardware':subprocess.check_output(['sysctl','hw.model','hw.memsize','hw.physicalcpu','hw.logicalcpu','machdep.cpu.brand_string'],text=True).strip(),
 'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),'SDK':subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip(),
 'OpenNVDA_commit':'da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5','Mesa_version':'26.2.4','Mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2',
 'envytools_commit':'f102b82381f3f11cee113d16374c87091db039d9',
 'NAK_used_for_new_native_repairs':False,'native_shader_MSL':'macos-metal2.4','benchmark_MSL':'macos-metal2.0',
 'system_files_rechecked':len(system),'system_files':system,'rootpatch_sha256':sha(rootpatch),
 'rootpatch_metadata':{k:patch_info[k] for k in ['OpenCore Legacy Patcher','PatcherSupportPkg','Commit URL','Time Patched']},
 'native_driver_components':driver_components,
 'supplemental_MetalOld_SHA256':sha(metal_old),'original_reviewed_packet_unchanged':{'path':str(original_packet),'sha256':sha(original_packet)},
 'own_signed_children_checked':probe_children,'inputs':inputs,'report_generator_sha256':sha(snapshot),
 'Qwen_job_ids':[],'system_modifications':False}
dump(OUT/'provenance.json',provenance)
summary={'native_CAS_combined':combined,'new_semantic_CAS':{k:v for k,v in cas.items() if k!='results'},
 'three_mode_benchmark':bench,'comparisons':comparisons,
 'ICB':{'CPU_encoded':'BLOCKED','GPU_generated':'BLOCKED','frontend':'PASS','native_pipeline':compile_icb['native_pipeline'],
        'factory_internal_selector_missing':True,'inherited_compute_blit_noops':5,'backend_error':compile_icb['observation']['error'],
        'render_execution_inspected':False,'GPU_ICB_execution':'NOT RUN','hardware_inability_proved':False},
 'native_heaps_fences_events':'Existing capabilities preserved; no new implementation claimed.',
 'all_hardware_functions_supported':False,'Metal3_or_4_qualified':False,'system_modifications':False,'Qwen_job_ids':[]}
dump(OUT/'summary.json',summary)
coords=[]
for fixture in fixtures:
 if fixture['policy']['qualified']:
  m=fixture['policy']['SASS'];coords.append(f"{fixture['fixture']}: old r{m['old_register']} → expected r{m['expected_register']}, redirect {m['redirect_offset']:#x}, composante {m['expected_output_component']}, shared {m['shared_address']}.")
stats=bench['stats_ms'];v=lambda mode,field:stats[mode][field]['median'];iq=lambda mode,field:stats[mode][field]['IQR']
rows=[]
for mode in ['wait_each','submit32_wait_end','batch32']:
 rows.append(f"{mode:20} {v(mode,'total_wall_ms'):8.3f} ({iq(mode,'total_wall_ms'):.3f}) {v(mode,'process_cpu_ms'):8.3f} ({iq(mode,'process_cpu_ms'):.3f}) {v(mode,'thread_cpu_ms'):8.3f} ({iq(mode,'thread_cpu_ms'):.3f})")
report=f'''KEPLERMETAL — CAS SÉMANTIQUE ET CONTRAT ICB, 13 octobre 2026

Objectif: moderniser la pile NVIDIA existante (A) et étendre les fonctions Metal
applicables (B), jusqu’aux applications usuelles. Ce jalon reste L1, en solo.
Git: main sans commit, dépôt {LAB.parent}. Les sources exécutées sont figées
dans chaque cohorte et hashées. Job_ids Qwen: aucun. Aucun composant système
modifié; les 83 fichiers inventoriés, le plist rootpatch et MetalOld concordent.
L’archive précédente, SHA d217b82cf46c6285c884a921641928e16e5824b76ba1d4f770b74ba9637a7c04,
reste inchangée. La contre-vérification fournie n’était pas un nouveau test GPU.
Les résultats ci-dessous ont été exécutés/observés ici sur l’iMac.

1. Branche A: correction du code produit par le backend NVIDIA natif

Trois shaders supplémentaires, fabriqués puis compilés avec xcrun metal MSL2.4,
qualifiés sans NAK. Changement d’adresse partagée, allocation de registres et
permutation de la sortie. Reconnaissance AIR typée et SASS; données épinglées
source/AIR/metallib/original/remplacement avant import. L’import conserve aussi
le contrôle byte-exact du programme arrivant au constructeur NVIDIA.
{chr(10).join(coords)}

Le trampoline est assemblé après découverte des coordonnées. Un mot original
de 8 octets redirige vers un bloc ajouté de 64 octets. La membar déplacée est
rejouée; tous les autres mots originaux et leur scheduling restent identiques.
Le témoin NOP diffère du réparé par le seul mot MOV ajouté. Les metadata gardent
le profil ABI qualifié, GPR floor24/launch576, et la mémoire partagée originale.

Nouveaux essais: 33/128 threads, trois groupes, operands égaux ou différents,
trois graines par configuration; contention et exact old/bool/final/index.
12 configurations réparées, 36 captures, 8694 opérations CAS correctes.
24 configurations native/NOP échouent comme attendu, y compris losers sous
contention avec comparand égal: 17280 mots incorrects conservés. Aucun échec
réparé, aucune garde altérée. L’oracle indépendant vérifie un gagnant par groupe
pour cette boucle lock/unlock NVIDIA préservée; ce n’est pas une garantie
générale des opérations weak-CAS du langage.

Témoin sémantique valide: il garde volontairement le comparand initial au lieu
de publier expected après CAS. Son SASS832B est exactement celui du shader
minimal défectueux (ea09f179ff169422f6f3ac8c3b1f85f020c52f5853106e68becbb0f408ef85e3),
mais son AIR/metallib est distinct. Sans réparation: 2898 opérations correctes.
Le filtre refuse de le réparer. Trois autres refus: metallib différent,
policy absente et original-code différent. Quatre refus avant pipeline/dispatch.
Une signature SASS seule, un offset fixe ou un remplacement r0/r4 serait faux.

Ancien shader et nouveaux combinés: quatre shaders, 22 configurations,
66 captures et 30606 CAS corrects. L’ancien 1024 threads/groupe reste acquis;
les nouveaux shapes sont qualifiés à 33/128, pas à toutes les tailles/types.
Ces observations concernent les octets transmis au constructeur et les sorties
Private GPU relues par blit, pas un dump des instructions résidentes.
Ce correctif appartient à A24. Aucun correctif Linux transposé, aucun compilateur
installé réparé, aucune prise en charge automatique des apps usuelles. Les autres
Invalid Resource restent distincts. Aucun benchmark de débit CAS réalisé.

2. Branche B: ICB CPU et génération GPU, contrats distincts

La méthode publique newIndirectCommandBufferWithDescriptor:maxCommandCount:options:
est héritée de MTLIOAccelDevice dans MetalOld à offset 0xb5717. L’appel interne
maxCount manque dans NVMTLDevice. Les anciennes exceptions rendu/calcul restent
la preuve de refus de factory; aucun objet factice n’a été fabriqué.

UUID du MetalOld chargé = 6581cd53858338d1b4b9773f1dc3f551;
SHA sur disque = 73234b361cfce5c7095b518e6876e627b1e891cfb5964c6fe0067003d0e93d49.
Cinq IMP hérités concordent avec cette image et sont de vrais no-ops:
compute execute(range) 0x38805, execute(indirect range) 0x3880b;
blit reset 0x380db, copy 0x380e1, optimize 0x380e7.
Chacun: bytes 55 48 89 e5 5d c3, push rbp / mov rbp,rsp / pop rbp / ret.
Leur présence ne fournit pas l’exécution ICB. Render execution n’a pas été
inspectée séparément. Aucune de ces méthodes vides n’a été appelée avec un ICB.

ICB généré par GPU: le frontend MSL2.4 compile le shader render_command;
le chemin natif vers le pipeline refuse: Unsupported indirect argument kind
"air.command_buffer" (CompilerError 2), avant tout constructeur de programme
observé et sans dispatch. Le sous-stade library/function/pipeline exact n’est
pas distingué par l’observateur existant. Aucun ICB GPU exécuté.

Contrat CPU: objet/commandes réutilisables, héritage des états/buffers, résidence,
reset/copie/ranges, raccordement au command stream NVIDIA. Contrat GPU: tout cela
plus argument buffer contenant command_buffer, layout et lowering des commandes
et cohérence après écriture GPU. NAK seul ne fournit pas ces contrats.
Draw/dispatch indirect simple fonctionnels restent des primitives utiles,
sans preuve de support d’un véritable objet ICB. L’incapacité matérielle GK104
n’est pas démontrée par ces refus logiciels.
Références officielles, et copies hashées sous sources/icb-contract:
https://developer.apple.com/documentation/Metal/encoding-indirect-command-buffers-on-the-cpu
https://developer.apple.com/documentation/metal/encoding-indirect-command-buffers-on-the-gpu
Le SDK26.2 date rendu ICB de macOS10.14 et compute concurrent de macOS11;
les disponibilités du sample Apple actuel ne sont pas la date d’introduction.
Les fonctions natives heaps/alias/fences/events déjà qualifiées sont conservées.

3. Optimisation applicative: trois modes sur le même travail natif

32 couples producer/consumer, 32768 éléments, local128, buffers et pipelines
persistants. Le compteur GPU et 32 témoins d’étapes vérifient les 64 dispatchs
de chaque sample. Même résultat, graines et guards pour chaque triplet.
wait_each: 32 command buffers, attente après chacun.
submit32_wait_end: 32 buffers soumis sans attente intermédiaire, attente du
dernier à la fin sur la même queue; tous les 32 états Completed sont contrôlés.
batch32: un command buffer regroupé et une attente finale.
Trois triplets d’échauffement, neuf triplets retenus; ordre circulaire des modes.
2304 dispatchs totaux = 576 échauffements + 1728 retenus; 108 captures,
1181988 mots uint32 vérifiés, 13824 octets de garde intacts, 1152 témoins d’étapes.

                      Mural ms(IQR)      CPU process ms(IQR) CPU appelant ms(IQR)
{chr(10).join(rows)}

Le retrait des attentes intermédiaires réduit la médiane murale de
{comparisons['wait_each_over_submit32_wait_end']['total_wall_ms']['percent_reduction_of_medians']:.1f}% sur cette charge;
le regroupement réduit ensuite la médiane CPU processus de
{comparisons['submit32_wait_end_over_batch32']['process_cpu_ms']['percent_reduction_of_medians']:.1f}%.
Rapports appariés et rapports des médianes sont conservés séparément en JSON.
Les effets peuvent interagir; ce protocole ne répartit pas chaque cycle CPU
entre pilote, threads auxiliaires, scheduling et appels bloquants.
Upload et readback sont mesurés séparément, hors boucle affichée. Temps GPU
exclusif non qualifié. Gain applicatif sur cette charge, aucune version du
pilote changée et aucun gain d’inférence ou WindowServer déduit.
Ancien benchmark à deux modes: 1536 totaux = 384 warmups + 1152 retenus.
https://developer.apple.com/library/archive/documentation/3DDrawing/Conceptual/MTLBestPracticesGuide/CommandBuffers.html

4. Versions, commandes et prochaine action

macOS26.7.1/25G241; iMac11,1 i7-870, 32 Gio; GTX880M registryID4294968458.
GeForceMTLDriver et GeForceAIRPlugin: CFBundleVersion16.0.0, short16.0.12.
Pilote: GeForceMTLDriver SHA2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
Rootpatch: OCLP v3.0.0 / supportpkg v2.0.1, provenance release3.0.0-rc.2;
aucune modification et aucun gain déduit du numéro OCLP.
Clang17.0.0 clang-1700.6.4.2, SDKMacOSX26.2. Les shas/arguments exacts
figurent dans provenance.json et commands.json de chaque cohorte.
OpenNVDA da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5 (lecteur AIR);
Envytools f102b82381f3f11cee113d16374c87091db039d9 (assembleur/désassembleur SM30).
Mesa26.2.4 96cb43121031992b85767f9c1be8f3f48e22b1d2 est une référence antérieure;
NAK n’a pas produit les trois réparations natives nouvelles.

Depuis le bridge, lire les preuves existantes sans aucun dispatch:
python3 tools/verify_semantic_cas_repair.py --input results/native-cas-semantic-qualification
python3 results/submission-benchmark-three-modes/verify_submission_benchmark.py --input results/submission-benchmark-three-modes
python3 tools/audit_icb_handlers.py --inspection results/icb-contract-inspection --out results/icb-static-reproduction-NEW

Reproduire avec le workspace et ses dépendances épinglées, répertoires frais:
python3 tools/prepare_native_cas_variants.py --out results/cas-fixtures-NEW
python3 tools/reproduce_semantic_cas_repair.py --fixtures results/cas-fixtures-NEW --out results/cas-qualification-NEW
python3 tools/verify_semantic_cas_repair.py --input results/cas-qualification-NEW
python3 tools/reproduce_submission_benchmark.py --library-input results/resource-sync-initial --modes 3 --out results/submission-three-NEW
python3 tools/verify_submission_benchmark.py --input results/submission-three-NEW
python3 tools/reproduce_icb_gpu_compile.py --out results/icb-pipeline-NEW
Chaque script refuse d’écraser les observations existantes; les children sont
signés en copie et surveillés, sans réessai s’ils restent présents.

Prochaine action A: extraire/associer l’AIR exact des metallibs, étendre le filtre
aux données de flot/alias/ABI et shaders supplémentaires; refuser si l’intention
reste ambiguë. Ensuite intégration L2 dans un client distinct avant toute L3.
Prochaine action B: tracer statiquement les primitives d’indirect NVIDIA déjà
fonctionnelles et leur command stream; établir un contrat minimal ICB CPU avec
réutilisation/résidence. Génération GPU nécessite aussi ABI/compiler command_buffer.
Aucun retour d’objet vide, capability spoof ou nouveau framework système.
Recherche des évolutions Linux: chantier distinct maintenu, aucun port appliqué.

Tests PASS: réparations/intent-control/gates, oracles et guards, benchmark trois
modes, identité UUID et no-ops, 83 empreintes système et archive précédente.
Tests FAIL conservés: 24 configurations native/NOP (défauts attendus), anciens
contrôles CAS et sans producteur. BLOCKED: ICB actuel factory/exécution/backend.
NOT RUN: ICB GPU, conformité CAS générale, intégration L2/L3, gain pilote global.
Le support de tout le matériel et Metal3/4 reste incomplet; ce n’est pas un
pilote global modernisé. Aucun fichier système/OCLP, kext, firmware ou registre
GPU n’a été modifié.
'''
(OUT/'RAPPORT.txt').write_text(report);(ROOT/'CAS_SEMANTIQUE_ICB.txt').write_text(report)
coverage_path=ROOT/'results/hardware-coverage.json';coverage=read(coverage_path)
for row in coverage['coverage']:
 if row['category']=='Pinned native shared-CAS shader correction':
  row['tested_scope']='Four native shaders: 22 repaired configurations, 66 captures, 30606 correct CAS. Three new AIR-aware shapes, dynamic registers/offsets, 8694 operations; valid SASS-colliding intention control passes without repair, rejected before replacement.'
  row['remaining_requirements']='General conservative AIR/control-flow/alias/ABI recognition, other types/scopes/progression and supported L2/L3 integration. SASS-only repair explicitly forbidden; installed native compiler unchanged and other Invalid Resource unresolved.'
  row['evidence'] += ['results/native-cas-semantic-qualification/independent-verification.json']
 if row['category']=='Native ICB factory/runtime boundary':
  row['tested_scope']='Render/compute factory internal selector missing; five inherited compute/blit execution/reset/copy/optimize methods are six-byte no-ops, UUID-matched. GPU ICB MSL frontend accepts, native backend refuses air.command_buffer before constructor/dispatch.'
  row['remaining_requirements']='Real CPU ICB objects, encoding/execution/lifetimes/resource residency; GPU-generated commands additionally require command-buffer ABI/layout/lowering. No hardware inability proved; no ICB execution qualified.'
  row['evidence'] += ['results/icb-contract-inspection/static-recheck/verification.json','results/icb-gpu-encoding-pipeline/summary.json']
 if row['category']=='Native application CPU submission cost':
  row['tested_scope']='Three modes on identical persistent native workload: 32 wait-each CB, 32 CB/one final wait, one grouped CB/one wait. Three warmup triplets + nine measured, 2304 total/1728 measured GPU dispatches, 1152 step witnesses and all raw results/guards correct.'
  row['evidence'] += ['results/submission-benchmark-three-modes/summary.json']
coverage['complete']=False;dump(coverage_path,coverage)
delivery={'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in [OUT/'summary.json',OUT/'provenance.json',OUT/'RAPPORT.txt',ROOT/'CAS_SEMANTIQUE_ICB.txt',coverage_path]],
          'system_files_unchanged':83,'all_hardware_functions_supported':False}
dump(OUT/'delivery.json',delivery);print(json.dumps(delivery,ensure_ascii=False,indent=2))

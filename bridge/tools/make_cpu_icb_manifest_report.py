#!/usr/bin/env python3
"""Reconcile manifest registration and dynamic shared-memory evidence, no GPU calls."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-manifest-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
protocol=read(ROOT/'results/cpu-icb-manifest-resize-gpu-qualified/independent-verification.json');life=read(ROOT/'results/cpu-icb-manifest-lifetime-gpu-qualified/independent-verification.json');regression=read(ROOT/'results/cpu-icb-manifest-regression-profiles-gpu-qualified/independent-verification.json')
assert protocol['status']==life['status']==regression['status']=='PASS' and protocol['user_GPU_invocations']==5496 and protocol['correct_uint32_words']==21984 and life['GPU_user_invocations']==594 and life['correct_uint32_words']==2376 and regression['user_GPU_invocations']==4725
cohorts=['native-manifest-pipeline-captured','native-manifest-pipeline-variable-captured','cpu-icb-manifest-legacy-profiles-prepared','cpu-icb-manifest-prepared','cpu-icb-manifest-full-parameters-prepared','cpu-icb-manifest-cached-bound-prepared','cpu-icb-manifest-gpu-qualified','cpu-icb-manifest-resize-prepared','cpu-icb-manifest-resize-gpu-qualified','cpu-icb-manifest-lifetime-prepared','cpu-icb-manifest-lifetime-gpu-qualified','cpu-icb-manifest-regression-profiles-prepared','cpu-icb-manifest-regression-profiles-gpu-qualified'];history=[]
ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for cohort in cohorts:
 f=ROOT/'results'/cohort;m=read(f/'execution/manifest.json');assert not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert not any(m['signed_executable'] in line or m['original_executable'] in line for line in ps.splitlines());history.append({'cohort':cohort,'pid':m['pid'],'exit_code':m['exit_code'],'terminal':True,'qualification':'FAIL_PRESERVED' if m['exit_code'] else 'PASS','source_hashes':read(f/'inputs.json')['source_hashes']})
assert [x['exit_code'] for x in history]==[-6,0,0,-6,0,0,0,0,0,0,0,0,0]
history[0]['note']='Read-only capture assumed464B for dynamic kernel; actual496B. Early return left encoder open and triggered dealloc assertion. No command buffer committed. Variable capture fixed.'
history[3]['note']='Client copied16 instead of20 bytes of the new parameter struct; shared bound guard rejected sentinel word before user kernel. Early error return then triggered open-encoder dealloc assertion. Struct copy and error cleanup fixed.'
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for e in baseline['system_files']:
 actual=sha(Path(e['path']));assert actual==e['sha256'];checked.append({'path':e['path'],'sha256':actual})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256']
for cohort in ['cpu-icb-manifest-resize-gpu-qualified','cpu-icb-manifest-lifetime-gpu-qualified','cpu-icb-manifest-regression-profiles-gpu-qualified']:
 for name,h in read(ROOT/'results'/cohort/'inputs.json')['source_hashes'].items():
  folder='src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/name)==h
sources=['src/KeplerCPUICB.h','src/KeplerCPUICB.mm','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/cpu_icb_manifest.metal','src/cpu_icb_manifest.json','tools/cpu_icb_manifest_probe.mm','tools/cpu_icb_manifest_lifetime_probe.mm','tools/reproduce_cpu_icb_manifest.py','tools/reproduce_cpu_icb_manifest_lifetime.py','tools/verify_cpu_icb_manifest.py','tools/verify_cpu_icb_manifest_v1.py','tools/verify_cpu_icb_manifest_lifetime.py','tools/make_cpu_icb_manifest_report.py','tools/decode_native_commands.py','tools/run_signed_probe.py']
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN; lab untracked; exact frozen sources by SHA256','integration_level':1,'manifest_registration_no_fixed_function_names':True,'registration_is_GPU_qualification':False,'buffer_ABI_scope':'uint4 output0, atomic counter1, CPU-readable constant struct2; optional uint threadgroup0','new_GPU_programs_qualified':2,'protocol_GPU_submissions':9,'protocol_GPU_invocations':5496,'protocol_correct_uint32_words':21984,'lifetime_GPU_submissions':2,'lifetime_GPU_invocations':594,'lifetime_correct_uint32_words':2376,'combined_latest_GPU_invocations':6090,'combined_latest_correct_uint32_words':24360,'regression_previous_three_programs_invocations':4725,'regression_previous_three_programs_correct_uint32_words':18900,'dynamic_threadgroup_bytes_qualified':[1024,32768,49152],'same_command_resize_1024_to49152':True,'cached_and_copied_invalid_length_bounds_rejected_before_submission':True,'API_rejections':13,'raw_protocol_files_checked':153,'guard_mismatches':0,'class_cache_reinstall_cycles':3,'native_shader_code_patched':False,'ICB_contract_complete':False,'GPU_resident_command_indirection':False,'GPU_generated_ICB':False,'performance_benchmark':False,'all_children_terminal':True,'system_modified':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'library_SHA256':'ed7854542c2a45533f0114fd7e1100f31f52728433f83667b5d9cd54568cea94','manifest_SHA256':'1b3733508f756bd28ba849a65d066cc371c458b966197896962f2f5a2ab79685','Qwen_job_ids':[],'Qwen_status':'No verified transfer/current source tree on MrWhite. No review submitted; coordinator task retained, solo continuation authorised.'}
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history)
provenance={'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'inputs':[{'path':str(ROOT/p),'sha256':sha(ROOT/p)} for p in sources],'system_files':checked,'rootpatch_sha256':sha(rootpatch),'system_modified':False,'sources':['https://docs.nvidia.com/cuda/archive/10.2/cuda-c-programming-guide/index.html#features-and-technical-specifications','https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/setthreadgroupmemorylength(_:at:)'],'Qwen_job_ids':[]};dump(OUT/'provenance.json',provenance)
coverage=read(ROOT/'results/hardware-coverage.json');assert not coverage['complete']
for row in coverage['coverage']:
 if row['category']=='CPU-recorded compute ICB selectors and bounded resource lifetime':
  row['tested_scope']='Latest manifest-driven native library registration (no fixed names/hash inside generic module), reflected 3-buffer ABI + optional threadgroup0. Nine CPU-ICB user CB submissions:5496invocations/21984uint32; two lifetime CBs594/2376. Dynamic1/32/48KiB and same-command1→48KiB resizing; cached and copied parameter bound mismatch rejected before submission;13API controls, guards intact. Raw464B/9packets and496B/12packets, original QMD metadata preserved. Previous three native programs regression4725/18900; no native shader-code modification.'
  row['remaining_requirements']='ABI beyond fixed output/counter/constants and one dynamic pointer; static+dynamic combinations/nonzero LDS pointer base, other lengths/indices, inherited states, nonuniform/2D/3D grids, rendering, GPU-timeline blits, indirect range/resourceID/GPU generation, concurrent mutation/residency/pressure/benchmarks and integration L2/L3. Registration alone does not qualify GPU correctness.'
  for item in ['results/cpu-icb-manifest-progress/summary.json','results/cpu-icb-manifest-resize-gpu-qualified/independent-verification.json','results/cpu-icb-manifest-lifetime-gpu-qualified/independent-verification.json','results/cpu-icb-manifest-regression-profiles-gpu-qualified/independent-verification.json','CPU_ICB_MANIFESTE_MEMOIRE_DYNAMIQUE.txt']:
   if item not in row['evidence']:row['evidence'].append(item)
dump(ROOT/'results/hardware-coverage.json',coverage);dump(RESEARCH/'inventory/hardware-coverage.json',coverage);dump(RESEARCH/'inventory/evidence-summaries/hardware-coverage.json',coverage)
report=f'''KEPLERMETAL — ENREGISTREMENT NATIF PAR MANIFESTE ET MÉMOIRE PARTAGÉE DYNAMIQUE

La bibliothèque et le manifeste JSON sont vérifiés par leurs SHA256. Le module
générique crée les MTLFunctions/PSO, vérifie la réflexion et leur identité réelle.
Il ne contient plus de noms ou de hash de bibliothèque imposés pour ce chemin.
Le manifeste décrit trois buffers et, facultativement, le pointeur threadgroup0,
les limites de groupe, la mémoire statique et le nombre de registres QMD capturé.
Ce contrat demeure borné: enregistrer une fonction ne prouve pas son calcul GPU.

Nouveaux programmes natifs: rotation entière et réduction sur mémoire dynamique.
Neuf soumissions GPU du protocole:5496invocations,21984mots corrects, gardes intactes.
Deux soumissions du client de lifetime:594invocations,2376mots corrects après release
de l’ICB/scope; bindings/pipelines conservés, readback avant completion. Contrôle
unretained libéré et jamais soumis. Total de ces deux qualifications:6090/24360.
Non-régression distincte des trois programmes précédents:4725/18900 sur huit CB.
Ces volumes ne sont pas un benchmark ou un pourcentage de couverture matérielle.

Mémoire dynamique1/32/48Kio: chaque groupe remplit toute la région, puis chaque lane
réduit ses mots après barrière. Les sommes modulo32bits et la géométrie concordent
avec le CPU. Ce sont des réductions vérifiées, pas une capture brute de chaque mot
de shared memory. Changement1→48Kio du même objet commande fonctionnel; le nouvel
état invalide le record, tout en conservant le programme natif et ses registres.
La copie CPU conserve son ancien état mais partage les buffers liés comme prévu;
une borne devenue incompatible est refusée avant tout dispatch utilisateur.

Treize contrôles refusés: identité library/manifest, réflexion altérée, fonctions
dupliquées/absentes, PSO étranger à label usurpé, tailles partagées, indices/ranges
ICB, resourceID, grilles non uniformes, héritage, bornes dynamiques cached/copied.
153 fichiers bruts du protocole relus; les contrôles avant commit montrent les
compteurs zéro/sentinelles inchangées. Caches de classes réutilisés trois cycles.

Format natif observé:464B/9paquets pour le kernel sans pointeur partagé;
496B/12paquets pour le kernel dynamique. Le préambule supplémentaire transfère
4octets de valeur0 vers le backing CB1+0x640; sa destination est relocalisée vers
le backing dédié, comme le reste des constantes/QMD. Attribution au pointeur
threadgroup0 cohérente avec l’ABI et les tests, mais pas désassemblage complet du
compilateur. QMDshared1/32/48Kio, GPR7/8; programmes distincts et stables à reuse.
Shaders NVIDIA natifs inchangés; aucun code NAK ou nouvelle famille Metal requise.

Branche B: état CPU ICB supplémentaire utilisable dans notre scope L1.
Branche A: cette étape ne transpose aucun correctif Linux et ne modernise pas le
pilote installé. MacOS/OCLP/frameworks/kexts/firmware/clocks sont inchangés.
83 fichiers système et plist de patch OCLP rehashés identiques. Enfants terminés.
Aucun gain mesuré ou annoncé. ICB GPU-résident/généré, rendu, héritage, autres ABI,
static+dynamic/nonzero LDS base, grilles/ranges indirects, mutations concurrentes,
gestion de pression et intégration transparente aux applications restent ouverts.

Références et reproduction
Git main UNBORN, aucun commit; sources non suivies, références SHA256 figées.
Library:ed7854542c2a45533f0114fd7e1100f31f52728433f83667b5d9cd54568cea94
Manifest:1b3733508f756bd28ba849a65d066cc371c458b966197896962f2f5a2ab79685
GeForceMTLDriver:2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Sources/exécutables signés, versions macOS/clang/SDK et toutes les commandes:
results/cpu-icb-manifest-progress/provenance.json et chaque inputs.json,
commands.json, execution/manifest.json. Bibliothèque copiée de la capture CPU
native-manifest-pipeline-variable-captured, pas recompilée à chaque test.
Référence QMD NVIDIA/open-gpu-doc:4de9b1af2ebcf610d8201af4ad07f7f2fb83b0f8.
Decoder Envytools:f102b82381f3f11cee113d16374c87091db039d9.
Référence limite SM30 GPR63/shared48Kio:CUDA10.2.89 Programming Guide table15,
https://docs.nvidia.com/cuda/archive/10.2/cuda-c-programming-guide/index.html
API: https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/setthreadgroupmemorylength(_:at:)

Depuis {ROOT}, choisir des dossiers nouveaux:
python3 tools/reproduce_cpu_icb_manifest.py --out results/NOUVEAU-prepare
python3 tools/verify_cpu_icb_manifest.py --input results/NOUVEAU-prepare --check-current-sources
Après PASS seulement:
python3 tools/reproduce_cpu_icb_manifest.py --out results/NOUVEAU-gpu --execute
python3 tools/verify_cpu_icb_manifest.py --input results/NOUVEAU-gpu --check-current-sources
Même séquence avec reproduce_cpu_icb_manifest_lifetime.py/verify_cpu_icb_manifest_lifetime.py.
verify_cpu_icb_manifest_v1.py conserve l’oracle exact du premier protocole huit CB,
SHA82c344dd3fb284fd206f09e1ed9fe132fe52633ffa7be161e957ad1a3535bca2.

Deux échecs initiaux conservés: capture supposant464B alors que496B; copie hôte de
16au lieu de20octets de paramètres, refusée par la garde avant kernel utilisateur.
Dans ces deux processus, l’encoder ouvert a ensuite provoqué SIGABRT à dealloc.
Nettoyage de l’encoder corrigé pour l’erreur d’encodage et format capturé. Aucune
soumission de kernel utilisateur dans ces échecs; aucune panne GPU déduite.

Qwen: accès/authentification/coordination établis, tâche T-20261013-230031-fe3487.
job_ids=[]; revue NOT RUN faute de copie actuelle vérifiée sur MrWhite. Pas de
repli cloud ni doublon de mission; continuation solo autorisée et exécutée.
Objectif complet toujours actif. Prochaine étape: élargir les ABI/bindings et
états des ICB CPU puis rendu/format GPU/compiler séparés; API familiale non falsifiée.
'''
(ROOT/'CPU_ICB_MANIFESTE_MEMOIRE_DYNAMIQUE.txt').write_text(report);print(json.dumps(summary,indent=2))

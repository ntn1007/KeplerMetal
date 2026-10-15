#!/usr/bin/env python3
"""Reconcile immutable imports and buffer ABI evidence, without GPU execution."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-buffers-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
protocol=read(ROOT/'results/cpu-icb-buffers-range-gpu-qualified/independent-verification.json');life=read(ROOT/'results/cpu-icb-buffers-lifetime-gpu-qualified/independent-verification.json');dynamic=read(ROOT/'results/cpu-icb-buffers-dynamic-regression-gpu-qualified/independent-verification.json');legacy=read(ROOT/'results/cpu-icb-buffers-legacy-regression-gpu-qualified/independent-verification.json')
assert all(x['status']=='PASS' for x in [protocol,life,dynamic,legacy]);assert protocol['correct_float32_values']==919040 and life['correct_float32_values']==65536 and dynamic['user_GPU_invocations']==5496 and legacy['user_GPU_invocations']==4725
cohorts=['native-buffer-pipeline-captured','cpu-icb-buffers-prepared','cpu-icb-buffers-immutable-prepared','cpu-icb-buffers-gpu-qualified','cpu-icb-buffers-range-prepared','cpu-icb-buffers-range-gpu-qualified','cpu-icb-buffers-lifetime-prepared','cpu-icb-buffers-lifetime-gpu-qualified','cpu-icb-buffers-dynamic-regression-prepared','cpu-icb-buffers-dynamic-regression-gpu-qualified','cpu-icb-buffers-legacy-regression-prepared','cpu-icb-buffers-legacy-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for cohort in cohorts:
 f=ROOT/'results'/cohort;m=read(f/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert not any(m['signed_executable'] in l or m['original_executable'] in l for l in ps.splitlines());history.append({'cohort':cohort,'pid':m['pid'],'exit_code':0,'terminal':True,'source_hashes':read(f/'inputs.json')['source_hashes']})
for cohort in ['cpu-icb-buffers-range-gpu-qualified','cpu-icb-buffers-lifetime-gpu-qualified','cpu-icb-buffers-dynamic-regression-gpu-qualified','cpu-icb-buffers-legacy-regression-gpu-qualified']:
 for name,h in read(ROOT/'results'/cohort/'inputs.json')['source_hashes'].items():
  folder='src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/name)==h
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for e in baseline['system_files']:
 actual=sha(Path(e['path']));assert actual==e['sha256'];checked.append({'path':e['path'],'sha256':actual})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256']
sources=['src/KeplerCPUICB.h','src/KeplerCPUICB.mm','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/cpu_icb_buffers.metal','src/cpu_icb_buffers.json','tools/cpu_icb_buffers_probe.mm','tools/cpu_icb_buffers_lifetime_probe.mm','tools/reproduce_cpu_icb_buffers.py','tools/reproduce_cpu_icb_buffers_lifetime.py','tools/verify_cpu_icb_buffers.py','tools/verify_cpu_icb_buffers_v1.py','tools/verify_cpu_icb_buffers_lifetime.py','tools/make_cpu_icb_buffers_report.py','tools/decode_native_commands.py','tools/run_signed_probe.py']
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN, lab untracked, frozen SHA snapshots','integration_level':1,'library_loaded_from_verified_immutable_bytes':True,'caller_mutation_and_deleted_source_controls':True,'manifest_schema2_buffer_registration':True,'tested_buffers':4,'registered_index_range':[0,15],'registration_is_GPU_qualification':False,'vector_counts_qualified':[128,8192,65536],'source_offsets_qualified':{'output':[128,256],'a':[64,128],'b':[256,512],'constant':[256,512]},'GPU_user_submissions':4,'processed_float4_elements':229760,'correct_float32_values':919040,'lifetime_GPU_user_submissions':2,'lifetime_processed_float4_elements':16384,'lifetime_correct_float32_values':65536,'combined_latest_float4_elements':246144,'combined_latest_float32_values':984576,'read_only_inputs_byte_identical':True,'guard_mismatches':0,'rejected_buffer_controls':4,'dynamic_regression_GPU_invocations':5496,'dynamic_regression_correct_uint32_words':21984,'three_program_regression_GPU_invocations':4725,'three_program_regression_correct_uint32_words':18900,'native_register_count':14,'ICB_contract_complete':False,'GPU_generated_ICB':False,'GPU_resident_command_indirection':False,'native_shader_code_patched':False,'performance_benchmark':False,'all_children_terminal':True,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'library_SHA256':'ba0f51c96f993240f9637f0b848e14a5362e125d9c5cdf2aa38efd518531a8fd','manifest_SHA256':'0c5f52ae67fdc53da8b9d43544b88173f67c4bdbe69e15797432315f6a55ca66','Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; central current source copy not verified. Solo fallback authorised.'}
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history)
provenance={'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'inputs':[{'path':str(ROOT/p),'sha256':sha(ROOT/p)} for p in sources],'system_files':checked,'rootpatch_sha256':sha(rootpatch),'system_modified':False,'Qwen_job_ids':[]};dump(OUT/'provenance.json',provenance)
coverage=read(ROOT/'results/hardware-coverage.json');assert not coverage['complete']
for r in coverage['coverage']:
 if r['category']=='CPU-recorded compute ICB selectors and bounded resource lifetime':
  r['tested_scope']='Latest: immutable SHA-verified native library data passed to Metal directly; caller data wiped/source copy deleted before materialization. Schema2 removes output/counter/constants3 toy ABI: four reflected buffers in AXPY, variable lengths and offsets,128/8192/65536float4 per command. Four submissions229760vectors/919040float32 plus two after caller release16384/65536; readonly inputs/guards preserved. Native CB1 four pointers and CB2 remaining1280/1024 bytes verified,14GPR metadata unchanged. Undersized/unaligned/unknown-index/oversized-grid rejected. Dynamic1/32/48KiB regression5496/21984 and previous3programs4725/18900.'
  r['remaining_requirements']='Registered indices0..15 are an interface bound, only0..3 qualified here. Other types/indices/resource address spaces, multi-constant/argument-buffer/texture ABI, inherited state,2D/3D/nonuniform grids, static+dynamic combinations, rendering, GPU timeline operations, GPU-resident/generation, concurrency/pressure/benchmarks and L2/L3 remain open.'
  for e in ['results/cpu-icb-buffers-progress/summary.json','results/cpu-icb-buffers-range-gpu-qualified/independent-verification.json','results/cpu-icb-buffers-lifetime-gpu-qualified/independent-verification.json','CPU_ICB_BUFFERS_IMPORT_IMMUABLE.txt']:
   if e not in r['evidence']:r['evidence'].append(e)
dump(ROOT/'results/hardware-coverage.json',coverage);dump(RESEARCH/'inventory/hardware-coverage.json',coverage);dump(RESEARCH/'inventory/evidence-summaries/hardware-coverage.json',coverage)
report=f'''KEPLERMETAL — IMPORT IMMUABLE ET BUFFERS PLUS GÉNÉRAUX

Le loader lit/cop ie les bytes de library et manifest, vérifie leur SHA puis
passe le même snapshot immuable à newLibraryWithData. Les loaders URL délèguent
au chemin mémoire; aucune seconde ouverture du fichier après sa vérification.
Le client relit une copie temporaire puis la supprime avant l’import, et détruit
ses NSData mutables après installation mais avant toute matérialisation/exécution.
Les fixtures originales restent intactes pour reproduction. Sources et SHA du
processus signé attestés; contrôle numérique indépendant de l’observateur.

Schema2 décrit les arguments par index, taille/alignment/type/access et bornes.
Il retire l’obligation du triplet uint4-out/compteur/constant2 dans ce chemin.
Le kernel natif AXPY utilise quatre buffers: sortie float4, deux entrées readonly,
constant3. Allocations variables:128,8192,65536vecteurs par commande. Offset
sortie128→256, entrée A64→128, entrée B256→512, constants256→512. Deux anciennes
séquences de commandes restent réutilisables; rebind invalide le record concerné.

Quatre CB utilisateur:229760float4 traités,919040valeurs float32 correctes;
entrées relues identiques byte-à-byte et toutes les gardes/sentinelles intactes.
Deux autres soumissions après libération ICB/scope:16384float4/65536valeurs, trois
buffers Private encore vivants jusqu’à completion; readback avant libération.
Le contrôle unretained constate les Private libérés, sans jamais soumettre ce CB.
Total des deux qualifications:246144vecteurs et984576valeurs. Pas de compteur
atomique dans ce nouveau programme: compter les vecteurs vérifiés ne constitue
pas un compteur indépendant d’invocations GPU. Les captures LAUNCH/QMD et sorties
Private relues par blit soutiennent l’exécution GPU des workloads enregistrés.

CPU oracle: données exactes entières/demi-entières, scales2 et-1, fma vectorielle
native; aucune généralisation NaN/denorm/FP64/précision flottante complète.
Quatre refus avant submission: index non enregistré, offset non aligné, grille
au-delà du contrat, buffer trop petit. Ce dernier laisse les sorties intactes.
Le binding réel CB1 index*32+8 correspond aux quatre addresses+offsets; QMD_CB2
pointe sur constant3+offset et sa taille1280/1024 reflète le reste du buffer.
14GPR natifs, programme/metadata préservés,464B/9paquets. Aucun shader-code patché.

Non-régression avec le module courant: shared dynamique1/32/48Kio, resize/reuse,
5496invocations/21984uint32; anciens entier/FMA/shared512B,4725/18900. Les mêmes
oracles relisent les sources figées et les résultats avec --check-current-sources.
Toutes les observations de cette étape ont exit0; aucun enfant en cours/SIGKILL.
83 fichiers système et plist rootpatch OCLP rehashés inchangés.

Branche B/L1: extension de l’interface CPU ICB en réutilisant le backend natif.
Enregistrer une ABI ne qualifie pas n’importe quel shader. Interface index0..15,
seuls0..3 testés ici. Textures/argument buffers/multi-constant, états hérités,
grilles2D/3D/nonuniformes, rendu et GPU-resident/génération/timeline restent ouverts.
Concurrence/pression, contrats complets et intégration L2/L3 non établis.
Branche A: aucun port Linux ni modification du pilote installé dans cette étape.
Aucun benchmark, aucun gain CPU/GPU annoncé. Objectif complet toujours actif.

Versions et reproduction
Git main UNBORN: aucun commit, sources non suivies référencées par snapshots SHA.
GeForceMTLDriver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Library ba0f51c96f993240f9637f0b848e14a5362e125d9c5cdf2aa38efd518531a8fd
Manifest0c5f52ae67fdc53da8b9d43544b88173f67c4bdbe69e15797432315f6a55ca66
macOS/clang/SDK/sources: results/cpu-icb-buffers-progress/provenance.json.
Commandes exactes, sources/binaries signés, durées/exit: chaque inputs.json,
commands.json, execution/manifest.json. NVIDIA QMD header commit
4de9b1af2ebcf610d8201af4ad07f7f2fb83b0f8 et decoder Envytools
f102b82381f3f11cee113d16374c87091db039d9, références conservées.
SDK26.2 MTLDevice.h newLibraryWithData: et MTLDataTypeFloat4=6 vérifiés.
https://developer.apple.com/documentation/metal/mtldevice/makelibrary(data:)

Depuis {ROOT}, nouveaux dossiers:
python3 tools/reproduce_cpu_icb_buffers.py --out results/NOUVEAU-prepare
python3 tools/verify_cpu_icb_buffers.py --input results/NOUVEAU-prepare --check-current-sources
Après PASS:
python3 tools/reproduce_cpu_icb_buffers.py --out results/NOUVEAU-gpu --execute
python3 tools/verify_cpu_icb_buffers.py --input results/NOUVEAU-gpu --check-current-sources
Même séquence buffers_lifetime avec reproduce_cpu_icb_buffers_lifetime.py et
verify_cpu_icb_buffers_lifetime.py. Metallib figée copiée de
results/native-buffer-pipeline-captured, pas recompilée à chaque essai.

Qwen job_ids=[]; review NOT RUN, copie source centrale non vérifiée. Solo autorisé.
Tâche coord T-20261013-230031-fe3487. Prochaine action: étendre les états/grilles et
le chemin rendu CPU ICB, en conservant les validations acquises; benchmarks séparés.
'''.replace('cop ie','copie')
(ROOT/'CPU_ICB_BUFFERS_IMPORT_IMMUABLE.txt').write_text(report);print(json.dumps(summary,indent=2))

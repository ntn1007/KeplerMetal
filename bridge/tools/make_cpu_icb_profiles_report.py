#!/usr/bin/env python3
"""Reconcile native multi-program ICB evidence; never runs GPU work."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-profiles-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
protocol=read(ROOT/'results/cpu-icb-profiles-gpu-qualified/independent-verification.json');life=read(ROOT/'results/cpu-icb-profiles-lifetime-gpu-qualified/independent-verification.json')
assert protocol['status']==life['status']=='PASS' and protocol['user_GPU_invocations']==4725 and protocol['correct_uint32_words']==18900 and life['GPU_user_invocations']==594 and life['correct_uint32_words']==2376
assert protocol['host_executable_SHA256_rechecked'] and life['host_executable_SHA256_rechecked']
cohorts=['native-pipeline-profiles-captured','native-pipeline-profiles-vector-captured','cpu-icb-registered-legacy-prepared','cpu-icb-registered-legacy-gpu-qualified','cpu-icb-profiles-prepared','cpu-icb-profiles-label-descriptor-prepared','cpu-icb-profiles-reflection-access-prepared','cpu-icb-profiles-gpu-qualified','cpu-icb-profiles-lifetime-prepared','cpu-icb-profiles-lifetime-private-buffers-prepared','cpu-icb-profiles-lifetime-gpu-qualified']
ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True);history=[]
notes={'native-pipeline-profiles-captured':'Shader compilation refused scalar lane builtin; fixed uint3 lane3. No child or submission.','cpu-icb-profiles-prepared':'Host compilation refused assigning readonly pipeline.label; label moved to descriptor. No child or submission.','cpu-icb-profiles-label-descriptor-prepared':'Exit4 before GPU preparation: our reflection access guard used WriteOnly(enum2) instead of observed ReadWrite(enum1). SDK enum checked and guard corrected.','cpu-icb-profiles-lifetime-prepared':'Host compilation used C++ keyword private as variable; renamed privateBuffers. No child or submission.'}
for name in cohorts:
 f=ROOT/'results'/name;commands=read(f/'commands.json');manifest=f/'execution/manifest.json';row={'cohort':name,'commands':commands,'qualification':'FAIL_PRESERVED' if name in notes else 'PASS','note':notes.get(name,'')}
 if manifest.exists():
  m=read(manifest);assert not m['authoritative_ps_status'] and not m['SIGKILL_requested'];assert not any(m['signed_executable'] in line or m['original_executable'] in line for line in ps.splitlines());row.update(pid=m['pid'],exit_code=m['exit_code'],terminal=True)
 else:row.update(exit_code=commands[-1]['exit_code'],child_started=False,terminal=True)
 history.append(row)
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for e in baseline['system_files']:
 actual=sha(Path(e['path']));assert actual==e['sha256'];checked.append({'path':e['path'],'sha256':actual})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256']
sources=['src/KeplerCPUICB.h','src/KeplerCPUICB.mm','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/cpu_icb_profiles.metal','tools/cpu_icb_profiles_probe.mm','tools/cpu_icb_profiles_lifetime_probe.mm','tools/reproduce_cpu_icb_profiles.py','tools/reproduce_cpu_icb_profiles_lifetime.py','tools/verify_cpu_icb_profiles.py','tools/verify_cpu_icb_profiles_lifetime.py','tools/decode_native_commands.py','tools/run_signed_probe.py','tools/make_cpu_icb_profiles_report.py','results/pipeline-profile-references/cla0c0qmd.h']
for cohort in ['cpu-icb-profiles-gpu-qualified','cpu-icb-profiles-lifetime-gpu-qualified']:
 inp=read(ROOT/'results'/cohort/'inputs.json')
 for name,h in inp['source_hashes'].items():
  folder='src' if name.startswith('Kepler') or name.endswith('.metal') else 'tools';assert sha(ROOT/folder/name)==h
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN; lab untracked, exact source snapshots by SHA256','integration_level':1,'registered_native_programs':3,'protocol_GPU_submissions':8,'protocol_GPU_invocations':4725,'protocol_correct_uint32_words':18900,'lifetime_GPU_submissions':2,'lifetime_GPU_invocations':594,'lifetime_correct_uint32_words':2376,'combined_GPU_invocations':5319,'combined_correct_uint32_words':21276,'guard_mismatches':0,'API_rejections':7,'class_cache_reinstall_cycles':3,'raw_packet_program_and_QMD_checks':True,'CPU_ICB_public_selector_subset':True,'ICB_contract_complete':False,'GPU_generated_ICB':False,'GPU_resident_command_indirection':False,'native_GPU_code_patched':False,'library_SHA256':'913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd','NVIDIA_QMD_header_commit':'4de9b1af2ebcf610d8201af4ad07f7f2fb83b0f8','performance_benchmark':False,'all_children_terminal':True,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'Qwen_authenticated_workers':['qwen-local','qwen-mac-coder'],'Qwen_coord_task':'T-20261013-230031-fe3487','Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; source transfer to MrWhite required; MCP source capture refuses absent tree. Both health/authentication/coord claim PASS.'}
assert summary['combined_GPU_invocations']==summary['protocol_GPU_invocations']+summary['lifetime_GPU_invocations']
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history)
provenance={'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'inputs':[{'path':str(ROOT/p),'sha256':sha(ROOT/p)} for p in sources],'system_files':checked,'rootpatch_sha256':sha(rootpatch),'system_modified':False,'Qwen_job_ids':[]};dump(OUT/'provenance.json',provenance)
coverage=read(ROOT/'results/hardware-coverage.json');assert not coverage['complete']
for row in coverage['coverage']:
 if row['category']=='Native ICB factory/runtime boundary':row['remaining_requirements']='Installed factory/no-op methods remain unchanged. Application-local CPU compute subset qualified separately; full resource/state contracts, render, GPU-resident ICB layout and GPU generation/lowering remain open.'
 if row['category']=='CPU-recorded compute ICB selectors and bounded resource lifetime':
  row['tested_scope']='Latest: three scope-owned native pipelines from hashed library with argument reflection; integer/FMA exact/shared512B+barrier, locals32/33/128. Eight GPU submissions4725invocations/18900uint32 and two lifetime submissions594/2376 after ICB/scope release; default CB retains three program owners and private bindings; unretained negative not submitted. Actual program-offset/QMD/packet checks; seven API rejections; cached scoped classes reused three cycles. Earlier single-program evidence retained.'
  row['remaining_requirements']='General library/program/ABI registration beyond three qualified functions; inherited states, dynamic threadgroup memory/nonuniform grids, rendering, GPU-timeline reset/copy/optimize, indirect range/resourceID/GPU generation and residency/concurrency/stress/benchmarks/L2/L3. Shared metadata buffer is not a GPU-readable ICB command layout.'
  for e in ['results/cpu-icb-profiles-gpu-qualified/independent-verification.json','results/cpu-icb-profiles-lifetime-gpu-qualified/independent-verification.json','results/cpu-icb-profiles-progress/summary.json','CPU_ICB_PIPELINES_NATIFS.txt']:
   if e not in row['evidence']:row['evidence'].append(e)
dump(ROOT/'results/hardware-coverage.json',coverage);dump(RESEARCH/'inventory/hardware-coverage.json',coverage);dump(RESEARCH/'inventory/evidence-summaries/hardware-coverage.json',coverage)
text=f'''KEPLERMETAL — ICB CPU ET TROIS PIPELINES NVIDIA NATIFS

Le scope crée maintenant ses pipelines à partir d’une bibliothèque immuable vérifiée,
au lieu d’accepter trois étiquettes déclaratives. La réflexion native valide les trois
buffers, dimensions/alignment/types/access, et la mémoire partagée statique. Un pipeline
étranger portant le label profile_integer est refusé avant modification d’état.

Sur la GTX 880M registry4294968458, huit soumissions vérifiées donnent4725invocations,
18900mots uint32 corrects. Trois programmes distincts: entier, FMA float à résultats
exactement représentables, shared512B avec barrière et lecture du voisin. Local32/33/128,
réutilisation, changement entier→FMA, plages, reset, copie CPU indépendante et rebinding;
dernier ICB vide n’écrit aucun résultat. Sept contrôles API refusés. Gardes intactes.
104 fichiers bruts relus par un oracle indépendant, y compris les paquets réellement
écrits avant commit. Les trois offsets de programmes sont distincts dans le processus
et stables lors de leur réutilisation; ils ne sont pas des adresses universelles.
QMD v00_06: registre7/7/8, shared0/0/512; masque6=CB1+CB2, pas nombre de registres.
Les autres métadonnées/programmes natifs ne sont pas réécrits par notre compilateur.

Client de durée de vie distinct: deux soumissions,594invocations/2376mots corrects,
trois pipelines et bindings Private encore vivants après libération ICB/scope/encoder
par l’application; classe device restaurée avant commit. Readback encodé avant la
completion. Le contrôle unretained libère les ressources Private et n’est jamais soumis.
18 fichiers bruts vérifiés; l’observation de propriété repose aussi sur l’instrumentation
weak du client signé. Ce n’est pas une preuve générale du fonctionnement des caches.
Les sous-classes process-local sont réutilisées sur trois réinstallations, sans ivar
ajouté ni modification d’une classe native partagée. Concurrence/stress non qualifiés.

Branche B: extension expérimentale L1 du sous-ensemble CPU ICB calcul. Ce chemin recopie
des commandes natives depuis le CPU; aucun layout ICB GPU-résident/généré n’est ajouté.
Ce n’est pas un pilote installé, ni un contrat Metal ICB complet, ni une intégration
transparente aux applications ordinaires. Branche A: aucun port Linux ou correctif
supplémentaire au compilateur/pilote installé n’est démontré par cette étape.
Aucun benchmark, donc aucun gain annoncé. Float couvre ces valeurs exactes uniquement,
pas NaN/denorm/FP64 ou conformité générale. Shared dynamique, états hérités, rendu,
ranges indirects et opérations blit timeline restent à implémenter/qualifier.

Références reproductibles
Git main UNBORN: aucun commit; sources locales non suivies. SHA des sources/exécutables
et commandes exactes dans chaque inputs.json, commands.json et execution/manifest.json.
macOS et compilateur: voir results/cpu-icb-profiles-progress/provenance.json.
GeForceMTLDriver:2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
Bibliothèque:913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd.
NVIDIA open-gpu-doc:4de9b1af2ebcf610d8201af4ad07f7f2fb83b0f8, classes/compute/cla0c0qmd.h,
headerSHA8a4ad7edaf88f26bd90fe8bd06353e2b7b7f6703b570e475a7fae7c4da7ab80c.
EnumSDK:MTLBindingAccessReadOnly0/ReadWrite1/WriteOnly2; notre garde erronée est corrigée.

Depuis {ROOT} (choisir de nouveaux dossiers, les captures existantes sont conservées):
python3 tools/reproduce_cpu_icb_profiles.py --out results/NOUVEAU-prepare
python3 tools/verify_cpu_icb_profiles.py --input results/NOUVEAU-prepare --check-current-sources
Puis, seulement si la préparation PASS:
python3 tools/reproduce_cpu_icb_profiles.py --out results/NOUVEAU-gpu --execute
python3 tools/verify_cpu_icb_profiles.py --input results/NOUVEAU-gpu --check-current-sources
Même séquence avec reproduce_cpu_icb_profiles_lifetime.py/verify_cpu_icb_profiles_lifetime.py.
Le wrapper copie la metallib figée de native-pipeline-profiles-vector-captured; recompiler
avec un autre chemin peut changer son identité et exige une qualification séparée.

Échecs conservés: builtin lane scalaire et compilations hôte (label readonly/private)
avant lancement; garde de réflexion WriteOnly erronée refusée exit4 avant préparation.
Tous les enfants réellement lancés sont terminés; aucun timeout/SIGKILL dans ces cohortes.
83 fichiers système et plist OCLP rehashés identiques; zéro modification système.

Qwen: deux MCP authentifiés et sains, files libres, coordination codex claim PASS.
Tâche T-20261013-230031-fe3487. Aucun job créé: le service exige un root tree déjà importé
sur MrWhite; la copie Windows n’est pas fournie par les outils MCP exposés. La revue
reste NOT RUN en attente du transfert demandé, sans repli cloud. Jeton privé non diffusé.

Objectif matériel complet toujours actif. Prochaine étape: généraliser de façon
conservatrice l’enregistrement des programmes/ABI et les états CPU ICB, puis traiter
rendu/format ICB GPU et génération séparément. Pas de nouveau pourcentage matériel
déduit de ces tests; l’estimation préliminaire d’ingénierie précédente reste indicative.
'''
for a,b in [('registry429','registry 429'),('donnent4725','donnent 4725'),('18900mots','18 900 mots'),('local32','local 32'),('594invocations','594 invocations'),('2376mots','2 376 mots'),('pipelineSHA','pipeline SHA')]:text=text.replace(a,b)
(ROOT/'CPU_ICB_PIPELINES_NATIFS.txt').write_text(text)
print(json.dumps(summary,indent=2))

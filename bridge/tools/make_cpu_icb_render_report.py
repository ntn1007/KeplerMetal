#!/usr/bin/env python3
"""Reconcile public-render ICB proofs and regression snapshots."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-render-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['cpu-icb-render-prepared','cpu-icb-render-gpu-qualified','cpu-icb-render-lifetime-prepared','cpu-icb-render-lifetime-gpu-qualified','cpu-icb-render-grid-regression-prepared','cpu-icb-render-grid-regression-gpu-qualified','cpu-icb-render-dynamic-regression-prepared','cpu-icb-render-dynamic-regression-gpu-qualified','cpu-icb-render-raw-regression-prepared','cpu-icb-render-raw-regression-gpu-qualified']
gpu=read(ROOT/'results/cpu-icb-render-gpu-qualified/independent-verification.json');life=read(ROOT/'results/cpu-icb-render-lifetime-gpu-qualified/independent-verification.json');grid=read(ROOT/'results/cpu-icb-render-grid-regression-gpu-qualified/independent-verification.json');dynamic=read(ROOT/'results/cpu-icb-render-dynamic-regression-gpu-qualified/independent-verification.json');raw=read(ROOT/'results/cpu-icb-render-raw-regression-gpu-qualified/independent-verification.json')
assert all(x['status']=='PASS' for x in [gpu,life,grid,dynamic,raw]);assert gpu['correct_float32_channels']==135168 and life['correct_float32_channels']==12288 and grid['GPU_invocations_counted']==18632 and dynamic['user_GPU_invocations']==5496 and raw['correct_replay_float32_channels']==86016
history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for cohort in cohorts:
 f=ROOT/'results'/cohort;m=read(f/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert not any(m['signed_executable'] in line or m['original_executable'] in line for line in ps.splitlines())
 hashes=read(f/'inputs.json')['source_hashes']
 for name,h in hashes.items():
  assert sha(f/name)==h;folder='src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/name)==h
 history.append({'cohort':cohort,'pid':m['pid'],'exit_code':0,'terminal':True,'source_hashes':hashes})
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for e in baseline['system_files']:
 h=sha(Path(e['path']));assert h==e['sha256'];checked.append({'path':e['path'],'sha256':h})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256'];OUT.mkdir(exist_ok=True)
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN/untracked frozen SHA snapshots','integration_level':1,'public_render_ICB_subset_GPU_qualified':True,'GPU_render_command_buffers':11,'correct_float32_channels':135168,'lifetime_GPU_render_command_buffers':1,'lifetime_correct_float32_channels':12288,'combined_correct_float32_channels':147456,'inherited_scissor_and_caller_pipeline_qualified':True,'CPU_reset_copy_overlap_qualified':True,'private_indices_data_dependence_qualified':True,'caller_scope_ICB_released_before_commit':True,'class_restore_qualified':True,'API_rejection_controls':7,'bare_draw_bytes':[24,60,60],'grid_regression_invocations':18632,'grid_regression_uint32_words':149056,'dynamic_regression_invocations':5496,'dynamic_regression_uint32_words':21984,'raw_render_regression_replay_float32':86016,'full_ICB_contract':False,'GPU_resident_ICB':False,'GPU_generated_ICB':False,'general_pipeline_state_bindings':False,'simultaneous_compute_render_ICB_scope':False,'exact_instance_invocation_count_qualified':False,'performance_benchmark':False,'all_children_terminal':True,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'library_SHA256':'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7','Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; both MCP tools now exposed and authenticated natively, central current source copy not verified'}
sources=['src/KeplerCPUICB.h','src/KeplerCPUICB.mm','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/KeplerNativeRenderDraws.h','src/KeplerNativeRenderDraws.mm','tools/cpu_icb_render_probe.mm','tools/cpu_icb_render_lifetime_probe.mm','tools/reproduce_cpu_icb_render.py','tools/reproduce_cpu_icb_render_lifetime.py','tools/verify_cpu_icb_render.py','tools/verify_cpu_icb_render_lifetime.py','tools/decode_native_commands.py','tools/run_signed_probe.py','tools/make_cpu_icb_render_report.py']
provenance={'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'inputs':[{'path':str(ROOT/p),'sha256':sha(ROOT/p)} for p in sources],'system_files':checked,'rootpatch_sha256':sha(rootpatch),'system_modified':False,'Qwen_job_ids':[]}
dump(OUT/'summary.json',summary);dump(OUT/'provenance.json',provenance);dump(OUT/'verification-history.json',history)
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete']
addition=' CPU render ICB public selectors now qualified in process-local scope: factory/render command slots/owned pipeline/direct/UInt16/UInt32, execute range and CPU reset/copy/overlap. Bare24/60B records inherit actual encoder scissor; caller red pipeline restored and ordinary subsequent draw correct. ElevenCB135168float32, plus caller scope/ICB release12288; leases preserve Private indices and classes restore before commit. Seven pre-dispatch refusals. GPU-resident/generation/general state/L2/L3 remain incomplete.'
for row in coverage['coverage']:
 if row['category'] in ['Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime']:
  if addition not in row['tested_scope']:row['tested_scope']+=addition
  obsolete=' A native-render packet transport is now GPU-qualified as an adjacent foundation; it is not yet connected to indirectRenderCommandAtIndex or executeCommandsInBuffer on render encoders.'
  row['remaining_requirements']=row['remaining_requirements'].replace(obsolete,'')
  remaining=' Public rendering subset remains fixed to a bufferless pinned pipeline/pass; extend pipeline/bindings and state/geometry, mixed compute+render scope, timeline/indirect ranges, GPU-resident/generation, conformance/concurrency/pressure/benchmarks/L2/L3.'
  if remaining not in row['remaining_requirements']:row['remaining_requirements']+=remaining
  for e in ['results/cpu-icb-render-progress/summary.json','results/cpu-icb-render-gpu-qualified/independent-verification.json','results/cpu-icb-render-lifetime-gpu-qualified/independent-verification.json','CPU_ICB_RENDU_PUBLIC.txt']:
   if e not in row['evidence']:row['evidence'].append(e)
for p in [ROOT/'results/hardware-coverage.json',RESEARCH/'inventory/hardware-coverage.json',RESEARCH/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
report=f'''KEPLERMETAL — SOUS-ENSEMBLE CPU ICB DE RENDU RACCORDÉ AUX SÉLECTEURS METAL

Résultat: PROGRESS GPU L1; objectif global toujours incomplet.
Le même KPCPUICBScope fournit maintenant la factory publique de render ICB sur
son objet device, indirectRenderCommandAtIndex, setRenderPipelineState, dessins
directs/indexés, reset/ranges et copie CPU incluant un chevauchement source/dest.
Le scope crée l'encodeur natif depuis le descripteur réellement observé, puis
adapte seulement son objet via une sous-classe sans ivar. Classe originale
et autres méthodes restent intactes; pas de remplacement de classe partagée.

Les records24/60B ne contiennent plus de scissor. L'état de l'encodeur produit
par le pilote (192B de scissor dans les cas testés) est conservé; le dessin de
priming est retiré avant commit. Le pipeline du client est suivi et rétabli:
un vrai dessin Metal ordinaire après l'ICB conserve son shader rouge attendu.
Les pipelines ICB sont réellement créés/possédés par le module depuis la library
native figée. Aucune capacité/famille Metal falsifiée, aucun shader/NAK patché.

Qualification GPU indépendante
11CB:135168composantes float32 correctes,956pixels du shader ICB et187pixels du
shader du client. Toutes les gardes256B et fonds vérifiés byte-à-byte.
ScissorA/B/C différents sur les mêmes records, ranges direct/index16/index32,
indices Private dégénérés0,0,0 et1,1,1 par blit GPU, resetdu direct, copie complète
avant resetdu source, source vide, copie réutilisée et copie avec chevauchement:
les résultats attendus apparaissent/disparaissent exactement.
Le compteurinstanceCount2 est présent mais le shader n'observe pas instance_id:
aucun nombre exact d'invocations vertex/fragment/instances n'est déclaré.

Une autre soumission: scope et ICB réellement libérés après drainage du pool
AVANT commit, classes device/encodeur déjà restaurées, deux indices Private
encore vivants via les leases des records.12288composantes et231pixels corrects.
Total des deux qualifications publiques:147456composantes,12CB. Les records,
pipeline/library/buffers/target restent détenus jusqu'à completion.

Sept contrôles avant dispatch: typescompute mélangés, inheritBuffers, pipeline
étranger, offsetindexmalaligné, zérovertices, slotcompute dansrender, rangeOOB.
Sources/binaries signés/resultats/paquets et oracles CPU indépendants figés.
Tous les dix processus de cette étape terminés exit0 sans SIGKILL/enfant actif.

Non-régression avec les sources communes MODIFIÉES actuelles
- Calcul2D/3D:18632invocations comptées/149056uint32,1024threads etZ64.
- Shared dynamique1/32/48Kio:5496invocations/21984uint32, cached/copied-bound.
- Ancien transport rendu explicite:98304float32 dont86016rejeu.
Les anciens clients calcul compilent sans lier le module rendu optionnel;
son absence refuse proprement l'installation du profil rendu.
83 fichiers système et plist rootpatch OCLP rehashés inchangés.

Périmètre et suite
Un seul PSO vs_state/fs_state, triangles trois sommets, zérobufferShader,
64x48RGBA32Float/sample1, passclear/store sansdepth/stencil/MRT. Descripteurs
Draw/DrawIndexed, ressourcesMetadataShared; index16/32, instances1/2 encodées,
vertexStart/baseVertex/baseInstance0. Métadonnées Shared ne sont pas le layout
de commandes ICB GPU. État/héritage complet, autres pipelines/bindings/geometry,
timeline/rangesindirects, GPU-résident/génération, concurrence/pression/perf et
intégrationL2/L3 restent ouverts. Un scope choisit encore calcul OU rendu;
coexistence ICB calcul+rendu dans le même scope reste à ajouter.
Le setter ICB scissor n'est pas inventé: il n'existe pas dans le SDK26.2.
En cas d'état natif non reconnu et exception d'encodage: jeter ce CB, ne pas
le soumettre. Les sélecteurs hors contrat refusent les commandes.
BrancheB: API de rendu supplémentaire fonctionnelle dans notre processus.
BrancheA: aucun port Linux ni modification du pilote installé ici.
Benchmark NOT RUN; aucun gain CPU/GPU et aucun pourcentage global déduit.

Versions et commandes
Git mainUNBORN/aucun commit; lab non suivi, références exactes par SHA snapshots.
CPUICB.mm:{sha(ROOT/'src/KeplerCPUICB.mm')}
NativeRender.mm:{sha(ROOT/'src/KeplerNativeRenderDraws.mm')}
Library965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
macOS/clang/SDK/sources/83files:results/cpu-icb-render-progress/provenance.json.
Depuis {ROOT}, dossiersnouveaux uniquement:
python3 tools/reproduce_cpu_icb_render.py --out results/NOUVEAU-render-prepare
python3 tools/verify_cpu_icb_render.py --input results/NOUVEAU-render-prepare --check-current-sources
AprèsPASS:
python3 tools/reproduce_cpu_icb_render.py --out results/NOUVEAU-render-gpu --execute
python3 tools/verify_cpu_icb_render.py --input results/NOUVEAU-render-gpu --check-current-sources
Même séquence avec reproduce_cpu_icb_render_lifetime.py et son vérificateur.
Les commandes clang/signature/lifecycle figurent dans chaque commands.json,
inputs.json et execution/manifest.json. La metallib est copiée, pas recompilée.

Qwen: les deux MCP maintenant exposés nativement;healthPASS,coordidentitycodex.
job_ids=[]; revue NOT RUN, copie source centrale courante non vérifiée. Solo autorisé.
TâcheT-20261013-230031-fe3487. Prochaine action: étendre l'enregistrement réel
des pipelines/bindings de rendu et le scope mixte, puis timeline/générationGPU.
'''
(ROOT/'CPU_ICB_RENDU_PUBLIC.txt').write_text(report);print(json.dumps(summary,ensure_ascii=False,indent=2))

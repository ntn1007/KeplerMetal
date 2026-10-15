#!/usr/bin/env python3
"""Reconcile mixed compute/render scope and the GPU data dependency proofs."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-mixed-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
gpu=read(ROOT/'results/cpu-icb-mixed-gpu-qualified/independent-verification.json');grid=read(ROOT/'results/cpu-icb-mixed-grid-regression-gpu-qualified/independent-verification.json');render=read(ROOT/'results/cpu-icb-mixed-render-regression-gpu-qualified/independent-verification.json');dynamic=read(ROOT/'results/cpu-icb-mixed-dynamic-regression-gpu-qualified/independent-verification.json');assert all(x['status']=='PASS' for x in [gpu,grid,render,dynamic]);assert gpu['GPU_compute_invocations_counted']==192 and gpu['correct_float32_channels']==110592
cohorts=['native-gpu-indices-pipeline-captured','cpu-icb-mixed-prepared','cpu-icb-mixed-gpu-qualified','cpu-icb-mixed-grid-regression-prepared','cpu-icb-mixed-grid-regression-gpu-qualified','cpu-icb-mixed-render-regression-prepared','cpu-icb-mixed-render-regression-gpu-qualified','cpu-icb-mixed-dynamic-regression-prepared','cpu-icb-mixed-dynamic-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for name in cohorts:
 f=ROOT/'results'/name;m=read(f/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert not any(m['signed_executable'] in line or m['original_executable'] in line for line in ps.splitlines());h=read(f/'inputs.json')['source_hashes']
 for filename,digest in h.items():
  assert sha(f/filename)==digest;folder='src' if filename.startswith('Kepler') or filename.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/filename)==digest
 history.append({'cohort':name,'pid':m['pid'],'exit_code':0,'terminal':True,'source_hashes':h})
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for row in baseline['system_files']:
 h=sha(Path(row['path']));assert h==row['sha256'];checked.append({'path':row['path'],'sha256':h})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256'];OUT.mkdir(exist_ok=True)
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN/untracked exact SHA snapshots','mixed_compute_render_ICB_scope_qualified':True,'same_device_class_when_render_registered':True,'GPU_producer_private_indices_consumed_by_render':True,'main_command_buffers':9,'GPU_compute_invocations_counted':192,'correct_float32_channels':110592,'colored_pixels':535,'intermediate_CPU_read_of_produced_indices':False,'missing_producer_consumer_degenerate_indices_reset_copies_qualified':True,'compute_render_objects_separate_domains':True,'cross_domain_refusal_controls':2,'native_compute_register_count':7,'integration_level':1,'full_ICB_contract':False,'GPU_resident_ICB':False,'GPU_generated_ICB':False,'general_render_pipeline_bindings':False,'synchronization_concurrency_pressure_conformance':False,'performance_benchmark':False,'grid_regression_invocations':18632,'grid_regression_uint32_words':149056,'render_regression_float32_channels':135168,'dynamic_regression_invocations':5496,'dynamic_regression_uint32_words':21984,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'all_children_terminal':True,'compute_library_SHA256':'7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911','manifest_SHA256':'225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be','render_library_SHA256':'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7','Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; both native MCP tools authenticated/healthy, central current source snapshot not verified'}
sources=['src/KeplerCPUICB.h','src/KeplerCPUICB.mm','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/KeplerNativeRenderDraws.h','src/KeplerNativeRenderDraws.mm','src/cpu_icb_gpu_indices.metal','src/cpu_icb_gpu_indices.json','tools/cpu_icb_mixed_probe.mm','tools/reproduce_cpu_icb_mixed.py','tools/verify_cpu_icb_mixed.py','tools/native_gpu_indices_pipeline_probe.mm','tools/reproduce_native_gpu_indices_pipeline.py','tools/decode_native_commands.py','tools/run_signed_probe.py','tools/make_cpu_icb_mixed_report.py']
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'inputs':[{'path':str(ROOT/p),'sha256':sha(ROOT/p)} for p in sources],'system_files':checked,'rootpatch_sha256':sha(rootpatch),'system_modified':False,'Qwen_job_ids':[]})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete']
addition=' Latest: compute and render ICB objects coexist under the same device/scope/queue. GPU compute emits indices0,1,2 or1,1,1 into Private buffer, then native indexed-render reads the identical address in the same main CB with no produced-data CPU read between stages. Nine CB/192atomic-counted compute invocations/110592float32; missing producer/consumer, degeneracy, domain copies/reset and empty source controls PASS. Mixed slot descriptors and cross-domain CPU copy refused. Native shaders, no NAK.'
for row in coverage['coverage']:
 if row['category'] in ['Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime']:
  if addition not in row['tested_scope']:row['tested_scope']+=addition
  row['remaining_requirements']=row['remaining_requirements'].replace('mixed compute+render scope, ','').replace('mixed compute+render scope','scope concurrency/pressure')
  for e in ['results/cpu-icb-mixed-progress/summary.json','results/cpu-icb-mixed-gpu-qualified/independent-verification.json','CPU_ICB_CALCUL_RENDU.txt']:
   if e not in row['evidence']:row['evidence'].append(e)
for p in [ROOT/'results/hardware-coverage.json',RESEARCH/'inventory/hardware-coverage.json',RESEARCH/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
report=f'''KEPLERMETAL — CALCUL ET RENDU ICB DANS LE MÊME SCOPE

PROGRESS L1. Le scope ne choisit plus exclusivement calcul OU rendu. Il garde
ses pipelines calcul et enregistre le domaine rendu sans changer de classe
device une seconde fois. commandTypes choisit le domaine de chaque objet ICB.
Les slots calcul/rendu restent séparés, copieCPU interdomaines/typesmélangés refusée.
Les mêmes factories et caches de sous-classes contrôlent les deux chemins.

Chaîne GPU réelle: kernel NVIDIA natif gpu_indices(7GPR)→uint4 privé→dessin indexé
NVIDIA natif vs_state/fs_state dans UN même command buffer principal. Le CPU
ne lit jamais les indices produits entre ces deux étapes. Le render record
pointe exactement sur le buffer0+offset64 du compute record, vérifié par
les paquetsQMD/bindings et SET_INDEX_BUFFER; lecture finale seulement parblit.
Le producer émet0,1,2,seed ou1,1,1,seed et compte32invocations atomiques.
Les profils/library/manifest/reflection/register metadata sont SHA-vérifiés.

Neuf CB:192invocations calcul comptées et110592composantes float32 correctes,
535pixels colorés au total; index/stamp/counter et toutes les gardes intacts.
Essais(trial,counter,pixels):0/32/117;1/32/0;2/0/0;3/32/0;
4/32/187;5/32/231;6/0/0;7/0/0;8/32/0.
Cas2 retire le producteur, cas3 le consommateur, cas1/8 rendent les indices
dégénérés. Avant chaque essai, des indices0,0,0 sûrs évitent toute lecture
horsindices du shader; retirer le producer laisse ces valeurs et seed-témoin
0x77777777. Copier chaque domaine puis resetdu source donne le résultat voulu;
sourcevide et consumercopié sansproducer restent vides. Les paramètres changent
sans rematérialiser les records, sauf les setters/reset prévus.
Les buffers d'enregistrement restent non soumis; shaderCompute/preparationNOP
et constant-readback/copy précèdent le CBprincipal comme dans le backend existant.
Le CBprincipal contient compute→render→readback, aucun bridgeCPU de l'index.

Non-régression aux bytescourants: calcul2D/3D18632/149056uint32,
renderpublic135168float32 avec pipelineclient/scissor/copies/reset,
shared1/32/48Kio5496/21984uint32. Tous les neuf processus de l'étape exit0,
aucunSIGKILL/enfant encoreactif.83fichiers système/rootpatchOCLP rehashés inchangés.

Limites: API ICBCPU partielle dans notre processus. Ce n'est pas la génération
GPU d'ICB: le GPU génère les données d'indices, les commandes restent copiéesCPU.
RenderPSO/passbufferless64x48RGBA32F ettriangle3vertices encorefixés; autres
PSO/bindings/états/geometry restent à généraliser. Le passage d'encodeurs et
la synchronisation fonctionnent dans ces scénarios en série; mécanismes détaillés,
pression/concurrence et conformance globale non qualifiés. Pas de benchmark,
aucun gain déclaré. L2/L3, compiler/direct-driver/Linusport non démontrés ici.
BrancheB: coexistence et interopAPI; brancheA aucun pilote installé modifié.

Git mainUNBORN/aucun commit; labuntracked, snapshotsSHA sources exécutées.
CPUICB.mm:{sha(ROOT/'src/KeplerCPUICB.mm')}
ComputeLibrary:{summary['compute_library_SHA256']}
ComputeManifest:{summary['manifest_SHA256']}
RenderLibrary:{summary['render_library_SHA256']}
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
macOS/clang/SDK/allSHA:results/cpu-icb-mixed-progress/provenance.json.
Capture native dédiée:results/native-gpu-indices-pipeline-captured. La library
est compilée à partir du nouveau shader MSL2.0; les GPR7 sont lus du QMDcapturé,
pas inférés depuis le fichier source. Capture passive sansdispatch/commit.

Depuis {ROOT}, dossiersnouveaux uniquement:
python3 tools/reproduce_cpu_icb_mixed.py --out results/NOUVEAU-mixed-prepare
python3 tools/verify_cpu_icb_mixed.py --input results/NOUVEAU-mixed-prepare --check-current-sources
AprèsPASS:
python3 tools/reproduce_cpu_icb_mixed.py --out results/NOUVEAU-mixed-gpu --execute
python3 tools/verify_cpu_icb_mixed.py --input results/NOUVEAU-mixed-gpu --check-current-sources
Compilation originaleshaders/commandes exactementdanscommands.json, sources,
binaries signés etlifecycle parcohorte. La reproductioncopie leslibrariesfigées.

Qwenjob_ids=[]: natifsMCPauthentifiés, mais sourcecentrale courante nonvérifiée,
revueNOTRUN/soloautorisé. CoordinationT-20261013-230031-fe3487. Objectifglobal
actif/incomplet. Suite: généraliser l'enregistrementPSO/bindings de rendu en
partantdes fixturesvertexIO natives existantes, puis autresétats ettimeline/GPUICB.
'''.replace('Linusport','Linux port')
(ROOT/'CPU_ICB_CALCUL_RENDU.txt').write_text(report);print(json.dumps(summary,ensure_ascii=False,indent=2))

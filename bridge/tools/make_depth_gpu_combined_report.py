#!/usr/bin/env python3
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];R=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/depth-gpu-combined-progress';assert not OUT.exists();OUT.mkdir()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['depth-gpu-combined-icb-prepared','depth-gpu-combined-icb-gpu-qualified','depth-gpu-combined-native-prepared','depth-gpu-combined-native-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for n in cohorts:
 p=ROOT/'results'/n;m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and not any(m['signed_executable'] in line for line in ps.splitlines());ver='verification-stateful.json' if 'icb-' in n else 'verification.json';assert read(p/ver)['status']=='PASS'
 for f,h in read(p/'inputs.json')['source_hashes'].items():
  assert sha(p/f)==h
  if f!='verify_cpu_icb_depth_gpu.py':assert sha(ROOT/('src' if f.startswith('Kepler') or f.endswith(('.json','.metal')) else 'tools')/f)==h
 history.append({'cohort':n,'pid':m['pid'],'exit_code':0,'terminal':True,'verification':ver})
gpu=read(ROOT/'results/depth-gpu-combined-icb-gpu-qualified/verification-stateful.json');native=read(ROOT/'results/depth-gpu-combined-native-gpu-qualified/verification.json');eq=read(ROOT/'results/depth-gpu-combined-icb-gpu-qualified/equivalence.json');assert gpu['correct_float32_channels']==110592 and gpu['exact_depth_values']==gpu['exact_stencil_values']==27648 and eq['native_ICB_files_byte_identical']==27
prior=read(ROOT/'results/depth-stencil-progress/provenance.json')['current_source_sha256'];core=[n for n in prior if n.startswith('Kepler')];assert len(core)==6 and all(sha(ROOT/'src'/n)==prior[n] for n in core)
system=read(ROOT/'results/depth-stencil-progress/system-check.json')
for row in system['system_files']:assert sha(Path(row['path']))==row['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256'];system['observed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(OUT/'system-check.json',system)
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':system['observed_at'],'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'core_source_files_unchanged':6,'native_reference_color_channels':native['correct_float32_channels'],'native_ICB_files_byte_identical':27,'ordinary_application_integration_complete':False,'full_ICB_contract':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current exact source snapshot on MrWhite unverified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'native-ICB-equivalence.json',eq);dump(OUT/'provenance.json',{'machine':system,'core_sources_unchanged_sha256':{n:prior[n] for n in core},'current_source_sha256':{n:sha(ROOT/('src' if n.startswith('Kepler') or n.endswith(('.json','.metal')) else 'tools')/n) for n in gpu['source_sha256']},'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[],'oracle_correction':'Initial oracle overwrote colors by the last instance regardless of depth. GPU capture completed exit0. The new independent oracle evaluates instances in submission order and applies stencil/depth tests and accepted depth writes. Existing GPU bytes were reverified without rerun; frozen oracle copies and initial error are preserved. Current verifier SHA is reported independently of the frozen old copy.'})
dump(OUT/'oracle-correction.json',{'initial_failure':{'trial':1,'pixel':32,'component':2,'GPU':0.6783370971679688,'old_CPU':0.8443527221679688},'initial_oracle':'results/depth-gpu-oracle-baseline/verify_cpu_icb_depth_gpu.py','corrected_oracle':'tools/verify_cpu_icb_depth_gpu.py','corrected_oracle_SHA256':sha(ROOT/'tools/verify_cpu_icb_depth_gpu.py'),'hardware_capture_not_restarted':True,'reason':'Strict depth compare with depth writes makes first overlapping instance win; equal-depth later fragments fail. LessEqual/Equal/Always cases still allow later writes.'})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete'];addition=' Combined indexed stage-in/GPU resource selection with native depth/stencil qualified:10CB(9render),110592float32 colors within2e-6(max6.956e-7),27648depth and27648stencil exact;224producerthreads/54wordwrites,9stencil-writer and8indexed copied records. 27color/depth/stencil files byte-identical to native direct rendering. MaskReplace7/Equal/NotEqual, depthLess/Greater/Equal/Always/Never/LessEqual with actual write ordering, caller rendering, omission/copy/reset/lifetime/complete reuse qualified. Core6sourcefiles unchanged; independent CPU oracle corrected for first-instance depth occlusion without GPU rerun. Full conformance/L2/L3 remain open.'
for row in coverage['coverage']:
 if row['category'] in ('CPU/GPU memory and DMA','Rasterization and render state','Texture/sampler/surface units','CPU-recorded compute ICB selectors and bounded resource lifetime'):
  row['tested_scope']+=addition;row['evidence']+=['CPU_ICB_ETATS_RESSOURCES_REUNIS.txt','results/depth-gpu-combined-progress/summary.json','results/depth-gpu-combined-icb-gpu-qualified/verification-stateful.json','results/depth-gpu-combined-icb-gpu-qualified/equivalence.json']
for p in [ROOT/'results/hardware-coverage.json',R/'inventory/hardware-coverage.json',R/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(R/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
 if row['id'] in ('B07','B10','B10C'):
  row['pipeline_execution_justesse']+=' Profondeur/stencil+stagein/indexé+PrivateGPUchoice réunis:10CB/110592float32 max6.956e-7/27648depth/27648stencil exacts;224threads/54selectorwrites;27files native/ICBbyteidentical. Testsstatefuldepth,mask,copies/reset/caller/omission/lifetime PASS, coreinchangé.'
  row['preuve']+='; ../bridge/CPU_ICB_ETATS_RESSOURCES_REUNIS.txt; ../bridge/results/depth-gpu-combined-progress/summary.json'
dump(R/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (R/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
(ROOT/'CPU_ICB_ETATS_RESSOURCES_REUNIS.txt').write_text('''KEPLERMETAL — PROFONDEUR/STENCIL, INDEXÉ ET RESSOURCES GPU RÉUNIS

PROGRESS. Branche B/L1, objectifglobal incomplet. Les6sources ducoeur restent
identiques aujalon précédent :qualificationcomposée,aucun piloteLinux/macOS
niOCLP modifié. Pasdemiseàniveau Metal4 oudegainmesuré.

10CB(9rendu),110592float32couleur corrects,errmax6.955697999799781e-7≤2e-6;
27648depth et27648stencil exacts.224threads producteurs et54wordwritesselector
comptés.9records stencilwriter et8records indexés copiés. Référence rendu par
appels natifs :27fichiers couleur/depth/stencil byte-identical. Le sélecteur de
tablesGPU etleproducteur sont partagés parlesdeux références; lacomparaison
porte surtransportICB versusappels derendu natifs, pasdeux implémentationsGPU
indépendantes des kernels. OracleCPU séparé calcule lajustesse end-to-end.

StencilReplace7 surtrianglepartiel/ColorWriteNone, puisEqual/NotEqual;
DepthLess/Greater/Equal/Always/Never/LessEqual, clears.25/.5/1 etwritesactivés.
GTX réduit32valeurs Private, calculebank+sum+signature et6indicesUInt32;
selectorcopie une table24B native(texture,sampler,pointerPrivateparameters).
Rendu smooth/linear/flat, index16/32, baseVertex5/-2, instances2/17/64.
GPUchoice/indices/table consommés sanslectureCPUintermédiaire. Contrôles
producteurabsent/tableA ouindicesdégénérés, consommateurabsent, snapshotsCPU
mutés, copies/reset, completedreuse,câllerstates etfermetureavantcommit :PASS.

Oracleinitial :attendaitladernièreinstancevisible malgréDepthLess etwrites.
Écarttrial1/pixel32/blue:GPU.6783370971679688,CPU.8443527221679688. La capture
GPU a terminéexit0. Correction :évaluerinstances enfragmentorder, appliquer
stencil/depth, puisécrire laprofondeurdesfragmentsacceptés. Encomparaison
stricte, lespremièresinstancesmasquentles suivantes àprofondeur égale.
MêmeGPUcapture revérifiée PASS, aucunredémarrage; sourceoracleinitialgelée et
SHAducorrectifindépendant conservés. Référence nativeultérieure confirme.
Les frozeninputsICB contiennentl'ancienoracle, etlesrésultatsdistinguent
explicitement cetteversionduvérificateur indépendantactuel.

Sources/versions/SHA/argv/binairesoriginaux+signés/PID/bruts dans lescohortes
etresults/depth-gpu-combined-progress/provenance.json. macOS26.7.1/25G241,
SDK26.2/clang17;Git mainUNBORN,aucuncommit.83fichiers/rootpatchOCLP rehashés
inchangés;4processusterminauxexit0sansSIGKILL.
Shader3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775
Writer965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7
Selector463dabbbb9538a9aef9baa6e421fe3d0d9783d3823acf12177225c3ad1c47494
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054

Reproduction depuisbridge,dossiersneufs,gateprepareavantGPU :
python3 tools/reproduce_cpu_icb_depth_gpu.py --out results/repro-depth-gpu-icb-prepare
python3 tools/verify_cpu_icb_depth_gpu.py results/repro-depth-gpu-icb-prepare --current
python3 tools/reproduce_cpu_icb_depth_gpu.py --execute --out results/repro-depth-gpu-icb-exec
python3 tools/verify_cpu_icb_depth_gpu.py results/repro-depth-gpu-icb-exec --current
python3 tools/reproduce_cpu_icb_depth_gpu.py --native --out results/repro-depth-gpu-native-prepare
python3 tools/verify_cpu_icb_depth_gpu.py results/repro-depth-gpu-native-prepare --current
python3 tools/reproduce_cpu_icb_depth_gpu.py --native --execute --out results/repro-depth-gpu-native-exec
python3 tools/verify_cpu_icb_depth_gpu.py results/repro-depth-gpu-native-exec --current
python3 tools/verify_depth_gpu_equivalence.py results/repro-depth-gpu-icb-exec results/repro-depth-gpu-native-exec

Limites :L1,target64x48RGBA32Fsample1,Depth32Float_Stencil8,ref7,z.5;
autresformats/dimensions/states/ABIs/MSAA/MRT/pressure/concurrency/conformance
etL2/L3ouverts. TablePrivate immutable seloncontratcoopératif;pasdecontrôle
général de writesclientsnihandlesGPUinventés. CommandsICB encodées/copiéesCPU,
pasICBGPUrésident/généré. BrancheA nativeCAS/pisteLinux indépendante.
Qwenjob_ids=[]/revueNOTRUN,currentexactWindowscopynonconfirmée;GPUiMacseulement.
Prochaineaction :élargircibles/formats etinterfacesapplicatives sansperdre
les propriétés de calcul,ressources etstates déjàqualifiées.
'''.replace('câllerstates','caller states'))
print(json.dumps(summary,indent=2))

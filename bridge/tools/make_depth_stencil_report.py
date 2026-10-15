#!/usr/bin/env python3
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];R=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/depth-stencil-progress';assert not OUT.exists();OUT.mkdir()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['depth-stencil-icb-prepared','depth-stencil-icb-gpu-qualified','depth-stencil-native-current-prepared','depth-stencil-native-current-gpu-qualified','depth-stencil-gpu-choice-regression-prepared','depth-stencil-gpu-choice-regression-gpu-qualified','depth-stencil-combined-regression-prepared','depth-stencil-combined-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for n in cohorts:
 p=ROOT/'results'/n;m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and not any(m['signed_executable'] in line for line in ps.splitlines());assert read(p/'verification.json')['status']=='PASS'
 for f,h in read(p/'inputs.json')['source_hashes'].items():assert sha(p/f)==h and sha(ROOT/('src' if f.startswith('Kepler') or f.endswith(('.json','.metal')) else 'tools')/f)==h
 history.append({'cohort':n,'pid':m['pid'],'exit_code':0,'terminal':True})
native=read(ROOT/'results/depth-stencil-native-current-gpu-qualified/verification.json');gpu=read(ROOT/'results/depth-stencil-icb-gpu-qualified/verification.json');physical=read(ROOT/'results/depth-stencil-icb-gpu-qualified/physical-verification.json');choice=read(ROOT/'results/depth-stencil-gpu-choice-regression-gpu-qualified/verification.json');combined=read(ROOT/'results/depth-stencil-combined-regression-gpu-qualified/verification.json');assert gpu['correct_float32_channels']==184320 and gpu['exact_depth_values']==46080 and gpu['exact_stencil_values']==9216 and physical['records_in_independently_read_native_stream']==20
matches=[]
for p in (ROOT/'results/depth-stencil-icb-gpu-qualified/outputs').glob('trial-*.bin'):
 if p.name.endswith(('.image.bin','.depth.bin','.stencil.bin')):assert p.read_bytes()==(ROOT/'results/depth-stencil-native-current-gpu-qualified/outputs'/p.name).read_bytes();matches.append({'file':p.name,'SHA256':sha(p)})
assert len(matches)==33;dump(OUT/'native-ICB-byte-comparison.json',matches)
system=read(ROOT/'results/gpu-choice-progress/system-check.json')
for row in system['system_files']:assert sha(Path(row['path']))==row['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256'];system['observed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(OUT/'system-check.json',system)
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':system['observed_at'],'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'integration_level':1,'native_reference_float32_channels':native['correct_float32_channels'],'native_ICB_files_byte_identical':33,'independent_native_stream_records':20,'native_stencil_prefixes_preserved':3,'formats_qualified':[252,260],'stencil_reference_qualified':[7],'pipeline_attachment_mismatch_refused':True,'gpu_choice_regression_channels':choice['correct_float32_channels'],'gpu_choice_regression_producer_threads':choice['counted_producer_threads'],'gpu_choice_regression_selector_writes':choice['counted_selector_word_writes'],'combined_regression_channels':combined['correct_float32_channels'],'combined_regression_compute_invocations':combined['GPU_compute_invocations_counted'],'ordinary_application_integration_complete':False,'full_ICB_contract':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; exact current sources on MrWhite not verified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'machine':system,'current_source_sha256':gpu['source_sha256'],'physical_verifier_SHA256':sha(ROOT/'tools/verify_depth_stencil_physical_commands.py'),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[],'source_baseline':'results/depth-stencil-source-baseline/SHA256.json','prior_native_reference':'results/depth-stencil-native-gpu-qualified kept unchanged; repeated after lifetime source strengthening (drop the caller pass descriptor before commit) and current core modifications'})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete'];addition=' Depth/stencil carried through CPU render ICB:15CB/20copied native draw records,184320float32 colors/46080depth/9216stencil values exact,33raw files byte-identical to native reference. Depth32Float/Depth32Float_Stencil8 attachments,8depth comparisons,near/far order/write-disable,stencilReplace7+Equal/NotEqual spatial mask,ColorWriteNone preserved. Pipeline/pass formats checked before actual mutation; native stencil reference prefix0x1394/0xf54 kept,20records verified in separate Mach capture. Pass snapshot leases attachments after scope restore; control empty ICB gives no triangle. Other dimensions/formats/MSAA/MRT and broader states/conformance/pressure/concurrency/L2/L3 remain open.'
for row in coverage['coverage']:
 if row['category'] in ('CPU/GPU memory and DMA','Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
  row['tested_scope']+=addition;row['evidence']+=['CPU_ICB_PROFONDEUR_STENCIL.txt','results/depth-stencil-progress/summary.json','results/depth-stencil-icb-gpu-qualified/verification.json','results/depth-stencil-icb-gpu-qualified/physical-verification.json']
for p in [ROOT/'results/hardware-coverage.json',R/'inventory/hardware-coverage.json',R/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(R/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
 if row['id'] in ('B10','B10C'):
  row['pipeline_execution_justesse']+=' Profondeur/stencil raccordés:15CB/20records,184320colorsFloat32+46080depth+9216stencil exacts;33files native/ICB byteidentical;8comparaisons,near/far/writeoff,Replace7+Equal/NotEqual spatialmask,callerstate etpasslifetime PASS.'
  row['preuve']+='; ../bridge/CPU_ICB_PROFONDEUR_STENCIL.txt; ../bridge/results/depth-stencil-progress/summary.json'
  row['modification_necessaire']+=' AttachmentsDepth32Float/Depth32Float_Stencil8,formatmatching etprefixStencilReference natif réutilisés enscopeL1; autresétats/formats/cibles/MSAA/MRT etL2/L3 restent ouverts.'
dump(R/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (R/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
experiments=read(R/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in experiments:
 if row.get('id')=='B2':row['prochaine_action']='Élargir dimensions/formats/cibles, blending/MRT/MSAA etcombinaisonsavecstage-in/indexé/ressourcesGPU; qualifierpression/concurrence/conformance puisinterfaceL2appadaptée etL3transparent. Profondeur/stencil existentnativement etsontraccordésL1, pasuneréécriturepilote.'
dump(R/'reports/EXPERIMENTATIONS_PRIORISEES.json',experiments)
report='''KEPLERMETAL — PROFONDEUR ET STENCIL DANS LE SCOPE CPU ICB

PROGRESS, objectif global incomplet. Branche B, intégration L1 :conservation
de fonctions matérielles/nativeMetal existantes dans notre chemin CPU ICB.
Aucune nouvelle modernisation Linux/pilote système ni mise à niveau Metal4.

15CB/20records copiés;184320float32 couleur,46080valeurs profondeur et9216
valeurs stencil exactes. Erreurcouleur0.33fichiers couleur/depth/stencil sont
identiques octet par octet à la référence native, qui utilise les mêmes
fonctions originales ducarrier965bed87. Source/API/compilationdifférentes
du cheminNAK précédent :aucun shader natif remplacé ou corrigé ici.

Depth32Float(252) :8comparaisons contreclearDepth.25; triangle near.25/far.75
dans les deuxordres; depthwrite désactivé surpremierdraw puis activé. Color
etdepthreadbacks contrôlés séparément. Depth32Float_Stencil8(260) :Replace7
sur géométrie partielle/colorWriteNone, puis Equal ouNotEqual. CPU calcule
la couverture à partir du triangle; stencil7/0,profondeur1 etimageattendues.
Un rangeICBvide ne dessinepas etlaisse les clears. Pass/resources/classes/PSO
relâchés/restaurés avantcommit surle derniercas; sortiesidentiques.

Le manifeste de pipeline peut désormais déclarer depth_format,stencil_format
etcolor_write_mask. Formats attestés à la créationPSO et comparés auxattachments
observés avant toute mutation d'exécution. Dummy de préparation construit les
attachments compatibles mais n'est jamais soumis. LoadClear/Store,64x48RGBA32F
sample1 restent imposés. Le descriptorcopié conserve les attachments jusqu'à
completion mêmeaprèsfermeture du scope. Le depth/stencilstate caller reste
géré par l'API native, sans méthode de state ajoutée aux commandesICB.

Le setter nativeStencilReference7 émet 0x1394 puis0xf54 :les2paquets restent
en place; seulela macro24B de draw1 est remplacée pardraw3. CaptureMach séparée
retrouve20records réels et3préfixes stencil inchangés. Aucun ordre de stencil,
de shader ou de pass n'est inventé. MismatchPSO/attachments est refusé avantdraw.

Régressions sources identiques :choixGPU/indexé110592float32/224producerthreads/
54selectorwrites; combiné147456float32/128compute, mêmeserreurs qu'avant.
Huitcohortes qualifiées PASS, processus terminalexit0 sansSIGKILL.83fichiers
système etrootpatch OCLP rehashés inchangés aprèslesessais. Anciens tests intacts.

macOS26.7.1/25G241,SDK26.2,clang17; Git mainUNBORN,aucuncommit. SHA sources,
argvclang,binairesoriginaux/signés,PID,résultatsbruts :cohortes inputs.json,
commands.json/execution/manifest.json; results/depth-stencil-progress/provenance.json.
Library965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054

Reproduction depuisbridge, dossiersneufs, gateprepare avant soumission :
python3 tools/reproduce_depth_stencil_icb.py --out results/repro-depth-native-prepare
python3 tools/verify_depth_stencil_icb.py results/repro-depth-native-prepare --current
python3 tools/reproduce_depth_stencil_icb.py --execute --out results/repro-depth-native-gpu
python3 tools/verify_depth_stencil_icb.py results/repro-depth-native-gpu --current
python3 tools/reproduce_depth_stencil_icb.py --icb --out results/repro-depth-icb-prepare
python3 tools/verify_depth_stencil_icb.py results/repro-depth-icb-prepare --current
python3 tools/reproduce_depth_stencil_icb.py --icb --execute --out results/repro-depth-icb-gpu
python3 tools/verify_depth_stencil_icb.py results/repro-depth-icb-gpu --current
python3 tools/verify_depth_stencil_physical_commands.py results/repro-depth-icb-gpu

Limites :L1, target64x48RGBA32F/sample1, zconstant .25/.75, stencilref7;
autresréférences/masks/arithmetic/depthbias/clip/facecases nonqualifiés ici.
Combinaisondepth/stencil avecstage-in/indexé/tableGPU pasencorequalifiée,
autresdimensions/formats/blends/MRT/MSAA/pressions/concurrence/conformance
etL2/L3 toujoursouverts. Pas d’ICBGPU-résident/généré. Aucun gainCPU/GPU mesuré.
BrancheA(CASgénéral/pisteLinux/modernisationNVIDIA) resteindépendante.
Qwenjob_ids=[]/NOTRUN, exactsnapshotWindowsnonconfirmé; MCP disponibles/auth,
observationsGPU suriMac uniquement. Sources système/OCLP read-only.

Prochaineaction :élargirformats/cibles etcombinaisons de states, puisinterface
utilisablepar applications adaptées, en conservant comportements etpreuves.
'''
(ROOT/'CPU_ICB_PROFONDEUR_STENCIL.txt').write_text(report);print(json.dumps(summary,indent=2))

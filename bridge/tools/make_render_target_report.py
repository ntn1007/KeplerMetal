#!/usr/bin/env python3
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];R=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/render-target-progress';assert not OUT.exists();OUT.mkdir()
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['render-target-native-prepared','render-target-native-gpu-qualified','render-target-icb-prepared','render-target-icb-gpu-qualified','render-target-depth-gpu-regression-prepared','render-target-depth-gpu-regression-gpu-qualified','render-target-legacy-mixed-regression-prepared','render-target-legacy-mixed-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for n in cohorts:
 p=ROOT/'results'/n;m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and not any(m['signed_executable'] in line for line in ps.splitlines());v=read(p/('independent-verification.json' if 'legacy-mixed-' in n else 'verification.json'));assert v['status']=='PASS'
 for f,h in read(p/'inputs.json')['source_hashes'].items():assert sha(p/f)==h and sha(ROOT/('src' if f.startswith('Kepler') or f.endswith(('.json','.metal')) else 'tools')/f)==h
 history.append({'cohort':n,'pid':m['pid'],'exit_code':0,'terminal':True})
gpu=read(ROOT/'results/render-target-icb-gpu-qualified/verification.json');native=read(ROOT/'results/render-target-native-gpu-qualified/verification.json');eq=read(ROOT/'results/render-target-icb-gpu-qualified/equivalence.json');depth=read(ROOT/'results/render-target-depth-gpu-regression-gpu-qualified/verification.json');mixed=read(ROOT/'results/render-target-legacy-mixed-regression-gpu-qualified/independent-verification.json');assert gpu['exact_color_components']==344064 and eq['native_ICB_images_byte_identical']==12
system=read(ROOT/'results/depth-gpu-combined-progress/system-check.json')
for r in system['system_files']:assert sha(Path(r['path']))==r['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256'];system['observed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();dump(OUT/'system-check.json',system)
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':system['observed_at'],'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'integration_level':1,'native_reference_exact_components':native['exact_color_components'],'native_ICB_images_byte_identical':12,'target_profile_extent_software_bound':[1,2048],'all_extents_in_software_bound_GPU_qualified':False,'depth_GPU_choice_regression_channels':depth['correct_float32_channels'],'depth_GPU_choice_regression_depth_values':depth['exact_depth_values'],'legacy_mixed_regression_channels':mixed['correct_float32_channels'],'legacy_mixed_regression_compute_invocations':mixed['GPU_compute_invocations_counted'],'ordinary_application_integration_complete':False,'full_ICB_contract':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; exact current source snapshot on MrWhite unverified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'native-ICB-equivalence.json',eq);dump(OUT/'provenance.json',{'machine':system,'current_source_sha256':gpu['source_sha256'],'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[],'source_baseline':'results/render-target-source-baseline/SHA256.json'})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete'];addition=' Declared color targets in CPU render ICB:RGBA8Unorm/BGRA8Unorm/RGBA16Float/RGBA32Float,64x48/96x64/128x96 (12combinations),86016pixels/344064components exact,12native/ICB images byte-identical. Target width/height/format registered in immutable pipeline profile and checked against actual pass before draw; dummy preparation matches dimensions/format; scissor prefixes preserve target bounds, extent/format mismatches refused. UNorm channel ordering/conversion and half/float storage independently checked with row padding/guards. Software profile bound1..2048 is not full-range hardware qualification. Broader targets, combined resources/states and L2/L3 remain open.'
for row in coverage['coverage']:
 if row['category'] in ('CPU/GPU memory and DMA','Texture/sampler/surface units','Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
  row['tested_scope']+=addition;row['evidence']+=['CPU_ICB_CIBLES_FORMATS.txt','results/render-target-progress/summary.json','results/render-target-icb-gpu-qualified/verification.json','results/render-target-icb-gpu-qualified/equivalence.json']
for p in [ROOT/'results/hardware-coverage.json',R/'inventory/hardware-coverage.json',R/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(R/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
 if row['id'] in ('B10','B10C'):
  row['pipeline_execution_justesse']+=' CiblesRGBA8/BGRA8/RGBA16F/RGBA32F et3dimensions64x48/96x64/128x96:12CB/344064components exacts;12images native/ICBbyteidentical. Targetprofile/Pso/passmatch,dynamicdummy/scissor,currentscope lifetime et2refus PASS. Extents horsfixturesnonqualifiés.'
  row['preuve']+='; ../bridge/CPU_ICB_CIBLES_FORMATS.txt; ../bridge/results/render-target-progress/summary.json'
dump(R/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (R/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
(ROOT/'CPU_ICB_CIBLES_FORMATS.txt').write_text('''KEPLERMETAL — CIBLES ET FORMATS DANS LE SCOPE CPU ICB

PROGRESS. Branche B/L1 :extension des profilsdecible, pasdenouveaufonctionnement
dupiloteinstallé. Objectifmatérielglobal incomplet,système/OCLP read-only.

12CB/12recordscopiés,86016pixels et344064composantes exactes. FormatsRGBA8Unorm
(70),BGRA8Unorm(80),RGBA16Float(115),RGBA32Float(125);dimensions64x48,96x64,
128x96. Fullscreentrianglebornéparscissorcentral;outsideclear0. UNormRGBA
attendu191/32/64/255, BGRAordre64/32/191/255; demi/float valeurs.75/.125/.25/1
exactement représentables. Gardes etpaddingdesrows256B-alignées inchangés.
12images identiquesoctetparoctet àdesappels derendunatifs, sanscopiecommands.

Profilimmuable déclare target_width/target_height/color_format, avec création
PSO auformatattendu. Factoryobservedescriptor/taille/formatréels; mismatch
extent/format refuséavanttoutdraw. Dummyuncommitted de préparation utilise
latargetd déclarée. Préfixesscissor contrôlés contrelesdimensionsobservées et
conservés,nativeprimer1 remplacéparmêmeMacrodraw3; recaptureMachdistincte.
Ancienpipelinelegacy reste64x48RGBA32F; nouveauxprofils n’altèrentpas seswords.

Dimensionsdéclarées acceptées dansune bornelogicielle1..2048, pasune déclaration
du maximumhardware ouune qualification dechaqueextent. Seules3tailles sont
testéesici. Format/base/mip/slice/sample etPSOmatch contrôlés; autresformats
etMRT/MSAA nonexposésparcetteextension. Fermeturescope/resourcesavantcommit
surdernierCB :sortiecorrecte. Aucun shader natifmodifié ouremplacé.

Régressions avec les6sourcescoreactuelles :depth/stencil/indexé/PrivateGPUchoice
110592float32,27648depth/stencil exacts,224threads/54wordwrites;ancienmixed
110592float32/192compute PASS. Huitcohortes terminauxexit0sansSIGKILL.
83fichiers système/rootpatch OCLP rehashésinchangés aprèslesessais.

macOS26.7.1/25G241,SDK26.2/clang17;Git mainUNBORN,aucuncommit. SHA sources,
argvclang,binairesoriginaux/signés/PID/bruts conservés danscohortes;
results/render-target-progress/provenance.json etsourcebaseline donnent les
référencesexactes. Library965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054

Reproduction depuisbridge,dossiersneufs,gatesprepareavantGPU :
python3 tools/reproduce_render_target_icb.py --out results/repro-target-native-prepare
python3 tools/verify_render_target_icb.py results/repro-target-native-prepare --current
python3 tools/reproduce_render_target_icb.py --execute --out results/repro-target-native-gpu
python3 tools/verify_render_target_icb.py results/repro-target-native-gpu --current
python3 tools/reproduce_render_target_icb.py --icb --out results/repro-target-icb-prepare
python3 tools/verify_render_target_icb.py results/repro-target-icb-prepare --current
python3 tools/reproduce_render_target_icb.py --icb --execute --out results/repro-target-icb-gpu
python3 tools/verify_render_target_icb.py results/repro-target-icb-gpu --current

Limites :L1/uneattachment/sample1/colorconstants/douzecombinaisons. Varying,
vertex/index/GPUtables/depth/blends danslesnouveauxformats/tailles restent à
qualifierensemble. Autrescibles/MRT/MSAA/resourcesABIs/conformance/pressure/
concurrency etL2/L3ouverts; pasICBGPU-résident/généré,aucun gainmesuré.
BrancheA nativeCAS/Linux/piloteindépendante,aucuneinstallation.
Qwenjob_ids=[]/reviewNOTRUN,currentexactWindowssnapshotnonconfirmé.
Prochaineaction :généraliserl'exploitationparles applicationsadaptées, élargir
states/ressources/cibles toutenconservantcorrectesse etrefus des casnonqualifiés.
'''.replace('latargetd déclarée','la target déclarée'))
print(json.dumps(summary,indent=2))

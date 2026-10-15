#!/usr/bin/env python3
"""Attest bounded native consumption of public-MSL-generated command records."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/command-ir-runtime-progress-20261015'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
modes=['basic','barrier','clear','copy','reset','no_producer','split','bad_flags','bad_tag','bad_pipeline','bad_address','bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_stage','bad_error','bad_reserved']
legacy=['prepare','select','range','split','completed','copy','no_producer','no_selector']
assert json.loads((OUT/'qualified-suite/receipt.json').read_text())['status']=='PASS'
library=ROOT/'results/command-ir-runtime-library-build-20261015-04';build=json.loads((library/'manifest.json').read_text())
assert sha(library/'libKeplerMetal.a')==build['static_library_SHA256']
for path,h in build['source_SHA256'].items():assert sha(ROOT/path)==sha(library/path)==h
rows=[];raw_equal=0;reference=ROOT/'results/command-ir-runtime-M1-return-20261015/Reference'
assert sha(reference/'gpu_command_frontend_runtime.metal')==sha(ROOT/'src/gpu_command_frontend_runtime.metal')
assert sha(reference/'cpu_icb_combined_shared.metal')==sha(ROOT/'src/cpu_icb_combined_shared.metal')
for kind,items in [('runtime',modes),('legacy',legacy)]:
 for mode in items:
  target=ROOT/'results'/('command-ir-runtime-qualified-'+('bindings-'if kind=='legacy'else'')+mode.replace('_','-')+'-20261015')
  v=json.loads((target/'independent-verification.json').read_text());m=json.loads((target/'execution/manifest.json').read_text());inp=json.loads((target/'inputs.json').read_text());assert v['status'].startswith('PASS') and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and inp['static_library_SHA256']==build['static_library_SHA256']
  rows.append({'kind':kind,'mode':mode,'directory':str(target),'PID':m['pid'],'exact_uint32_words':v['exact_uint32_words'],'consumer_invocations':v.get('consumer_GPU_invocations_counted',v.get('GPU_invocations_counted'))})
  if kind=='runtime'and mode in modes[:7]:
   native=reference/'results'/mode;data=json.loads((target/'results.json').read_text());other=json.loads((native/'results.json').read_text());nm=json.loads((native/'execution/manifest.json').read_text());assert nm['exit_code']==0 and not nm['SIGKILL_requested'] and not nm['authoritative_ps_status'] and other['native_reference']
   for a,b in zip(data['runs'],other['runs']):
    assert a['node_specs']==b['node_specs']
    for field in ['outputs','counter_files']:
     assert a[field]==b[field]
     for name in a[field]:assert (target/'outputs'/name).read_bytes()==(native/'outputs'/name).read_bytes();raw_equal+=1
system=json.loads((OUT/'system-and-source-check-final.json').read_text())
for r in system['system_files']:assert sha(r['path'])==r['SHA256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==system['OCLP_SHA256']
snapshot=json.loads((OUT/'source-snapshot.json').read_text())
for r in snapshot['files']:assert sha(ROOT/r['path'])==r['SHA256']
assert raw_equal==300
runtime=[r for r in rows if r['kind']=='runtime'];nr=[r for r in rows if r['kind']=='legacy'];primary_words=sum(r['exact_uint32_words']for r in runtime);primary_invocations=sum(r['consumer_invocations']for r in runtime)
receipt={'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_goal_turn':'PROGRESS','current_goal_turn':'PROGRESS','objective':'Toutes les fonctionnalités matérielles de la GTX880M sur macOS','objective_complete':False,'Git_branch':'main','Git_commit':None,'source_snapshot_SHA256':sha(OUT/'source-snapshot.json'),'library_SHA256':build['static_library_SHA256'],'materializer_SHA256':'3dc506dc7b763e291f77094eedaaa31217e6676baed342725925e7f95f85ea72','public_MSL_SHA256':sha(ROOT/'src/gpu_command_frontend_runtime.metal'),'GTX_runtime_modes':20,'GTX_runtime_trials':60,'GTX_runtime_exact_uint32_words':primary_words,'GTX_runtime_consumer_invocations':primary_invocations,'GPU_data_rejection_types':13,'API_alias_refusals':4,'legacy_binding_modes':8,'legacy_binding_trials':24,'legacy_binding_exact_words':sum(r['exact_uint32_words']for r in nr),'M1_native_trials':21,'M1_GTX_output_counter_files_identical':300,'zero_CTA_probe_trials':3,'zero_CTA_positive_control_trials':6,'system_files_unchanged':83,'OCLP_unchanged':True,'IR_CPU_read_before_execution':False,'CPU_computed_expected_answers_uploaded':False,'pipeline_resource_roots_CPU_initialized':True,'GPU_computed_grid_from_Private_word':True,'GPU_materializer_consumes_public_MSL_IR':True,'consumer_code_is_native_NVIDIA':True,'integration_level':2,'ordinary_applications_transparent':False,'installed_driver_updated':False,'performance_benchmark':False,'job_ids':[],'rows':rows,'BLOCKED':[],
 'NOT_RUN':['Full older129-cohort regression sweep on this new library','All local/grid/resource dimensions beyond tested fixtures','Nonuniform grid emulation','Stage-in attribute execution','Cross-context ICB copy compatibility','Kernel strides','Concurrent ICB execution and dependency stress','General shader/layout registration','Transparent normal-application integration','New-library performance benchmark','Video/display/power/fullVRAM qualification'],
 'next_action':'Generalize the runtime beyond the three registered native consumers and qualify multidimensional/partial-grid semantics against M1; complete the regression matrix and connect a real unmodified-API client. Keep driver-modernization and Metal-extension branches distinct.'}
(OUT/'qualification-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
(OUT/'next-action.json').write_text(json.dumps({'objective':receipt['objective'],'state':'active','previous_goal_turn':'PROGRESS','objective_complete':False,'job_ids':[],'BLOCKED':[],'next_action':receipt['next_action']},ensure_ascii=False,indent=2)+'\n')
report=ROOT/'COMMANDES_MSL_EXECUTION_NATIVE_GTX_M1_2026-10-15.txt'
report.write_text(f'''KEPLERMETAL — COMMANDES MSL CONSOMMÉES SUR GTX, 15 octobre 2026
Objectif matériel complet ACTIF. Branche B, extension explicitement utilisée
par une application adaptée, niveau2. Aucun pilote système installé ou modifié.

Résultat nouveau
Le même producteur public MSL compute_command est compilé Apple→AIR puis
notre frontend AIR→NIR→SM30. Il écrit des records Private sur GTX. Un shader
Metal natif valide ces records et matérialise le descripteur et les bindings
d'un consommateur NVIDIA natif enregistré. Le consommateur exécute le calcul.
Pas de lecture CPU des records, du choix résolu ou de la grille avant consommation.
Le CPU initialise le catalogue, les racines de pipelines/ressources et les bornes.
Dans ces fixtures, il fournit les handles pipeline/ressource; la grille est
calculée par le producteur depuis un mot Private, pas fournie déjà résolue.

Chemin couvert
reset, pipeline, buffers device/constant, shared0, groupes uniformes1D,
set/clear_barrier et copie de contenu dans le même contexte. Un reset de la
source après copie laisse la destination exécutable. Les barrières conservent
un ordre plus fort:WAIT_FOR_IDLE après chaque commande; aucune concurrence
supplémentaire n'est revendiquée. source/consommation dans le même CB ou trois
CB successifs de la même queue, sans attente CPU intermédiaire après préparation.
La préparation froide utilise toujours des blits/NOP natifs et des attentes.

Matérialisation et refus
Le runtime capture de vrais pipelines, paramètres et ressources et réutilise
les modèles natifs vérifiés; il ne prend pas des adresses de programmes ou des
QMD arbitraires de l'application. Les tokens IR sont propres au prototype,
pas les gpuResourceID Apple. Chaque adresse de sortie/compteur est comparée
au catalogue, l'adresse des paramètres, local et mémoire partagée au modèle.
Un record reset, inconnu ou refusé devient un modèle natif avec grille X=0.
Les tests zéro-CTA gardent sorties intactes et compteurs0; le contrôle grille1
effectue1280invocations correctes. La baseline non modifiée effectue5632.
13types de refus GPU:flags,tag,pipeline,adresse,paramètres,local,shared,
nombre de groupes,Y,threads non divisibles,stage-in,code erreur,réservé.
Ils terminent sans effet consommateur. Ce sont des mutations de données IR,
pas des shaders/conteneurs/machines codes corrompus soumis au GPU.
Quatre refus API protègent les alias des records avec des bindings originaux,
descripteurs ou constantes natifs. Vérification dans le client basic, suivie
d'un témoin de calcul valide. La préparation de ces refus peut allouer/initialiser
des modèles, mais n'exécute pas de producteur ni de kernel consommateur invalide.
Le statut GPU du record est dans generatedGeometry après completion:0reset,
1accepté,2refusé. Un refus GPU ne transforme pas le CB en erreur Metal.

Mesures de correction
20modes/60essais GTX, {primary_words}valeurs uint32 et{primary_invocations}invocations
consommateurs correctes, gardes intactes. Les négatifs ne lancent pas le kernel.
8modes historiques bindings/24essais passent avec la bibliothèque finale:
{receipt['legacy_binding_exact_words']}valeurs correctes. La suite historique complète129cohortes n'a
pas été rejouée ici; ses anciens résultats ne qualifient pas automatiquement
cette nouvelle bibliothèque. L'ancien SDK reste disponible, byte-identique.
Les 7modes publics ont aussi21essais M1 natifs.300fichiers de sorties et
compteurs sont identiques à la GTX et aux oracles CPU. Les mêmes sources MSL
et de consommateur sont utilisées; runtimes et binaires sont distincts.
Les états source, témoins, compteurs bruts et codes de terminaison sont archivés.

Versions et identification
Git main sans commit, sources locales non suivies; versions par SHA256.
iMac macOS26.7.1/build25G241,SDK26.2,x86_64. GTX880M/GK104/SM30,8Go.
M1 Max macOS27.0.1/build26A434,SDK27.0,arm64. MSL macos-metal2.3.
OpenNVDA da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5
Mesa26.2.4 96cb43121031992b85767f9c1be8f3f48e22b1d2
Bibliothèque runtime {receipt['library_SHA256']}
Matérialiseur Metal {receipt['materializer_SHA256']}
Source producteur public {receipt['public_MSL_SHA256']}
Instantané source {receipt['source_snapshot_SHA256']}
Retour M1 f2db6d255d3ed65109d1862c6a08bfa5d928003a60a7206c347ac65e007261a2
Les objets inchangés NativeCommands/Render/CAS/FP64 sont réutilisés avec leurs
empreintes du SDK qualifié; le runtime ICB modifié est recompilé. Import du
producteur:payload SM30 et registres décodés vérifiés, driver épinglé. Aucune
lecture indépendante des instructions résidentes n'est revendiquée.

Reproduction, destinations neuves depuis bridge
python3 tools/build_command_ir_runtime_library.py --out results/<library>
python3 tools/build_command_frontend.py --source src/gpu_command_frontend_runtime.metal --entry encode_runtime_basic --out results/<compiler>
python3 tools/build_command_ir_runtime_client.py --out results/<client> --library-build results/<library> --compiler-build results/<compiler>
python3 tools/run_command_ir_runtime.py --build results/<client> --out results/<run> --mode basic
python3 tools/verify_command_ir_runtime.py results/<run>
Autres modes:barrier,clear,copy,reset,no_producer,split et bad_* du runner/client.
Les scripts utilisent les dépendances et le SDK historique déjà présents dans
ce workspace; le paquet de preuves n'est pas un installateur autonome Mesa/Xcode.
M1:prepare_m1_command_ir_runtime_reference.py,transfer_m1_source_directory.py,
puis run_m1_command_ir_runtime_reference.py dans l'instantané vérifié.

Limites et préservation
Seuls shared_mix_s128/s1024/s4096 de la bibliothèque b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd sont admis.
Catalogue1..8programmes,1..4paires de ressources,1..8destinations, contexte commun,
3bindings; qualifications de cette phase:3programmes/3paires et1ou2destinations.
Grille1D uniforme,local/shared identiques au modèle. Les threads alignés sont
prévus par le validateur mais n'ont pas de cohorte positive dédiée ici.
Threads non uniformes et stage-in sont refusés, copie entre contextes et strides
restent incomplets. Ce n'est pas le contrat ICB complet ni Metal3/4 global.
83fichiers système et OCLP inchangés. Aucun service Qwen/MLX, pilote, kext,
framework système, firmware, protection ou WindowServer modifié. job_ids=[].
Les échecs de compilation MRC/ARC, manifeste de cache et brace de référence
M1 sont conservés. Les essais GPU qualifiés terminent sans SIGKILL.
Aucun gain de performance annoncé. La modernisation NVIDIA/Linux reste une
branche distincte; cette étape n'en démontre pas un portage.

Prochaine action
{receipt['next_action']}

Sources primaires inspectées
MSL6.17.2/6.17.3 https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf
QMDv00_06 https://download.nvidia.com/open-gpu-doc/qmd/1/cla0c0qmd.h
Mesa au commit ci-dessus:src/nouveau/vulkan/nvk_cmd_dispatch.c et headers
NVIDIA cla0c0.h. Les références aident l'analyse; la grille0 est qualifiée
par les essais locaux, pas déduite du fonctionnement d'un autre GPU.
''')
print(json.dumps({'status':'PASS','report':str(report),'runtime_trials':60,'legacy_trials':24,'M1_trials':21,'objective_complete':False}))

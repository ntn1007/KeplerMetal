#!/usr/bin/env python3
"""Reconcile bounded stage-in rendering evidence without declaring completion."""
from pathlib import Path
import datetime, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-vertex-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
gpu=read(ROOT/'results/cpu-icb-vertex-gpu-qualified/verification.json');control=read(ROOT/'results/cpu-icb-vertex-primer-control/verification.json');mixed=read(ROOT/'results/cpu-icb-vertex-mixed-regression-gpu-qualified/independent-verification.json');grid=read(ROOT/'results/cpu-icb-vertex-grid-regression-gpu-qualified/independent-verification.json')
assert all(d['status']=='PASS' for d in [gpu,control,mixed,grid]) and gpu['correct_float32_channels']==110592 and control['colored_pixels']==0
cohorts=['cpu-icb-vertex-prepared-04','cpu-icb-vertex-primer-control','cpu-icb-vertex-gpu-qualified','cpu-icb-vertex-mixed-regression-prepared','cpu-icb-vertex-mixed-regression-gpu-qualified','cpu-icb-vertex-grid-regression-prepared','cpu-icb-vertex-grid-regression-gpu-qualified'];history=[]
ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for name in cohorts:
    f=ROOT/'results'/name;m=read(f/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];assert not any(m['signed_executable'] in line for line in ps.splitlines())
    h=read(f/'inputs.json')['source_hashes']
    for n,digest in h.items():
        assert sha(f/n)==digest;folder='src' if n.startswith('Kepler') or n.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/n)==digest
    history.append({'cohort':name,'pid':m['pid'],'exit_code':0,'terminal':True,'source_hashes':h})
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for row in baseline['system_files']:
    h=sha(Path(row['path']));assert h==row['sha256'];checked.append({'path':row['path'],'sha256':h})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256'];OUT.mkdir(exist_ok=True)
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN/untracked; exact immutable SHA snapshots','generic_reflected_native_vertex_registration':True,'registered_pipelines_tested':['smooth','linear','flat'],'main_command_buffers':9,'copied_draw_records':14,'correct_float32_channels':110592,'colored_pixels':gpu['colored_pixels'],'maximum_float_error':gpu['maximum_float_error'],'tolerance':gpu['tolerance'],'tested_instances':[2,17,64],'tested_vertex_start':5,'tested_base_instance':[3,5],'buffers_private':True,'CPU_raster_oracle':'barycentric interpolation, archived input bytes, independent of GPU output','one_vertex_native_GPU_control_float32_channels':12288,'one_vertex_native_GPU_control_colored_pixels':0,'negative_controls':9,'scope_and_resources_released_before_last_commit':True,'caller_pipeline_and_vertex_state_qualified':True,'CPU_snapshot_copy_reset_overlap_qualified':True,'mixed_regression_compute_invocations':192,'mixed_regression_float32_channels':110592,'grid_regression_invocations':18632,'grid_regression_uint32_words':149056,'native_draw_API_calls_per_record':1,'integration_level':1,'full_ICB_contract':False,'GPU_resident_ICB':False,'GPU_generated_ICB':False,'arbitrary_vertex_fragment_programs_qualified':False,'indexed_stage_in_qualified':False,'fragment_resources_qualified':False,'render_targets_generalized':False,'pressure_concurrency_conformance':False,'performance_benchmark':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'all_children_terminal':True,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; MCPs authenticated, current Windows snapshot not verified','vertex_library_SHA256':gpu and sha(ROOT/'results/cpu-icb-vertex-gpu-qualified/vertex_io_carrier.metallib'),'manifest_SHA256':sha(ROOT/'src/cpu_icb_vertex_profiles.json')}
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'system_files':checked,'rootpatch_sha256':sha(rootpatch),'current_source_hashes':gpu['source_sha256'],'Qwen_job_ids':[]})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete']
addition=' Registered SHA-verified native stage-in render pipelines with reflected Float4 layouts and per-vertex/per-instance buffers: smooth/linear/flat, 9CB,14 copied draw macros,110592 float32 components within 2e-6. Native primers have vertexCount=1 and cannot form triangles; their draw is replaced by the cached count=6 macro. Private buffer updates, CPU copies/reset/overlap, caller pipeline/bulk buffers/offsets/inline instance data and pre-commit scope/resource release qualified. One-vertex native GPU control stays empty. Rendering is L1 CPU materialization/copy with one native primer per record, not GPU-resident/generated ICB or a measured performance improvement.'
for row in coverage['coverage']:
    if row['category'] in ('Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
        if addition not in row['tested_scope']:row['tested_scope']+=addition
        for e in ['results/cpu-icb-vertex-progress/summary.json','results/cpu-icb-vertex-gpu-qualified/verification.json','CPU_ICB_PIPELINES_RENDU.txt']:
            if e not in row['evidence']:row['evidence'].append(e)
for p in [ROOT/'results/hardware-coverage.json',RESEARCH/'inventory/hardware-coverage.json',RESEARCH/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
    if row['id'] in ('B10','B10C'):
        row['pipeline_execution_justesse']='Enregistrement stage-in natif avec ABI réfléchie : smooth/linear/flat, 9CB,14 macros copiées,110592 composantes float32 correctes (erreur max '+str(gpu['maximum_float_error'])+'). Buffers privés par sommet/instance; vertexStart5, baseInstance3/5, instances2/17/64; copies/reset/overlap, données privées mises à jour sans rematérialisation et état caller restauré. Témoin natif un sommet : 12288 composantes nulles. Régressions scope calcul+rendu192/110592 et calcul2D/3D18632/149056 PASS.'
        row['modification_necessaire']='Rendu indexé stage-in, ressources fragment/textures/samplers, autres états et cibles, mélange des profils, ranges indirects/timeline, format ICB GPU-résident/génération, conformance sous pression/concurrence, benchmark et intégration L2/L3 restent à qualifier.'
        row['performance']='Non mesurée. Une amorce native par record; aucun gain CPU ou GPU attribué à cette extension.'
        row['preuve']+='; ../bridge/CPU_ICB_PIPELINES_RENDU.txt; ../bridge/results/cpu-icb-vertex-gpu-qualified/verification.json'
dump(RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
import csv
with (RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
plans=read(RESEARCH/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in plans:
    if row['id']=='B2':
        row['etat']='Enregistrement natif stage-in et transport CPU ICB qualifiés L1 pour trois pipelines et buffers privés : 9CB/110592 composantes, restauration caller et lifetime avant commit, témoins/refus PASS. Pilote système et shader NVIDIA inchangés.'
        row['travail']='Étendre la même inscription réfléchie au rendu indexé et aux ressources fragment depuis les fixtures natives; qualifier états/cibles puis pression/concurrence. Format GPU-résident/génération et intégration L2/L3 restent des contrats distincts.'
dump(RESEARCH/'reports/EXPERIMENTATIONS_PRIORISEES.json',plans)
report=f'''KEPLERMETAL — PIPELINES NATIFS ET BUFFERS DANS LE RENDU ICB

Résultat : PROGRESS, objectif global encore incomplet.
Branche B : extension applicative expérimentale de l'API CPU ICB.
Branche A : aucune nouvelle correction du pilote installée ou transposition
Linux démontrée dans cette étape. Le correctif CAS existant reste distinct.

Ce qui a changé
Le scope accepte des bibliothèques et manifestes en mémoire vérifiés par SHA,
construit et possède les PSO nommés, et compare leur réflexion native à l'ABI.
Attributs Float4, layouts par sommet/instance, stepRate1, lecture seule;
fragment sans ressource. Les plages de fetch sont vérifiées à chaque exécution,
y compris lorsque les commandes sont déjà matérialisées ou copiées.
Le profil constant historique et ses dessins indexés restent disponibles.
Le nouveau chemin général reste limité aux dessins directs stage-in.

L'enregistrement ne prouve pas la compatibilité de tous les programmes.
La qualification actuelle porte sur vs/fs_io_smooth, linear et flat.
Bibliothèque : {summary['vertex_library_SHA256']}
Manifeste : {summary['manifest_SHA256']}
Driver GeForceMTLDriver :
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Git main sans premier commit : aucun commit inventé, sources SHA dans provenance.
Compilateur/SDK/macOS exacts : results/cpu-icb-vertex-progress/provenance.json.

Preuve d'exécution
Capture passive : le profil avec attributs emploie la macro native0x3aa0;
le profil constant historique emploie0x3830. Ces numéros ne sont pas des
équivalences avec les slots MME Nouveau. Les setters natifs sont conservés.
Deux draws non soumis matérialisent la macro stage-in24octets. Au rendu,
une amorce native avec UN sommet produit l'état; elle ne peut former de triangle.
Seuls ses24octets de dessin sont remplacés par la macro enregistrée à6sommets.
Les prefixes natifs scissor/flush restent inchangés. Un lecteur Mach distinct
dans la sonde recapture les paquets réels et les archives; l'oracle compare
ces bytes, les bindings, les images GPU et une rasterisation CPU barycentrique.
Le témoin natif GPU à un sommet reste vide (12288 composantes nulles).

Mesures de justesse, pas de performance
9 command buffers principaux,14 records copiés,110592 composantes float32,
{gpu['colored_pixels']} pixels colorés; erreur max {gpu['maximum_float_error']:.12g}, tolérance2e-6.
Instances2/17/64, vertexStart5, baseInstance3/5. L'image observe instance_id;
aucun compteur d'invocations vertex indépendant n'est annoncé.
Smooth : interpolation perspective; linear : sans perspective; flat : constante.
Buffers vertex et instance Private, offsets non nuls et gardes vérifiés.
Mise à jour du contenu privé sans setter : record réutilisé et nouvelle image.
Copie CPU, reset du source, overlap copy et source vide : résultats corrects.
Pipeline et bindings caller restaurés : bulk buffers, offset et bytes inline
utilisés avant l'ICB, puis dessin natif ordinaire après, comparé au CPU.
Dernier CB : scope/ICB/refs locales relâchés et classes restaurées AVANT commit;
résultats GPU corrects avec les ressources nécessaires retenues jusqu'à completion.
Neuf refus : hashes, PSO étranger, index/alignement/bindings/plages, fragment.

Non-régression avec les mêmes sources actuelles
Scope calcul→indicesPrivate→rendu :192 invocations comptées/110592 float32 PASS.
Calcul2D/3D :18632 invocations comptées/149056 uint32 PASS; local1024 etZ64.
Sept processus de la qualification sont terminés exit0, sans SIGKILL.
83 fichiers système et rootpatch OCLP rehashés inchangés.
Les captures/échecs préparatoires antérieurs restent préservés dans results.

Contrat et limites
Intégration L1. Factory publique seulement sur notre objet device et notre
encoder explicitement adapté; aucun composant système ni famille Metal falsifiés.
Objets ICB CPU; les paquets sont copiés par le CPU dans le flux natif.
Une amorce native PAR RECORD reste nécessaire : aucun gain n'est annoncé.
ICB GPU-résident/généré, ranges indirects et copie sur timeline restent ouverts.
Stage-in indexé, mélange de profils legacy/stage-in dans une même séquence,
buffers fragment, textures/samplers, autres formats/cibles/états, gestion
pression/concurrence et conformance générale restent non qualifiés.
La restauration est qualifiée pour le pipeline caller explicitement défini et
les setters buffer/array/offset/bytes couverts; ce n'est pas une preuve de tous
les états possibles. Aucun benchmark nouveau, aucune accélération WindowServer.
Deux MCP Qwen disponibles, identité codex; job_ids=[] / revue NOT RUN : le code
actuel doit encore être transféré et vérifié sur MrWhite avant délégation.

Commandes reproductibles (depuis le dossier bridge, dossiers de sortie neufs)
python3 tools/reproduce_cpu_icb_vertex.py --out results/repro-vertex-prepare
python3 tools/verify_cpu_icb_vertex.py results/repro-vertex-prepare --current
python3 tools/reproduce_cpu_icb_vertex.py --primer-control --out results/repro-vertex-control
python3 tools/verify_cpu_icb_vertex.py results/repro-vertex-control --current
python3 tools/reproduce_cpu_icb_vertex.py --execute --out results/repro-vertex-gpu
python3 tools/verify_cpu_icb_vertex.py results/repro-vertex-gpu --current
Les scripts conservent les sources/bibliothèques, argv exacts de clang,
empreintes des exécutables originaux/signés, PID, sorties et données brutes.
Une expiration d'observation ne prouve jamais la fin d'un processus.

Interface d'intégration à poursuivre
installRenderingOnDevice crée le scope; registerRenderVertexLibraryData charge
la bibliothèque/manifest vérifiés. renderPipelineForName fournit le PSO possédé.
Descriptor Draw, maxVertexBufferBindCount2, inheritBuffers/PipelineStateNO,
maxKernel/Fragment0. Les commandes publiques setRenderPipelineState,
setVertexBuffer et drawPrimitives enregistrent l'état, sans GPU à cette étape.
renderEncoderWithDescriptor observe le vrai pass natif; executeCommandsInBuffer
encode les records; le caller end/commit sa propre commande. restore ferme le
scope. Le transfert à des applications ordinaires et le niveau L3 restent à faire.
'''
(ROOT/'CPU_ICB_PIPELINES_RENDU.txt').write_text(report)
print(json.dumps(summary,ensure_ascii=False,indent=2))

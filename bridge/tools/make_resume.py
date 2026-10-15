#!/usr/bin/env python3
"""Short incremental handoff: new verified facts, limits and commands."""
from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parents[1]
def read(name):
    path = root/'results'/name
    if not path.exists(): return None
    try: return json.loads(path.read_text())
    except json.JSONDecodeError: return None

metal = read('submission-probe.json')
native = read('native-transport.json')
air = read('air-reader-air.json')
metallib = read('air-reader-metallib.json')
reference = read('add-reference.json')
compiled = read('air-sm30-air.json')
disassembly = read('disassembly-summary.json')
state = {'metal_reference':metal,'native_transport':native,'AIR_reader':air,
         'metallib_reader':metallib,'addition_through_installed_driver':reference,'offline_SM30_compilation':compiled,
         'independent_disassembly':disassembly,
         'NAK_binary_executed_on_GPU':False,'new_system_driver_installed':False,
         'new_Metal_family_qualified':False}
nak = read('nak-macos-summary.json')
if nak and nak.get('NAK_AIR_binary_executed_and_compared_on_GTX'):
    state['NAK_binary_executed_on_GPU'] = True
    state['NAK_macos_execution'] = nak
    compute = read('compute-summary.json')
    if compute:
        state['compute_qualification'] = compute
        state['hardware_coverage'] = read('hardware-coverage.json')
    graphics=read('graphics-summary.json')
    if graphics:
        state['graphics_qualification']=graphics
        state['hardware_coverage']=read('hardware-coverage.json')
    renderState=read('render-state-summary.json')
    if renderState:
        state['render_state_qualification']=renderState
        state['hardware_coverage']=read('hardware-coverage.json')
    vertexIO=read('vertex-io-summary.json')
    if vertexIO:
        state['vertex_io_qualification']=vertexIO
        state['hardware_coverage']=read('hardware-coverage.json')
    resource=read('resource-summary.json')
    if resource:
        state['resource_qualification']=resource
        state['hardware_coverage']=read('hardware-coverage.json')
    tess=read('tessellation-summary.json')
    if tess:
        state['tessellation_qualification']=tess
        state['hardware_coverage']=read('hardware-coverage.json')
    video=read('video-summary.json')
    if video:
        state['video_qualification']=video
        state['hardware_coverage']=read('hardware-coverage.json')
    execution=read('native-execution-summary.json')
    if execution:
        state['native_execution_qualification']=execution
        state['hardware_coverage']=read('hardware-coverage.json')
    reportName='VIDEO.txt' if video else ('TESSELLATION.txt' if tess else ('RESSOURCES_IMAGES.txt' if resource else ('VERTEX_RESSOURCES.txt' if vertexIO else ('ETATS_RENDU.txt' if renderState else ('GRAPHIQUE.txt' if graphics else ('CALCUL_MATERIEL.txt' if compute else 'NAK_MACOS.txt'))))))
    if execution:reportName='EXECUTION_NATIVE.txt'
    atomic64=read('atomic64-summary.json')
    if atomic64:
        state['atomic64_qualification']=atomic64
        state['hardware_coverage']=read('hardware-coverage.json')
        reportName='ATOMIQUES_64.txt'
    imageLoad=read('image-load-summary.json')
    if imageLoad:
        state['image_load_qualification']=imageLoad
        state['hardware_coverage']=read('hardware-coverage.json')
        reportName='LECTURE_IMAGES.txt'
    sharedUnits=read('shared-units-summary.json')
    if sharedUnits:
        state['shared_units_qualification']=sharedUnits
        state['hardware_coverage']=read('hardware-coverage.json')
        reportName='MEMOIRE_PARTAGEE.txt'
    benchmark=read('shared-benchmark-summary.json')
    if benchmark:state['shared_benchmark']=benchmark
    importAudit=read('import-audit-summary.json')
    if importAudit:
        state['import_audit']=importAudit
        state['hardware_coverage']=read('hardware-coverage.json')
        reportName='AUDIT_PONT_NAK.txt'
    (root/'results/resume.json').write_text(json.dumps(state,indent=2)+'\n')
    report = (root/reportName).read_text()
    (root/'REPRISE.txt').write_text(report+'\nÉtat de reprise structuré : results/resume.json.\n'
        +'La soumission IOKit brute kb_submit_native reste non implémentée ;\n'
        +'la voie fonctionnelle importe notre code dans un programme de notre processus\n'
        +'et utilise le pilote installé pour les ressources et la soumission Metal.\n')
    print('Updated REPRISE.txt and results/resume.json with verified NAK execution')
    sys.exit(0)
(root/'results/resume.json').write_text(json.dumps(state,indent=2)+'\n')
text = '''KEPLERMETAL — éléments retenus du prompt ancien, 13 octobre 2026

La session s'exécute localement sur l'iMac. Le bloc Windows/OpenClaw/SSH
est périmé pour cette session ; aucun accès SSH n'a été nécessaire ni testé.
Les cinq anciens documents nommés dans le prompt n'ont pas été trouvés dans
le workspace courant par la recherche de noms. Le prompt a servi de source
de pistes, pas d'instruction pour installer un pilote ou contacter un hôte.

Sources exactes
Mesa 26.2.4 : commit 96cb43121031992b85767f9c1be8f3f48e22b1d2.
OpenNVDA : commit da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5, licence MIT.
Envytools : commit f102b82381f3f11cee113d16374c87091db039d9, licence MIT.
Linux/Nouveau : fichiers v6.18, commit 7d0a66e4bb9081d75c82ec4957c50034cb0ea449.
Archives, URL, empreintes et outils : results/*source*.json et provenance.json.

Pistes conservées et vérifiées
1. NAK possède déjà le backend SM30 : sm20.rs sélectionne encode_sm30_shader
   pour 30 <= SM < 32. Il n'est pas nécessaire d'écrire un nouvel encodeur.
2. OpenNVDA apporte un lecteur AIR/metallib et AIR -> NIR. Notre addition de
   buffers bornée compile avec la toolchain Metal locale en .air et .metallib ;
   les deux fichiers sont lus avec succès (un corps add_buffers, métadonnées
   air.kernel présentes). La chaîne AIR -> NIR -> SM30 fonctionne hors ligne.
   Les deux formats produisent le même code de 384 octets : 39 instructions
   rapportées par NAK, 24 registres, groupe 32x1x1, 4 buffers, bloc constant 56 B.
   SHA256 SASS : 90c087d8997f5c25b4a292118d07f57f16bbbda2544b64c513ed5c97cc334a00.
   Envytools reconnaît toutes les instructions, opérandes et bits du binaire.
   Référence numérique : le même add_buffers.metallib exécute correctement
   1041 additions sur la GTX via le pilote installé : zéro différence CPU,
   47 éléments de garde inchangés après 1088 threads dispatchés. Ce test ne
   soumet pas le code NAK. Le temps GPU d'un seul test est un relevé de
   diagnostic, pas un benchmark ou une preuve d'accélération.
3. Les correctifs de compilation macOS sont utiles. Notre adaptation construit
   seulement les bibliothèques du compilateur : pas de DRM simulé ni de pilote
   NVK macOS prétendu fonctionnel. Aucun changement aux encodeurs SM30.
   Les offsets fragment/sample/printf requis par l'édition de liens sont nuls
   dans le harness ; ces fonctionnalités ne sont pas testées ni prises en
   charge par ce harness limité à notre kernel compute sans printf.
4. Envytools permet un contrôle indépendant de l'ISA. Seul envydis est construit,
   sans les outils d'accès au GPU. Les directives du parser sont adaptées au
   Bison 2.3 installé, sans changer les tables d'instructions.
5. Les capacités et résultats OpenNVDA/RTX 4080 ne qualifient pas la GTX 880M.
   nakc.c initialise AD103, device 0x2704, SM89 et compute 0xc9c0.
   NVMTLDevice.m:6035 rejoue certaines commandes indirectes dans une boucle CPU ;
   cette voie doit être évaluée séparément de l'allègement du CPU.

Accès matériel : ce qui fonctionne et ce qui manque
Le module IOKitKeplerBridge, sans dépendance Metal, identifie PCI 10de:1198,
ouvre les clients 5/6/8 et mappe les zones partagées connues. Il n'écrit pas
dans ces zones. kb_submit_native retourne explicitement 1001 (non implémenté).
La trace de notre test Metal observe le client de queue 8, sélecteur 1,
descripteur de 32 octets compatible avec la forme 8 + 24 * 1. La sémantique
des ressources/fences et le flux de commandes NVIDIA restent à établir.
Il manque le contrat d'allocation, d'adressage GPU, de soumission et de
complétion pour exécuter le binaire NAK en conservant un seul propriétaire
matériel. Les sondes Metal actuelles utilisent le pilote déjà installé.

Prochaine validation matérielle
Une addition bornée compilée par NAK doit être exécutée puis comparée au CPU
avec les buffers, adresses, constantes, barrières et fences réellement établis.
L'obtention d'un fichier SASS n'est pas cette validation.

Reproduction depuis le dossier bridge
python3 tools/setup_tools.py
python3 tools/reproduce_probes.py
python3 tools/prepare_mesa_compiler.py
python3 tools/build_offline_compiler.py
python3 tools/build_air_compiler.py
python3 tools/prepare_envydis.py
cmake -S tools/envydis-build -B build/envydis-only -DCMAKE_BUILD_TYPE=Release -DENVYTOOLS_SOURCE="$PWD/vendor/envytools-f102b82381f3f11cee113d16374c87091db039d9"
cmake --build build/envydis-only --target envydis --parallel 2
python3 tools/disassemble.py
python3 tools/provenance.py
python3 tools/make_resume.py
Les commandes exactes de compilation et leurs codes de retour sont enregistrés
dans results/*.json ; les sorties détaillées sont dans logs/.
Le setup local utilise Python 3.12.14, Meson 1.11.2, Ninja 1.13.2,
Rust/cargo 1.99.0, bindgen 0.73.2 et cbindgen 0.29.2.
La toolchain Apple relevée est Xcode 26.3, SDK 26.2, Clang 17.0.0,
Metal 32023.864 ; notre source Metal est compilée en macos-metal2.4.
Accepter cette option de langage ne qualifie pas toute l'API Metal 2/3/4.

Résultats relevés automatiquement
'''
text += json.dumps(state,indent=2,ensure_ascii=False)+'\n'
(root/'REPRISE.txt').write_text(text)
print('Saved REPRISE.txt and results/resume.json')

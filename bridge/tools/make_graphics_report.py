#!/usr/bin/env python3
"""Report fixture-qualified graphics without closing the full hardware goal."""
from pathlib import Path
import argparse
import hashlib
import json

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/graphics-reproduction')
folder=parser.parse_args().input.resolve();manifest=json.loads((folder/'manifest.json').read_text())
assert manifest['driver_unchanged']
records=[];pixels=0;events=0
for case in manifest['cases']:
    result=json.loads((root/case['result']).read_text());assert result['device']=='NVIDIA GeForce GTX 880M'
    for code in case['codes']:
        assert hashlib.sha256((root/code['path']).read_bytes()).hexdigest()==code['sha256']
    if case['label'].startswith('compute-'):
        assert result['mismatches']==0 and result['changed_guards']==0
        continue
    assert result['mismatched_channels']==0
    for test in result['tests']:
        pixels+=test['pixels']
        if case['codes']:
            assert test['import']['contract_verified']
            for event in test['import']['events']:
                if event.get('code_replaced'):
                    events+=1
                    assert event['imported_code_identical'] and event['original_graphics_header_preserved']
    records.append({'label':case['label'],'result':case['result'],'codes':case['codes'],
                    'format':result['target_format'],'half_geometry':result['half_geometry'],'tests':result['tests']})
evidence=['results/graphics-summary.json',str((folder/'manifest.json').relative_to(root)),
          'src/mesa-26.2.4-macos-texture-import.patch']
updates=[
 {'category':'Application-local native program import','status':'sample_qualified',
  'tested_scope':'Compute 5, vertex 0, fragment 4; containers 7/8/9; identical SASS and decoded size/GPR; paired stages, preserved native graphics header and retained payloads',
  'remaining_requirements':'General metadata/resource ABI; other stages and control-stack/scratch configurations; sustained/concurrent lifecycle qualification and incompatible-driver handling',
  'evidence':['src/KeplerProgramImport.mm']+evidence},
 {'category':'Texture/sampler/surface units','status':'sample_qualified',
  'tested_scope':'NAK bound 2D RGBA8Unorm read, nearest/linear, clamp-to-edge; 64x48 fixture; RGBA8Unorm and RGBA32Float targets; observed texture TIC224/sampler TSC1 for this carrier',
  'remaining_requirements':'General binding ABI and other sizes; 1D/3D/cube/array/mips/formats, stores/gather/compression/ordering. Linear UNorm16 oracle is an empirical fixture model, not general format conformance',
  'evidence':['tools/graphics_fragment_compile.c','tools/render_reference_probe.mm']+evidence},
 {'category':'Rasterization and render state','status':'sample_qualified',
  'tested_scope':'NAK vertex ID/position and fragment constants/textures; separately and paired; two geometries with CPU coverage/pixel oracle, native headers and installed raster transport',
  'remaining_requirements':'Blend/depth/stencil/MRT/MSAA, vertex attributes/interpolation, indexed/instanced/indirect draws, tessellation; standalone/system renderer integration',
  'evidence':['tools/render_reference_probe.mm','src/graphics_reference.metal']+evidence}]
for summaryName in ('render-state-summary.json','vertex-io-summary.json','resource-summary.json','tessellation-summary.json'):
    stateSummary=root/'results'/summaryName
    if stateSummary.exists():
        stateUpdates={r['category']:r for r in json.loads(stateSummary.read_text()).get('coverage_updates',[])}
        updates=[stateUpdates.get(r['category'],r) for r in updates]
summary={'collected_at':manifest['collected_at'],'render_cases':len(records),
         'compute_regression_cases':len(manifest['cases'])-len(records),'pixels_checked':pixels,
         'channels_checked':pixels*4,'verified_stage_imports':events,'mismatched_channels':0,
         'records':records,'coverage_updates':updates,'driver_sha256':manifest['driver_after_sha256'],
         'driver_unchanged':True,'graphics_performance_benchmark':False,'global_hardware_goal_complete':False}
(root/'results/graphics-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
ledgerPath=root/'results/hardware-coverage.json'
if ledgerPath.exists():
    ledger=json.loads(ledgerPath.read_text());byCategory={r['category']:r for r in updates}
    ledger['coverage']=[byCategory.get(r['category'],r) for r in ledger['coverage']];ledger['complete']=False
    ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n')
report=f'''KEPLERMETAL — exécution NAK graphique sur macOS
Relevé : {manifest['collected_at']}

{len(records)} cas de rendu et {summary['compute_regression_cases']} régressions compute passent.
{pixels} pixels / {pixels*4} canaux comparés au CPU, {events} imports de stage vérifiés.
Zéro canal hors des tolérances. Aucun benchmark de gain graphique.
Le pilote complet et les API Metal 3/4 restent à développer.

CONTRAT ET PREUVE
KPCreateVertexPipeline, KPCreateRenderPipeline et KPCreateGraphicsPipeline
remplacent temporairement le programme dans notre processus au constructeur
NVMTLFunctionVariant initWithCompilerOutput:size:device:, puis restaurent la
méthode. Le pilote installé garde allocations, commandes, fences et ressources.
Code SASS comparé octet par octet, taille et GPR relus dans le variant.
Stages : vertex0, fragment4, compute5 ; conteneurs 7/8/9 observés. Les 80 octets
du header graphique natif et les sections auxiliaires sont préservés.
Il s’agit d’un composant explicite d’application, pas d’un pilote autonome.

Vertex NAK : vertex ID et sortie position, plein écran puis couverture partielle
calculée indépendamment au CPU. Fragment NAK : .25/.5/.75/1, différente du
carrier .75/.125/.25/1 ; fs_match natif contrôle la conversion de couleur.
Textures NAK : TLD/TEX bound et TEXBAR, lectures, nearest et linéaire.
Les deux stages ensemble passent aussi la géométrie partielle et les textures.
Les cinq régressions freshly linked vérifient FP64, atomic32, shuffle,
shared_reduce et SGEMM64x64. Calculs antérieurs : NAK_MACOS.txt et CALCUL_MATERIEL.txt.

JUSTESSE ET LIMITES
Fixture 64x48, entrée RGBA8Unorm, sorties RGBA8Unorm/RGBA32Float.
RGBA8 : lecture/nearest exacts ; constante/linéaire tolérance 1 LSB. La valeur .5
donne 127 avec NAK comme avec fs_match natif. RGBA32Float : constante exacte,
lecture/nearest erreur <=2.969e-8. Linéaire : écart à l’idéal <=6.684e-6.
Le modèle nearest-even UNorm16 explique cette fixture, erreur <=2.978e-8
(tolérance 1e-7). Le premier oracle idéal rejetait 8653 canaux ; ces résultats
et la comparaison des modèles restent conservés. Pas de conformance générale.
Texture0 observée ici comme TIC224 et sampler TSC1 : autre contrat refusé.
Les temps gpu_seconds des petits essais sont des diagnostics, sans benchmark.

COMPILATEUR LOCAL
Mesa26.2.4 commit {manifest['mesa_commit']}.
Trois correctifs, hors pilote : callback NIR après lowering avant allocation,
TIC8+TSC5 dans sm20.rs, et TEXBAR avant EXIT si résultats texture en attente.
Patch : src/mesa-26.2.4-macos-texture-import.patch.
Le bindless initial et des coordonnées mal alignées rendaient zéro : échecs
conservés dans results/texture-*-status.json. La reproduction finale produit
le SASS par le compilateur, sans retouche manuelle des octets.
Envytools commit {manifest['envytools_commit']} : instructions décodées.

PISTES ASTRA
hw_runner.rs épinglé : CB0 ligne37, run_raw423, nak_fill_qmd513,
SetProgramRegion530 et SendPcas572. Référence Linux DRM/Nouveau, pas transport
macOS. Notre CB2 compute natif56B n’est pas copié depuis ce CB0.
https://github.com/chaotic-cx/mesa-mirror/blob/mesa-26.2.4/src/nouveau/compiler/nak/hw_runner.rs
NullMoth cible Turing+ et GSP, pas Kepler. Aucun kext ni code repris ici.
https://github.com/nullmoth/nvidia-macos-driver
Ghidra/LLDB et metal2vulkan restent des diagnostics possibles ; le raccordement
actuel fonctionne sans ajouter de seconde pile.

REPRODUCTION DEPUIS bridge
python3 tools/reproduce_graphics.py
python3 tools/make_graphics_report.py
python3 tools/provenance.py
python3 tools/make_resume.py
Préconditions : archives Mesa build/mesa et outils locaux Rust/Meson/Ninja,
envydis et toolchain Metal Xcode déjà préparés. Aucun installateur système.
Commandes complètes : {str((folder/'commands.json').relative_to(root))}
Sources/binaires/SHA256 : {str((folder/'manifest.json').relative_to(root))}
SHA256 pilote avant/après : {manifest['driver_after_sha256']}
Aucune modification du pilote système ou d’OCLP par ces commandes.

RESTANT
États blend/depth/stencil/MSAA/MRT et ressources générales, puis backend
tensoriel et inférence LLM. Le registre results/hardware-coverage.json conserve
le but complet ouvert. Ces essais n’étendent pas les familles Metal déclarées.
'''
(root/'GRAPHIQUE.txt').write_text(report.replace('freshly linked','fraîchement liées'))
print('Saved GRAPHIQUE.txt, graphics-summary.json and hardware coverage.')

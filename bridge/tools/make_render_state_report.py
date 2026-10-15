#!/usr/bin/env python3
"""Verify the render-state evidence and update the full hardware coverage ledger."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/render-state-final')
folder=parser.parse_args().input.resolve();manifest=json.loads((folder/'manifest.json').read_text())
assert manifest['driver_unchanged']
for artifact in manifest['source_snapshot']+manifest.get('runtime_snapshot',[])+manifest['shaders']:
    assert hashlib.sha256((root/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
checks=json.loads((folder/'container-checks.stdout').read_text());assert checks['failures']==0
records=[];stageImports=0
for case in manifest['cases']:
    assert case['exit_code']==0,case
    result=json.loads((root/case['result']).read_text());assert result['device']=='NVIDIA GeForce GTX 880M'
    assert result['mismatched_channels']==0 and result['command_status']==4
    if case['mode']=='nak':
        assert len(result['imports'])==result['draws']
        for evidence in result['imports']:
            assert evidence['contract_verified']
            replaced=[e for e in evidence['events'] if e.get('code_replaced')]
            assert len(replaced)==evidence['requested_stages']
            assert all(e['imported_code_identical'] and e['original_graphics_header_preserved'] for e in replaced)
            stageImports+=len(replaced)
    records.append({**case,'pixels_checked':result['pixels_checked'],'maximum_error':result['maximum_error'],
                    'tolerance':result['tolerance'],'expected_colored_pixels':result['expected_colored_pixels'],
                    'format':result['target_format'],'samples':result['samples'],'render_targets':result['render_targets']})
byMode={mode:[r for r in records if r['mode']==mode] for mode in ('native','nak')}
assert {r['label'] for r in byMode['native']}=={r['label'] for r in byMode['nak']}
expected={'blend-'+x for x in ('add','subtract','reverse','min','max','one-add','constant')}
expected|={'depth-'+x for x in ('never','less','equal','less-equal','greater','not-equal','greater-equal','always','near-first','far-first','write-off')}
expected|={'scissor','color-mask','cull-front','cull-back','mrt2','mrt4','mrt8','stencil-equal','stencil-inverse'}
expected|={f'msaa{s}-mask{m}' for s in (2,4,8) for m in (0,1,5,15)}
assert {r['label'] for r in byMode['nak']}==expected
# Preserve the observed failures independently of the default reproduction output.
failureFolder=root/'results/render-state-failures';failureFolder.mkdir(exist_ok=True)
for label in ('stencil-equal','stencil-inverse'):
    source=root/'results/render-state-reproduction'/(label+'-nak.json')
    if source.exists():
        data=json.loads(source.read_text())
        if data.get('error') and not (failureFolder/source.name).exists():shutil.copyfile(source,failureFolder/source.name)
evidence=['results/render-state-summary.json',str((folder/'manifest.json').relative_to(root)),
          'tools/render_state_probe.mm','tools/graphics_fragment_compile.c']
updates=[
 {'category':'Application-local native program import','status':'sample_qualified',
  'tested_scope':'Compute5/vertex0/fragment4, container7/8/9; byte-identical SASS and decoded size/GPR; preserved native headers; paired stages and vertex-only stencil writer; observed zero terminal alignment padding accepted, corrupt copies rejected',
  'remaining_requirements':'General resource/metadata ABI; other shader stages, control-stack/scratch configurations, sustained/concurrent lifecycle and incompatible-driver handling',
  'evidence':['results/graphics-summary.json','src/KeplerProgramImport.mm',str((folder/'container-checks.stdout').relative_to(root))]+evidence},
 {'category':'Rasterization and render state','status':'sample_qualified',
  'tested_scope':'NAK vertex ID/position and constants/textures; CPU pixel and coverage oracles; seven blending fixtures; eight depth compares and near/far/write-disable sequences; stencil Replace/Equal/NotEqual spatial mask; scissor/color mask/front-back culling; 2/4/8 simultaneous RGBA32Float targets; RGBA8 MSAA2/4/8 with shader sample masks0/1/5/15 and resolve',
  'remaining_requirements':'Other blend factors/operations and exceptional values, varying depth/depth bias/clip, stencil arithmetic and masks, sample positions/per-sample attributes and edge coverage, vertex attributes/interpolation, indexed/instanced/indirect draws, tessellation and standalone/system renderer integration',
  'evidence':['results/graphics-summary.json']+evidence}]
vertexPath=root/'results/vertex-io-summary.json'
if vertexPath.exists():
    vertexUpdates={r['category']:r for r in json.loads(vertexPath.read_text()).get('coverage_updates',[])}
    updates=[vertexUpdates.get(r['category'],r) for r in updates]
resourcePath=root/'results/resource-summary.json'
if resourcePath.exists():
    resourceUpdates={r['category']:r for r in json.loads(resourcePath.read_text()).get('coverage_updates',[])}
    updates=[resourceUpdates.get(r['category'],r) for r in updates]
tessPath=root/'results/tessellation-summary.json'
if tessPath.exists():
    tessUpdates={r['category']:r for r in json.loads(tessPath.read_text()).get('coverage_updates',[])}
    updates=[tessUpdates.get(r['category'],r) for r in updates]
summary={'collected_at':manifest['collected_at'],'native_cases':len(byMode['native']),'nak_cases':len(byMode['nak']),
         'pixels_checked':sum(r['pixels_checked'] for r in records),'nak_pixels_checked':sum(r['pixels_checked'] for r in byMode['nak']),
         'verified_stage_imports':stageImports,'container_checks':len(checks['cases']),'mismatched_channels':0,
         'maximum_float_error':max(r['maximum_error'] for r in records if r['format']=='RGBA32Float'),
         'maximum_unorm_error_lsb':max(r['maximum_error'] for r in records if r['format']=='RGBA8Unorm'),
         'driver_sha256':manifest['driver_after_sha256'],'driver_unchanged':True,'records':records,'coverage_updates':updates,
         'performance_benchmark':False,'global_hardware_goal_complete':False}
(root/'results/render-state-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text());byCategory={r['category']:r for r in updates}
ledger['coverage']=[byCategory.get(r['category'],r) for r in ledger['coverage']];ledger['complete']=False
ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n')
report=f'''KEPLERMETAL — états de rendu NAK / GTX 880M
Relevé : {manifest['collected_at']}

{summary['nak_cases']} cas NAK et {summary['native_cases']} témoins natifs passent.
{summary['pixels_checked']} pixels comparés au CPU, dont {summary['nak_pixels_checked']} avec NAK.
{stageImports} imports de stage vérifiés ; aucun canal hors tolérance.
RGBA32Float : erreur maximale {summary['maximum_float_error']}; MSAA RGBA8 :
erreur maximale {summary['maximum_unorm_error_lsb']} LSB, tolérance 1 LSB.
Ces essais établissent la justesse de fixtures, sans benchmark de performance.

FONCTIONS MATÉRIELLES EXERCÉES
Blending : addition, soustraction, soustraction inverse, min/max, facteurs
SourceAlpha/OneMinusSourceAlpha, addition One/One et BlendColor/BlendAlpha.
Les couleurs/alpha NAK et natives sont différents ; les références CPU le sont aussi.
Depth32Float : les huit comparaisons, égalité à .25, triangles .25/.75 dans
les deux ordres et désactivation de l’écriture de profondeur. Les deux ordres
conservent le triangle proche ; write-off permet au second triangle loin de passer.
Stencil Depth32Float_Stencil8 : Replace7 sur une géométrie partielle puis Equal
ou NotEqual7. Résultats : 2304 pixels sélectionnés ou les 768 pixels complémentaires.
Le writer est un pipeline vertex NAK seul, sans fragment et sans écriture couleur.
Scissor17/9/31/21, écriture Red/Blue, culling avant/arrière avec winding CCW.
MRT : 2, 4 et 8 cibles RGBA32Float, couleurs différentes par cible ; NAK MRT8
utilise 40 GPR (< limite physique SM30 de 63), code320 octets.
MSAA : 2, 4 et 8 échantillons, masques NAK0/1/5/15, sortie RGBA8 et resolve.
Le CPU prédit la fraction d’échantillons actifs, y compris une sortie nulle.
Exemple mask5/MSAA4 : pixel NAK [32,64,96,127] vs idéal byte [32,64,96,128].

IMPORT MACOS ET CORRECTION
Les API KPCreateGraphicsPipeline et KPCreateVertexPipeline conservent les
headers natifs, importent notre SASS octet par octet et relisent taille/GPR.
Le pilote installé reste propriétaire du raster/ROP, des ressources et commandes.
La méthode du constructeur est modifiée temporairement dans notre processus,
puis restaurée. Il ne s’agit pas d’un remplacement du pilote système.
Le premier import stencil était rejeté avant soumission : la constante finale
de 4 octets était suivie de 4 octets nuls d’alignement8. Capture native intacte
dans {str((folder/'stencil-native-container').relative_to(root))}.
Le parseur accepte cet alignement terminal nul ; {len(checks['cases'])} contrôles CPU
incluent les vrais conteneurs et des versions/liens/longueurs/paddings corrompus.
Échecs conservés : results/render-state-failures/ et results/render-state-initial/.

VERSIONS ET ARTEFACTS
Mesa26.2.4 commit {manifest['mesa_commit']}.
NAK SM30 avec le correctif local texture séparé, SHA256 :
{manifest['mesa_texture_patch_sha256']}
Code, sources figées, compilateur, bibliothèque, sonde et metallib :
{str((folder/'manifest.json').relative_to(root))}
Environnement/toolchains actualisés : results/provenance.json.
SHA256 GeForceMTLDriver avant/après : {manifest['driver_after_sha256']}
Aucun pilote système, OCLP, VBIOS, fréquence ou registre matériel modifié.
Les tailles mémoire JSON sont des allocations logiques couleur/readback,
pas une mesure de résidence physique ni une validation de toute la VRAM8Go.

REPRODUCTION DEPUIS bridge
python3 tools/reproduce_render_state.py --out results/render-state-final
python3 tools/make_render_state_report.py --input results/render-state-final
python3 tools/provenance.py
python3 tools/make_resume.py
Préconditions : build Mesa/NAK isolé et correctifs déjà préparés, envydis,
toolchain Metal Xcode et outils locaux. Aucune installation système.
Commandes complètes : {str((folder/'commands.json').relative_to(root))}

LIMITES ET SUITE
Ce résultat ne qualifie pas toutes les variantes des unités testées, un pilote
autonome, WindowServer ou une nouvelle famille Metal. Le registre de couverture
reste ouvert. À développer : ressources/bindings généraux, attributs et
interpolation, indexation/instancing/indirect, tessellation, vidéo, grilles3D,
scratch/spills, VRAM sous pression, gestion énergie et backend tensoriel/LLM.
Les benchmarks SGEMM antérieurs restent dans CALCUL_MATERIEL.txt ; aucun gain
graphique ou gain global d’interface n’est déduit de ces essais.
'''
(root/'ETATS_RENDU.txt').write_text(report)
print('Saved ETATS_RENDU.txt, render-state-summary.json and hardware coverage.')

#!/usr/bin/env python3
"""Verify resource/draw fixtures and preserve the full hardware coverage goal."""
from pathlib import Path
import argparse
import hashlib
import json

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/vertex-io-qualified')
folder=parser.parse_args().input.resolve();manifest=json.loads((folder/'manifest.json').read_text());assert manifest['driver_unchanged']
for artifact in manifest['source_snapshot']+manifest['runtime_snapshot']+manifest['shaders']:
    assert hashlib.sha256((root/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
records=[];imports=0
for case in manifest['cases']:
    assert case['exit_code']==0
    data=json.loads((root/case['result']).read_text());assert data['device']=='NVIDIA GeForce GTX 880M'
    assert data['mismatched_channels']==0 and data['argument_mismatches']==0 and data['changed_argument_guards']==0
    assert data['command_status']==4
    for key in ('render_import','compute_import'):
        evidence=data[key]
        if evidence:
            assert evidence['contract_verified']
            for event in evidence['events']:
                if event.get('code_replaced',True):assert event['imported_code_identical'];imports+=1
    records.append({**case,'draw':data['draw'],'mode':data['mode'],'interpolation':data['interpolation'],'memory':data['memory'],
                    'pixels':data['pixels_checked'],'maximum_float_error':data['maximum_float_error'],
                    'GPU_argument_producer':data['arguments_produced_on_GPU'] and not data['native_empty_control'],
                    'argument_words':data['argument_words'],'native_empty_control':data['native_empty_control']})
assert len(records)==38
assert {r['interpolation'] for r in records}=={'smooth','linear','flat'}
required={'direct','vertex-start','indexed16','indexed32','base-vertex','negative-base-vertex','instanced','base-instance','indirect','indirect-indexed','indirect-control'}
assert {r['draw'] for r in records}==required
assert {r['memory'] for r in records}=={'managed','nocopy','private'}
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text());existing={r['category']:r for r in ledger['coverage']}
evidence=['results/vertex-io-summary.json',str((folder/'manifest.json').relative_to(root)),'tools/vertex_io_compile.c','tools/vertex_io_probe.mm']
updates=[]
for category,addition,remaining in [
 ('Application-local native program import','Resource-backed vertex attributes0/1/2 and varying0; CB1[0x6c4] observed instance-base convention; CB2 compute resource addresses for indirect argument producer',
  'General metadata/resource ABI beyond this driver/fixture, other shader stages and scratch/control stack, sustained/concurrent workloads and incompatible-driver handling'),
 ('Rasterization and render state','Float4 vertex attributes with32-byte interleaved stride,16-byte per-instance stride; perspective/screen-linear/flat interpolation with unequal w; vertexStart5; UInt16/UInt32 indices with nonzero byte offsets; baseVertex+2/-2; two instances and baseInstance3; indirect/indexed-indirect parameters produced by NAK compute before rendering in the same command buffer',
  'Other attribute types/formats/strides/step rates, varying layout/bindings and broader draw/interpolation boundaries, per-sample shading, tessellation and standalone/system integration')]:
    row=dict(existing[category]);row['status']='sample_qualified'
    if addition not in row['tested_scope']:row['tested_scope']+='; '+addition
    row['remaining_requirements']=remaining;row['evidence']=list(dict.fromkeys(row['evidence']+evidence));updates.append(row)
resourcePath=root/'results/resource-summary.json'
if resourcePath.exists():
    resourceUpdates={r['category']:r for r in json.loads(resourcePath.read_text()).get('coverage_updates',[])}
    updates=[resourceUpdates.get(r['category'],r) for r in updates]
tessPath=root/'results/tessellation-summary.json'
if tessPath.exists():
    tessUpdates={r['category']:r for r in json.loads(tessPath.read_text()).get('coverage_updates',[])}
    updates=[tessUpdates.get(r['category'],r) for r in updates]
summary={'collected_at':manifest['collected_at'],'cases':len(records),'pixels_checked':sum(r['pixels'] for r in records),
         'maximum_float_error':max(r['maximum_float_error'] for r in records),'tolerance':2e-6,
         'verified_stage_imports':imports,'GPU_argument_producer_cases':sum(r['GPU_argument_producer'] for r in records),
         'native_empty_controls':sum(r['native_empty_control'] for r in records),'mismatched_channels':0,
         'driver_sha256':manifest['driver_sha256'],'driver_unchanged':True,'records':records,'coverage_updates':updates,
         'performance_benchmark':False,'global_hardware_goal_complete':False}
(root/'results/vertex-io-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
byCategory={r['category']:r for r in updates};ledger['coverage']=[byCategory.get(r['category'],r) for r in ledger['coverage']];ledger['complete']=False
ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n')
report=f'''KEPLERMETAL — ressources de vertex et dessins indirects
Relevé : {manifest['collected_at']}

38 cas passent ; {summary['pixels_checked']} pixels comparés à un raster CPU indépendant.
Erreur maximale RGBA32Float : {summary['maximum_float_error']:.9g}, tolérance2e-6.
Aucun canal hors tolérance, aucun argument incorrect, aucune garde modifiée.
{imports} imports de stage vérifiés. Pas de benchmark ou de gain de performance annoncé.

RESSOURCES ET INTERPOLATION
Position/couleur Float4 interleavées, stride32, attributs0/1 ; offset par instance
Float4, stride16, attribut2. Accès NAK ALD0x80/0x90/0xa0 et AST varying0x80.
Buffers Managed, NoCopy Shared et Private avec transferts GPU passent.
Les vertices ont w=.5/1/2 : perspective et interpolation linéaire écran produisent
des images distinctes. Flat est comparé au premier vertex de chaque triangle
dans cette fixture. Tests avec vertex NAK seul, fragment seul, puis ensemble.
Le vertex et le fragment NAK appliquent des transformations de couleur différentes
des témoins natifs : exécuter le carrier inchangé ne donne pas les pixels attendus.

DESSINS
vertexStart5 ; index16/32 bits avec offset16 octets ; baseVertex+2 et -2 ;
deux instances ; baseInstance3. Le CPU reconstruit les triangles et les poids
barycentriques en double, avec division par w pour la perspective.
L’essai baseInstance avant correction échouait sur3072 canaux, écart .0703126.
Le shader natif révèle ALD instance0x2f8 + CB1[0x6c4] : NAK ajoute désormais
cette base fournie par le driver. Échec/source conservés dans results/vertex-io-failures/.

ARGUMENTS PRODUITS SUR GPU
NAK compute décode seed XOR0x5a5a5a5a et écrit les paramètres du dessin.
Upload, compute, render indirect et readback sont encodés dans une seule
MTLCommandBuffer. Notre code ne lit pas les arguments GPU avant la soumission.
Non indexé : [6,2,0,3]. Indexé : [6,2,3,2,3]. Les gardes restent intactes.
Le contrôle utilisant le kernel natif non remplacé écrit zéro et rend une image
vide. Les cas « native » désignent les stages raster natifs ; leur producteur
indirect positif utilise lui aussi NAK. Le contrôle vide utilise le compute natif.
Le driver rapporte storageModePrivate2 pour les arguments, mais contents n’est
pas nul sur cette pile legacy. Cela a fait échouer notre première assertion,
retirée car elle ne décrit pas ce driver. Aucune lecture des octets avant commit
n’a été ajoutée ; aucune résidence physique VRAM n’est déduite de cette propriété.
La soumission reste gérée par le driver installé. L’encodage interne du dessin
indirect et son coût CPU ne sont pas qualifiés indépendamment dans cette étape.

VERSIONS ET PREUVE
Mesa26.2.4 commit {manifest['mesa_commit']}, SM30, cinq programmes avec24 GPR,
sans scratch/CRS. Correctif NAK texture local conservé : voir GRAPHIQUE.txt.
Bytecode importé identique ; taille/GPR relus dans les variants ; header natif
préservé. Sources et exécutables figés : {str((folder/'manifest.json').relative_to(root))}
Captures natives des modes smooth/linear/flat dans ce même dossier.
SHA256 GeForceMTLDriver avant/après : {manifest['driver_sha256']}
Aucune modification des pilotes système, OCLP, VBIOS, fréquences ou registres.

REPRODUCTION DEPUIS bridge
python3 tools/reproduce_vertex_io.py --out results/vertex-io-qualified
python3 tools/make_vertex_io_report.py --input results/vertex-io-qualified
python3 tools/provenance.py
python3 tools/make_resume.py
Commandes exactes et codes de retour : {str((folder/'commands.json').relative_to(root))}
Préconditions : archives Mesa/NAK déjà préparées, envydis, tools Xcode et
libKeplerProgramImport.dylib. Outils/sources actuels : results/provenance.json.

LE BUT COMPLET RESTE OUVERT
Il reste notamment les bindings/formats généraux, uniformes/storage/images,
tessellation, grilles3D, scratch/spills, contraintes mémoire, vidéo, énergie,
intégration système et backend tensoriel/LLM. Les essais ne qualifient pas une
nouvelle famille Metal ni toutes les variantes des fonctions matérielles.
'''
(root/'VERTEX_RESSOURCES.txt').write_text(report)
print('Saved VERTEX_RESSOURCES.txt, vertex-io-summary.json and hardware coverage.')

#!/usr/bin/env python3
"""Preserve raster limitations and add independently checked buffer-only results."""
from pathlib import Path
import argparse,hashlib,json

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--capture',type=Path,default=root/'results/tessellation-capture-reproduction')
args=parser.parse_args();capture=args.capture.resolve();capture.relative_to(root/'results')
manifest=json.loads((capture/'manifest.json').read_text())
for artifact in manifest['source_snapshot']+manifest['runtime_snapshot']:
    assert hashlib.sha256((root/artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
assert hashlib.sha256((capture/'capture.sass').read_bytes()).hexdigest()==manifest['code_sha256']
assert hashlib.sha256((capture/'carrier.metallib').read_bytes()).hexdigest()==manifest['carrier_metallib_sha256']
records=[dict(case,data=json.loads((root/case['result']).read_text())) for case in manifest['cases']]
assert len(records)==16 and all(r['exit_code']==0 for r in records)
for record in records:
    data=record['data'];assert data['mismatches']==data['guard_mismatches']==data['tail_mismatches']==0
    assert data['command_status']==4 and data['device']=='NVIDIA GeForce GTX 880M'
    if data['NAK_imported']:assert data['import']['contract_verified']
assert manifest['driver_unchanged']
summaryPath=root/'results/tessellation-summary.json';summary=json.loads(summaryPath.read_text())
maxError=max(r['data']['max_error_vs_cpu_double'] for r in records)
factor64=next(r['data'] for r in records if r['label']=='nak-factor64')
captureSummary={'manifest':str((capture/'manifest.json').relative_to(root)),'cases':records,'comparisons':manifest['comparisons'],
                'code_sha256':manifest['code_sha256'],'shader_info':manifest['shader_info'],'maximum_cpu_error':maxError,
                'independent_pointwise_arithmetic_passed':True,'independent_topology_passed':False,
                'scope':manifest['scope']}
summary['buffer_capture']=captureSummary
coveragePath=root/'results/hardware-coverage.json';coverage=json.loads(coveragePath.read_text())
additions={
 'Application-local native program import':'Buffer-only tessellation stage2, no raster output; native CB1 buffer0/1/2 addresses confirmed; 384B NAK SASS,24GPR, scratch/CRS0',
 'Global atomic arithmetic':'UInt32 returning atomic add in tessellation evaluation allocates unique output slots, up to4874 invocations in this fixture',
 'Rasterization and render state':'Buffer-only triangle tessellation evaluation: factors0..64, independent CPU square at captured hardware coordinates, exact native/NAK coordinate multisets; factor64 arithmetic error<=2.655e-8; raster ideal-bound discrepancy remains open'
}
changed=[]
for row in coverage['coverage']:
    addition=additions.get(row['category'])
    if not addition:continue
    if addition not in row['tested_scope']:row['tested_scope']+='; '+addition
    for evidence in ('results/tessellation-summary.json',str((capture/'manifest.json').relative_to(root)),'tools/tessellation_capture_compile.c','tools/tessellation_capture_probe.mm'):
        if evidence not in row['evidence']:row['evidence'].append(evidence)
    changed.append(row)
updates={r['category']:r for r in summary.get('coverage_updates',[])};updates.update({r['category']:r for r in changed})
summary['coverage_updates']=list(updates.values())
coveragePath.write_text(json.dumps(coverage,indent=2)+'\n');summaryPath.write_text(json.dumps(summary,indent=2)+'\n')
lines=['KEPLERMETAL — tessellation NAK sur GTX 880M','',
 'Le code NAK est exécuté par le stage2 post-tessellation du pilote installé.',
 'La création du pipeline relit taille/registres et vérifie le code importé octet',
 'par octet ; le header graphique natif80B et le transport Metal sont conservés.',
 'Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2.',
 'Aucun changement de pilote système, OCLP, protection, VBIOS ou fréquence.','',
 'CAPTURE DIRECTE — SANS RASTERISATION',
 '16 essais : shader natif et NAK, facteurs0/1/2/4/8/16/32/64, partition integer.',
 'Trois buffers Private initialisés par blit : compteur, coordonnées, valeurs.',
 'Buffers0/1/2 : adresses GPU natives CB1[8/40/72], offsets de liaison64B.',
 'Le GPU écrit les données ; le CPU les lit après la complétion et le blit retour.',
 'Compteur atomic add ; 64B de sentinelles avant/après et queue inutilisée A5.',
 'Le natif écrit coord² ; NAK écrit .5*coord²+.125 en RGB, alpha1.',
 'La référence indépendante CPU calcule cette formule en double à partir de',
 'chaque coordonnée capturée. Cela vérifie l’arithmétique à tous les facteurs,',
 'sans prétendre reconstruire la connectivité des triangles sur le CPU.',
 f'Erreurs de valeurs CPU/sentinelles/queue : zéro. Erreur numérique max : {maxError:.12g}.',
 f'NAK facteur64 : {factor64["invocations"]} évaluations ; erreur CPU {factor64["max_error_vs_cpu_double"]:.12g}.',
 'Coordonnées natives/NAK : multisets exactement identiques, ordre atomique ignoré.',
 'Nombre d’évaluations observé (les doublons de coordonnées restent comptés) :']
for c in manifest['comparisons']:lines.append(f'  facteur{c["factor"]}: {c["invocations"]} ; écart affine natif/NAK {c["max_affine_value_difference"]:.12g}')
lines+=['',f'NAK capture SHA256 : {manifest["code_sha256"]}.',
 'NAK384B,24GPR, scratch/CRS0 ; variant décodé464B avec header80B.',
 'Le shader natif optimise son compteur par warp ; NAK fait un atomic par invocation.',
 'Ce sont des validations de résultat, aucun benchmark de performance.','',
 'RENDU — LIMITATION CONSERVEE',
 'Le test raster antérieur compare des triangles visibles de64x48 pixels.',
 'Facteur0 : patch supprimé ; facteur1 : oracle CPU indépendant, erreur<=5.961e-8.',
 'Aux facteurs supérieurs, le rendu NAK correspond au natif transformé par CPU',
 f'à {summary["NAK_native_comparison_max_error"]:.12g} près.',
 'Le facteur64 échoue toujours à la borne idéale de convexité, tolérance2e-6 :',
 '80 canaux natifs et67 NAK sous la borne. La capture directe passe au facteur64,',
 'mais ne prouve pas la cause exacte de cet écart de rasterisation/interpolation.',
 'L’oracle raster n’a pas été assoupli : son script conserve deux retours10.',
 'La capture ne remplace pas un oracle CPU indépendant de topologie/rasterisation.',
 'Quad, autres partitions, facteurs asymétriques, indexation/scaling restent ouverts.','',
 'REPRODUCTION DEPUIS bridge',
 'python3 tools/reproduce_tessellation_capture.py',
 'python3 tools/make_tessellation_report.py',
 'python3 tools/provenance.py',
 'python3 tools/make_resume.py',
 'Préconditions : compilateur Mesa/NAK déjà construit, envydis, Xcode et bibliothèque',
 'build/libKeplerProgramImport.dylib (voir commandes historiques des compilations).',
 f'Commandes exactes : {capture.relative_to(root)}/commands.json',
 f'Binaries, sources et empreintes figés : {capture.relative_to(root)}/manifest.json',
 'Rendu antérieur : python3 tools/reproduce_tessellation.py (retour10 attendu).',
 'Rendu/captures raster : results/tessellation-reproduction/manifest.json',
 f'SHA256 pilote inchangé : {manifest["driver_sha256"]}',
 'Le but global reste incomplet : results/hardware-coverage.json.','',
 'Contrat primaire Metal :',
 'https://developer.apple.com/library/archive/documentation/Miscellaneous/Conceptual/MetalProgrammingGuide/Tessellation/Tessellation.html']
(root/'TESSELLATION.txt').write_text('\n'.join(lines)+'\n');print('Updated TESSELLATION.txt and tessellation-summary.json; raster limitation retained')

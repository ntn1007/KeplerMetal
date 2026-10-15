#!/usr/bin/env python3
"""Evidence-calibrated compute report and full-goal coverage ledger."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import statistics

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/compute-reproduction')
args=parser.parse_args();folder=args.input.resolve();manifest=json.loads((folder/'manifest.json').read_text())
records=[]
for case in manifest['cases']:
    result=json.loads((root/case['result']).read_text())
    assert result['device']=='NVIDIA GeForce GTX 880M'
    assert result['mismatches']==0 and result['changed_guards']==0
    assert result['import']['contract_verified'] and result['import']['events']
    assert all(e['imported_code_identical'] for e in result['import']['events'])
    assert hashlib.sha256((root/case['code']).read_bytes()).hexdigest()==case['code_sha256']
    metrics={}
    fields=[key for key,value in result['samples'][0].items() if key.endswith('_ms')]
    for field in fields:
        samples=[s[field] for s in result['samples']]
        metrics[field]={'mean':statistics.mean(samples),'sample_sd':statistics.stdev(samples),
                        'median':statistics.median(samples),'min':min(samples),'max':max(samples)}
    records.append({'label':case['label'],'result':case['result'],'code':case['code'],
                    'code_sha256':case['code_sha256'],'kind':result.get('kind','memory'),
                    'elements':result.get('elements'),'warmups':result['warmups'],'trials':result['measured_trials'],
                    'mismatches':0,'changed_guards':0,'metrics_ms':metrics,
                    'policy':result['policy'],'initial_upload_wall_ms':result['initial_upload_wall_ms'],
                    'final_readback_wall_ms':result['final_readback_wall_ms']})
    records[-1]['batch']=result.get('batch',1)
    if result.get('kind')=='tiled_counted':
        assert result['dispatch_count_verified']
        records[-1]['verified_gpu_dispatches']=result['dispatch_counter']
byLabel={record['label']:record for record in records}
for name in ['fp64-resident','atomic32-resident','shuffle-resident','shared_reduce-resident',
             'tiled_matmul-1024-resident','tiled_matmul-1024-roundtrip']:
    assert name in byLabel
assert manifest['driver_unchanged']
summary={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':records,
         'driver_sha256':manifest['driver_after_sha256'],'driver_unchanged':True,
         'global_hardware_goal_complete':False,
         'scope':'sample-qualified compute functions and memory transports through the installed driver; no system driver or Metal-family qualification'}
clockPath=root/'results/clock-probe.json'
if clockPath.exists():
    clock=json.loads(clockPath.read_text())
    if clock.get('failures')==0:
        summary['shader_clock_observation']={'result':'results/clock-probe.json','scope':'counter read qualified; cycles/command ns is only a lower frequency estimate, not a driver query',
            'cycle_delta_min':min(s['delta_cycles'] for s in clock['samples']),
            'cycle_delta_max':max(s['delta_cycles'] for s in clock['samples']),
            'command_ms_min':min(s['gpu_command_ms'] for s in clock['samples']),
            'command_ms_max':max(s['gpu_command_ms'] for s in clock['samples'])}
(root/'results/compute-summary.json').write_text(json.dumps(summary,indent=2)+'\n')

def row(category,status,tested,remaining,evidence):
    return {'category':category,'status':status,'tested_scope':tested,'remaining_requirements':remaining,'evidence':evidence}
coverage=[
 row('Device identity and build provenance','verified_inventory','GTX 880M PCI 10de:1198, GK104/SM30; pinned compiler and exact artifacts',
     'Refresh changing machine/driver facts on each system change',['results/provenance.json','results/driver-inventory.json']),
 row('Application-local native program import','sample_qualified','Version-7/8 compute container, code bytes verified, decoded registers verified, payload retained with pipeline; caller pool can end before dispatch',
     'General metadata specification, non-compute stages, incompatible-driver handling, sustained and concurrent workloads',['src/KeplerProgramImport.mm',str((folder/'manifest.json').relative_to(root))]),
 row('CPU/GPU memory and DMA','sample_qualified','Shared, Managed, Private, GPU blits, explicit Managed synchronization, NoCopy page registration and CPU-visible results',
     'Full 8 GiB coverage, aliasing, memory pressure/eviction, larger buffer spans, lifecycle stress',['results/compute-summary.json']),
 row('FP32 arithmetic and FMA','sample_qualified','Addition plus tiled matrix multiply on 64..1024 square matrices; independent double CPU reference and Accelerate',
     'Other shapes, operations, rounding/NaN/Inf/subnormal behavior and general math library',['tools/kepler_compute_suite.c',byLabel['tiled_matmul-1024-roundtrip']['result']]),
 row('FP64 hardware arithmetic','sample_qualified','Native DADD, 1041 doubles with below-float32 precision; exact CPU comparison',
     'Multiply/FMA/divide/sqrt, rounding and special values; reusable high-level API, not MSL double syntax',[byLabel['fp64-resident']['result']]),
 row('Global atomic arithmetic','sample_qualified','UInt32 RED.ADD from 1025 threads; four launches accumulate 4100 with untouched guards',
     'UInt64, compare-exchange, float32, shared atomics, ordering and contention variants',[byLabel['atomic32-resident']['result']]),
 row('Subgroups','sample_qualified','SHFL butterfly xor16 on complete 32-lane warps',
     'Other shuffle modes, ballot/vote/reductions, partial active masks and divergence',[byLabel['shuffle-resident']['result']]),
 row('Shared memory and workgroup barriers','sample_qualified','512-byte reduction across four warps and 2048-byte tiled GEMM across eight warps; native barrier/membar instructions',
     'Full 48 KiB physical capacity, bank modes, shared atomics, subgroup/workgroup ordering corner cases',[byLabel['shared_reduce-resident']['result'],byLabel['tiled_matmul-1024-resident']['result']]),
 row('Grid geometry and control flow','partly_qualified','One-dimensional groups 32/128/256; bounds, loops, reconvergence fields 9/11 empirically qualified',
     '2D/3D grids, maximum group sizes, deeper control stacks, local/scratch memory and register spilling',['tools/kepler_compute_suite.c']),
 row('Texture/sampler/surface units','pending','No new NAK texture backend tested',
     '1D/2D/3D/cube/array sampling, filtering, formats, texture stores, gather, compression, coherent resource binding',[]),
 row('Rasterization and render state','pending','Desktop currently uses installed driver; that is not new-driver validation',
     'NAK vertex/fragment import; offscreen render CPU oracle; blending, depth/stencil, MRT, MSAA and tessellation paths',[]),
 row('Video engines','pending','No codec engine validation in this phase',
     'Map physically present decode/encode engines and test their macOS transport with hardware-only requirements',[]),
 row('Display and system integration','pending','System driver and OCLP preserved',
     'Display/WindowServer integration, outputs, suspend/resume and recovery; no new system driver delivered',[]),
 row('Clock/power/thermal management','pending','Existing driver remains owner; no registers or clocks changed',
     'Native shader counter read sampled; driver frequency query, thermal/power state and causes of performance variation remain unqualified',['results/clock-probe.json']),
 row('Metal API coverage','pending','Declared families remain Mac1; no Metal3/4 qualification',
     'Feature-by-feature API mapping, shader frontend coverage, protocol objects and conformance; never qualify a family by changing its identifier',['../results/metal-capabilities.json']),
 row('OpenCL and LLM application path','pending','OpenCL GPU compiler and old llama Metal failures remain documented; NAK GEMM now works',
     'Reusable tensor backend, quantized kernels and full model inference with equal-model CPU/GPU benchmarks',['../../opencl-880m/RAPPORT.txt']),
]
ledger={'objective':'Toutes les fonctionnalites materielles de la GTX 880M sur macOS, avec maximum API applicable et delestage CPU',
        'constraints':['No system driver, OCLP, protections or hardware register changes'],
        'complete':False,'coverage':coverage,
        'physical_reference':'https://docs.nvidia.com/cuda/archive/10.2/cuda-c-programming-guide/index.html#compute-capabilities',
        'physical_limits_note':'SM30: 63 registers/thread, up to 48 KiB shared/block, warps of 32; native tensor cores and native FP16 arithmetic are not SM30 features. Published limits are not runtime validation.'}
for summaryName in ('graphics-summary.json','render-state-summary.json','vertex-io-summary.json','resource-summary.json','tessellation-summary.json','video-summary.json','native-execution-summary.json','atomic64-summary.json','image-load-summary.json','shared-units-summary.json','import-audit-summary.json'):
    graphicsPath=root/'results'/summaryName
    if graphicsPath.exists():
        graphics=json.loads(graphicsPath.read_text())
        updates={row['category']:row for row in graphics.get('coverage_updates',[])}
        ledger['coverage']=[updates.get(row['category'],row) for row in ledger['coverage']]
(root/'results/hardware-coverage.json').write_text(json.dumps(ledger,indent=2)+'\n')

lines=['KEPLERMETAL — mémoire, calcul et couverture du matériel','Relevé : '+summary['collected_at'],'',
       'Cette étape ajoute une bibliothèque locale réutilisable et cinq tests matériels NAK.',
       'Le but complet reste ouvert. Aucun pilote système ni réglage OCLP n’est modifié.','',
       'Bibliothèque : build/libKeplerProgramImport.dylib, interface src/KeplerProgramImport.h.',
       'KPCreatePipeline importe notre programme SM30 dans notre processus, avec le pilote',
       'installé comme propriétaire des allocations, commandes et fences. Les payloads',
       'sont retenus avec le pipeline. Les tests exécutent après fermeture du pool qui',
       'contenait les données d’import. KPCreateHostBuffer crée les buffers de staging',
       'Managed ou NoCopy Shared à partir de pages CPU alignées.','',
       'Fonctions réellement exécutées et comparées au CPU :',
       '- FP64 : addition native DADD de 1041 doubles. Les valeurs 1/-1 comportent des',
       '  variations 2^-42/2^-44 ; les arrondir en FP32 ne donnerait pas les réponses.',
       '- UInt32 atomiques : RED.ADD de 1025 threads, résultat accumulé 4100 après',
       '  quatre lancements. Les gardes restent intactes.',
       '- SHFL xor16 : permutation entre les 32 lanes d’un warp, 1024 résultats exacts.',
       '- Mémoire partagée : somme 8384, 128 threads/quatre warps, 512 octets, barrières',
       '  matérielles conservées (le premier cas à un seul warp avait été optimisé).',
       '- SGEMM par tuiles 16x16 : 256 threads/huit warps et 2048 octets partagés,',
       '  matrices 64, 128, 256, 512 et 1024. Les matrices finales sont pseudo-aléatoires',
       '  avec des valeurs dyadiques indépendantes, pour éviter une périodicité courte.',
       '  Référence indépendante : accumulation scalaire FP64, puis Accelerate SGEMM.',
       '  Zéro différence dans cette fixture, zéro garde modifiée.',
       'La FP64 est exposée par notre programme NIR/NAK ; aucune prise en charge MSL',
       'double ou qualification complète IEEE/Metal n’est annoncée.','',
       'Preuves : code importé identique, taille/registres relus dans le variant du',
       'pilote, commandes terminées, résultat CPU indépendant et contrôle des gardes.',
       'Envytools reconnaît les instructions DADD, RED.ADD, SHFL, barrières/membar,',
       'LDS/STS et FFMA sans instruction inconnue.','',
       'Mémoire : Shared, Managed, Private et Private + staging NoCopy passent chacun',
       'les essais résidents et avec copies à chaque appel. Les pages NoCopy permettent',
       'un retour GPU vers une allocation CPU existante ; l’identité contents est vérifiée.',
       'Les allocations demandées ne sont pas une mesure de la VRAM physique totale.','',
       'SGEMM 1024 x 1024, moyenne +/- écart-type, millisecondes :',
       '3 échauffements, 9 essais ; CPU Accelerate avec VECLIB_MAXIMUM_THREADS=4.',
       'La compilation, les allocations initiales et la validation sont hors chrono.']
for policy in ['resident','roundtrip']:
    record=byLabel['tiled_matmul-1024-'+policy];metrics=record['metrics_ms']
    lines += ['',policy+' :']
    for key,label in [('cpu_blas_wall_ms','CPU Accelerate durée'),('cpu_blas_consumed_ms','CPU Accelerate temps CPU'),
                      ('gpu_command_ms','Commande GPU'),('compute_submit_wait_wall_ms','Calcul GPU avec soumission/attente'),
                      ('upload_wall_ms','Copies des entrées/reset'),('readback_wall_ms','Retour/copie sortie'),
                      ('wall_with_copies_ms','Parcours GPU mesuré'),('host_cpu_with_copies_ms','Temps CPU hôte consommé')]:
        metric=metrics[key];lines.append(f"  {label} : {metric['mean']:.6f} +/- {metric['sample_sd']:.6f}")
    ratio=metrics['cpu_blas_wall_ms']['mean']/metrics['wall_with_copies_ms']['mean']
    lines.append(f"  Rapport des durées CPU/GPU sur ce test : {ratio:.3f}.")
    if policy=='resident':lines.append('  Upload initial et retour final exclus, consignés séparément dans le résultat brut.')
    else:lines.append('  Copies/reset, soumission/attente et retour inclus à chaque appel ; résultat et gardes vérifiés après chaque essai.')
lines += ['', 'Le temps CPU consommé est user+system de ce processus, tous ses threads :',
          'il ne mesure pas l’usage CPU de toute la machine. Les petites opérations',
          'et certaines autres tailles restent plus lentes sur GPU. Aucun gain global',
          'd’application, d’interface ou d’inférence LLM n’est déduit de ce benchmark.','',
          'Variabilité et lots de commandes :',
          'Un essai résident du même code a pris ~56 ms contre ~13-14 ms dans d’autres',
          'essais. L’assemblage est identique et les résultats sont corrects. Les',
          'copies/remises en résidence peuvent changer le comportement, mais la',
          'cause exacte (fréquence, attente, placement mémoire) n’est pas prouvée.',
          'Une sonde NAK de CLOCK/CLOCKHI exécute un nombre stable de cycles (~27,2 M)',
          'avec des durées de commande différentes. La fréquence calculée à partir',
          'de toute la commande reste une estimation basse, pas une lecture DVFS.',
          'Aucun état de fréquence, registre matériel ou réglage d’énergie n’est changé.']
for batch in (1,4,12):
    record=byLabel.get(f'tiled_counted-1024-batch{batch}')
    if not record:continue
    metrics=record['metrics_ms'];cpu=metrics['cpu_blas_wall_ms']['mean'];gpu=metrics['compute_submit_wait_wall_ms']['mean']
    host=metrics['host_cpu_ms']['mean']
    lines += [f"Lot {batch}, temps par SGEMM : GPU {gpu:.6f} ms, CPU {cpu:.6f} ms, CPU hôte {host:.6f} ms.",
              f"  Compteur atomique sur GPU : {record['verified_gpu_dispatches']} lancements vérifiés ; sorties/gardes exactes."]
lines += ['',
          'Versions et reproduction :',
          'Mesa 26.2.4 : 96cb43121031992b85767f9c1be8f3f48e22b1d2.',
          'OpenNVDA : da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5 (frontend AIR de l’addition).',
          'Envytools : f102b82381f3f11cee113d16374c87091db039d9.',
          'Les autres kernels sont créés en NIR puis compilés par NAK SM30.',
          'Le compilateur local possède désormais un correctif texture séparé :',
          'src/mesa-26.2.4-macos-texture-import.patch ; voir GRAPHIQUE.txt.',
          'SHA256 GeForceMTLDriver, avant et après : '+manifest['driver_after_sha256'],
          'Empreintes des kernels : '+str((folder/'manifest.json').relative_to(root)),
          'Outils et sources : results/provenance.json. Commandes exactes : '+str((folder/'commands.json').relative_to(root)),
          'Diagnostic CLOCK/CLOCKHI : commandes séparées dans results/clock-build-run.json.',
          'Depuis bridge : python3 tools/reproduce_compute_suite.py',
          'Préconditions : sources épinglées et build Mesa isolé existants. Aucun installateur système.','',
          'Couverture complète : results/hardware-coverage.json. Les domaines encore',
          'ouverts incluent rendu/texture/tessellation, vidéo, grilles 3D, mémoire locale',
          'et spills, étendue VRAM, formats/types supplémentaires, intégration système',
          'et couverture des API Metal. Les déclarations Mac1/Metal3/Metal4 restent',
          'celles du pilote installé ; ce composant est utilisable par une application',
          'qui l’intègre explicitement. Le pilote complet demandé reste à développer.','']
(root/'CALCUL_MATERIEL.txt').write_text('\n'.join(lines))
print('Saved CALCUL_MATERIEL.txt, compute-summary.json and hardware-coverage.json')

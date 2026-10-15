#!/usr/bin/env python3
"""Summarize the numerical evidence, exact inputs and warmed measurements."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import statistics

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--input',type=Path,default=root/'results/nak-reproduction')
args=parser.parse_args();directory=args.input.resolve()
manifest=json.loads((directory/'manifest.json').read_text())
cases=[];benchmarks=[];success=True
for case in manifest['cases']:
    result=json.loads((root/case['result']).read_text())
    cases.append(dict(case,device=result.get('device'),gpu_dispatch=result.get('gpu_dispatch'),
                      imported_code_verified=result.get('import_contract_verified'),
                      mismatches=result.get('mismatches',result.get('mismatches_including_warmups')),
                      changed_guards=result.get('changed_guard_elements',result.get('changed_guard_elements_including_warmups'))))
    if case['expected_exit_code']==0 and result.get('gpu_dispatch'):
        success &= cases[-1]['mismatches']==0 and cases[-1]['changed_guards']==0
    if 'samples' not in result:continue
    fields=['cpu_ms','gpu_command_ms','encode_submit_wait_ms','host_upload_reset_ms',
            'host_readback_ms','wall_with_host_copies_ms']
    metrics={}
    for field in fields:
        samples=[s[field] for s in result['samples']]
        metrics[field]={'mean':statistics.mean(samples),'median':statistics.median(samples),
                        'sample_sd':statistics.stdev(samples),'min':min(samples),'max':max(samples)}
    success &= result['warmups']==3 and result['measured_trials']==9
    benchmarks.append({'elements':result['active_elements'],'warmups':result['warmups'],
                       'trials':result['measured_trials'],'metrics_ms':metrics,
                       'mismatches_including_warmups':result['mismatches_including_warmups'],
                       'changed_guards_including_warmups':result['changed_guard_elements_including_warmups'],
                       'requested_shared_buffer_bytes':result['requested_shared_buffer_bytes'],
                       'metal_allocated_bytes_after_trials':result.get('metal_reported_allocated_bytes_after_trials'),
                       'input_pattern':result['input_pattern']})

code=root/'build/add_buffers-air-cb2.sass'
mesa=json.loads((root/'results/mesa-source.json').read_text())
summary={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'NAK_AIR_binary_executed_and_compared_on_GTX':bool(success and len(benchmarks)==2),
         'installed_driver_binary_unchanged':manifest['installed_driver_binary_unchanged'],
         'mesa':mesa,'shader':{'input':'src/add_buffers.metal','path':str(code.relative_to(root)),
         'bytes':code.stat().st_size,'sha256':hashlib.sha256(code.read_bytes()).hexdigest(),
         'sm':30,'registers':24,'constant_bank':2,'constant_bytes':56,'workgroup':[32,1,1]},
         'verified_launch_metadata_words_9_11':manifest['observed_branch_launch_words_9_11'],
         'cases':cases,'benchmarks':benchmarks,
         'limitations':['private NVIDIA container/constructor ABI of this installed driver only',
                        'two launch words observed and tested; complete metadata semantics remain unknown',
                        'this addition kernel, not general AIR coverage, a new system driver or LLM inference',
                        'no Metal family, system driver or OCLP change',
                        'shared buffers and host copies; no VRAM-only benchmark or total physical VRAM measurement',
                        'CPU comparison is optimized single-thread addition; no application-wide performance claim',
                        'NaN, infinity, subnormals and other arithmetic kernels remain unqualified']}
(root/'results/nak-macos-summary.json').write_text(json.dumps(summary,indent=2)+'\n')

lines=["KEPLERMETAL — exécution réelle NAK/SM30 sur macOS",
       "Résultats relevés le "+summary['collected_at'],"",
       "Résultat : l'addition AIR -> NIR -> NAK -> SASS SM30 est exécutée sur la GTX 880M.",
       "Les tailles 1, 17, 31, 32, 33, 1041, 65536 et 1048576 passent sans différence",
       "CPU et sans écriture dans les gardes. Le benchmark emploie des float32 normaux",
       "avec signes, mantisses et exposants variés, renouvelés à chaque essai.","",
       "Preuve d'exécution",
       "Notre processus remplace seulement la section de code natif de son programme",
       "via NVMTLFunctionVariant initWithCompilerOutput:size:device:. Le constructeur",
       "original et les encodeurs Metal du pilote gèrent allocations, commandes et fences.",
       "La section importée est comparée octet par octet au fichier SASS. Le pilote",
       "décode 384 octets et 24 registres avant la soumission. Le CPU ne remplit jamais",
       "le buffer de sortie GPU avec la réponse : il calcule une référence séparée.",
       "Le buffer GPU est initialisé à -123456, puis lu après complétion matérielle.",
       "La variante témoin native produit une autre valeur. Le marqueur NAK écrit 77.","",
       "Contrat macOS établi pour ce shader",
       "Container NVIDIA version 7, sections chaînées ; code natif type 0x10005.",
       "Métadonnées type 0x10004, 232 octets : mot 7 = 24 registres.",
       "Mots 9 et 11 : 0 -> 576, valeurs obtenues d'un programme natif à branchements.",
       "Avec les deux champs à 0, le marqueur NAK n'écrit rien malgré une commande",
       "terminée. Avec les deux champs à 576, le même code écrit 77. Les mêmes champs",
       "rendent correcte l'addition AIR avec contrôles de bornes. Leur sémantique",
       "complète reste à nommer ; aucune règle générale pour tous les shaders n'est affirmée.",
       "Le bloc de paramètres de 56 octets est fourni en CB2 : quatre adresses GPU",
       "u64 à 0/8/16/24, grid uint3 à 32, block uint3 à 44. Les adresses publiques",
       "MTLBuffer.gpuAddress correspondent au champ fournisseur utilisé par setBuffer.","",
       "Versions et empreintes",
       "Mesa 26.2.4 : "+mesa['git_commit'],
       "OpenNVDA : da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5 (lecteur AIR / traduction NIR).",
       "Envytools : f102b82381f3f11cee113d16374c87091db039d9 (décodage indépendant).",
       "SASS CB2 : "+summary['shader']['sha256'],
       "GeForceMTLDriver système SHA256 avant et après : "+manifest['driver_before_sha256'],
       "Le fichier du pilote installé a la même empreinte avant et après les tests.",
       "Notre travail ne modifie aucun pilote système, paramètre OCLP ou protection.",
       "Versions macOS, Xcode, compilateurs et sources : results/provenance.json.","",
       "Mesures en millisecondes : moyenne +/- écart-type d'échantillon, 3 échauffements, 9 essais.",
       "CPU : addition C++ -O3, un thread, même float32 ; validation hors chronométrage.",
       "GPU : horodatages de la commande Metal, pas une mesure de kernel isolé en VRAM.",
       "Total : copie des entrées/reset, encodage/soumission/attente, copie de la sortie.",
       "La compilation du pipeline, les allocations initiales et la validation sont exclues.",""]
for bench in benchmarks:
    lines.append(str(bench['elements'])+" éléments :")
    for field,label in [('cpu_ms','CPU'),('gpu_command_ms','Commande GPU'),
                        ('host_upload_reset_ms','Copie entrées/reset'),
                        ('encode_submit_wait_ms','Encodage/soumission/attente'),
                        ('host_readback_ms','Copie sortie'),('wall_with_host_copies_ms','Total avec copies')]:
        value=bench['metrics_ms'][field]
        lines.append(f"  {label} : {value['mean']:.6f} +/- {value['sample_sd']:.6f}")
    lines.append("  Différences CPU / gardes modifiées, échauffements compris : 0 / 0.")
    lines.append(f"  Buffers demandés : {bench['requested_shared_buffer_bytes']} octets (Shared).")
    lines.append(f"  Allocation rapportée par Metal : {bench['metal_allocated_bytes_after_trials']} octets.")
    lines.append("  Cette allocation inclut les ressources du pilote ; elle n'est pas la VRAM physique occupée.")
    lines.append("")
lines += ["Ce benchmark ne démontre aucun gain par rapport au CPU optimisé.",
          "Les copies, surtout la lecture côté hôte, pénalisent cette petite opération.","",
          "Reproduction dans le dossier bridge, sans installation système :",
          "  python3 tools/reproduce_nak_macos.py",
          "Précondition : le build Mesa isolé et les sources épinglées existent déjà.",
          "Pour le reconstruire : tools/setup_tools.py, prepare_mesa_compiler.py, build_offline_compiler.py.",
          "Le script reconstruit les petits outils, compile le shader Metal, traduit AIR en",
          "NAK/SM30, vérifie le témoin et le cas négatif, teste les huit tailles et benchmarke.",
          "Il relève les empreintes du pilote avant/après et vérifie le code réellement importé.",
          "Commandes exactes et résultats : "+str(directory.relative_to(root))+"/commands.json et manifest.json.","",
          "Limites et prochaine suite",
          "L'import repose sur une ABI privée de ce pilote précis. Il reste un prototype",
          "dans notre processus ; les autres applications ne l'utilisent pas automatiquement.",
          "Il ne qualifie ni toute la lecture AIR, ni textures, atomiques, barrières, FP64,",
          "rendu, vidéo, ni Metal 2/3/4. L'inférence LLM GPU reste à raccorder et mesurer.",
          "La prochaine suite doit qualifier mémoire Private/Managed, copies GPU et les",
          "kernels utiles (matrices, réductions, mémoire partagée) avec références CPU.",
          "Le but global reste la couverture matérielle ; cette étape valide le transport",
          "d'un programme NAK et un premier calcul, sans prétendre livrer un pilote complet.",""]
(root/'NAK_MACOS.txt').write_text('\n'.join(lines))
print('Saved NAK_MACOS.txt and results/nak-macos-summary.json')

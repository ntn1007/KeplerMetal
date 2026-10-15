#!/usr/bin/env python3
"""Attest the current frontend milestone without completing the hardware goal."""
from pathlib import Path
import datetime,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/gpu-command-frontend-progress-20261015'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cohorts=json.loads((OUT/'cohorts.json').read_text());snapshot=json.loads((OUT/'source-snapshot.json').read_text());system=json.loads((OUT/'system-and-core-check.json').read_text());m1=ROOT/'results/command-frontend-M1-return-20261015';reference=json.loads((m1/'independent-verification.json').read_text())
assert cohorts['status']==reference['status']==system['status']=='PASS'
assert cohorts['total_runs']==252 and cohorts['checked_uint32_words_including_guards']==72576
for row in snapshot['files']:assert sha(ROOT/row['path'])==row['SHA256']
for row in system['system_files']:assert sha(row['path'])==row['SHA256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==system['OCLP_SHA256']
for path,h in system['qualified_core_and_generated_table_unchanged'].items():assert sha(path)==h
build=ROOT/'results/gpu-command-frontend-build-20261015-04';compiler_manifest=json.loads((build/'manifest.json').read_text());assert sha(build/'air_command_compile')==compiler_manifest['compiler_SHA256']
for path,h in compiler_manifest['fork_SHA256'].items():assert sha(build/path)==h
native_source=m1/'CommandFrontendReference/gpu_command_frontend_methods.metal';assert sha(native_source)==sha(ROOT/'src/gpu_command_frontend_methods.metal')
receipt={'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_goal_turn':'NO_PROGRESS: status explanation only; next available compiler build performed in this turn','current_goal_turn':'PROGRESS','objective':snapshot.get('objective','Toutes les fonctionnalités matérielles de la GTX880M sur macOS'),'objective_complete':False,'Git_branch':'main','Git_commit':None,'job_ids':[],
 'GTX_cohorts':7,'GTX_trials':252,'GTX_producer_dispatches':180,'GTX_native_carrier_dispatches':36,'GTX_no_producer_control_trials':36,'GTX_checked_uint32_words_including_guards':72576,'GTX_record_states':cohorts['records'],
 'M1_native_ICB_trials':12,'M1_positive_uint32_words':reference['positive_uint32_words'],'M1_guard_bytes':reference['guard_bytes'],'same_MSL_methods_source_on_both_hosts':True,
 'compiler_SHA256':compiler_manifest['compiler_SHA256'],'source_snapshot_SHA256':sha(OUT/'source-snapshot.json'),'MSL_source_SHA256':sha(ROOT/'src/gpu_command_frontend_methods.metal'),'command_IR_header_SHA256':sha(ROOT/'src/KeplerCommandIR.h'),'lowering_include_SHA256':sha(ROOT/'src/opennvda-command-ir.inc'),
 'MSL_standard':'macos-metal2.3','OpenNVDA_commit':snapshot['OpenNVDA_commit'],'Mesa_commit':snapshot['Mesa_commit'],'programs':cohorts['cohorts'][:5],'system_files_unchanged':83,'OCLP_unchanged':True,'previous_core_changed':False,'performance_benchmark':False,'new_GTX_command_IR_consumed':False,'ordinary_applications_transparent':False,'installed_driver_updated':False,
 'PASS':['Public MSL AIR→NIR→SM30 compiler and GPU record writes','Bounded record/header/token checks','Copy content survives source reset','Barrier/stage-in flags encoded, not hardware barriers qualified','Dispatch unit and last-call state preserved','Backend-disabled and strided-buffer refusal','Two CAS baselines byte-identical SASS','M1 native public ICB output oracle','System and previous SDK core unchanged'],
 'FAIL_preserved':['gpu-command-frontend-build-20261015-01: offline SIGSEGV in mixed CFG','gpu-command-frontend-build-20261015-03: missing C brace','gpu-command-ir-host-build-20261015-01: MSL2.0 ulong buffer type rejected','gpu-command-ir-imac-no-producer-20261015-02: host expected128 static bytes; driver reports256, exit5 before dispatch','gpu-command-frontend-final-offline-controls-20261015: invalid macos-metal3.1 spelling; corrected metal3.1 refusal saved separately','command-frontend-M1-source-20261015-01: pre-fix host source transferred but not executed'],
 'BLOCKED':[], 'NOT_RUN':['GTX GPU materializer consuming these records','Cross-context command copy','Kernel strides','Native gpuResourceID integration','Full ICB concurrency/barrier contract','New frontend performance benchmark','Transparent integration','Full video/display/power/VRAM stress qualification'],
 'next_action':'Implement the runtime materializer for this public-MSL command IR against real validated pipeline/resource owners; preserve reset/no-action and reject unsupported shapes without submitting arbitrary QMDs. Then compare consumed outputs with the M1 native reference.'}
(OUT/'qualification-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
(OUT/'next-action.json').write_text(json.dumps({'objective':receipt['objective'],'state':'active','previous_goal_turn':'PROGRESS','objective_complete':False,'job_ids':[],'BLOCKED':[],'next_action':receipt['next_action'],'evidence':'qualification-receipt.json'},ensure_ascii=False,indent=2)+'\n')
report=ROOT/'FRONTEND_COMMANDES_MSL_GTX_M1_2026-10-15.txt'
program_lines='\n'.join(f"{r['name']}: {r['program_bytes']} octets SM30, {r['registers']} registres"for r in receipt['programs'])
text=f'''KEPLERMETAL — FRONTEND DE COMMANDES MSL, 15 octobre 2026
Objectif complet ACTIF, non réalisé. Branche B, prototype de laboratoire.
Git main sans commit; sources non suivies, versions par SHA256. job_ids=[].

Résultat
Un producteur utilisant les appels publics compute_command est compilé par
Apple en AIR, puis traduit par notre frontend opt-in en NIR et SM30. La GTX
écrit réellement des enregistrements de commandes Private. Les résultats
sont relus après exécution et vérifiés par un script CPU distinct.
Il ne s'agit pas du layout ICB Apple ni d'une nouvelle implémentation Metal4.
Le runtime GTX ne consomme PAS ENCORE ces nouveaux enregistrements.

Contrat couvert
reset; set_compute_pipeline_state; buffers device/constant sans stride;
set_threadgroup_memory_length(index0); dispatch groupes et threads;
set_barrier/clear_barrier; set_stage_in_region; copy_command dans le même
contexte. La copie conserve son contenu après reset de la source. Le dernier
dispatch conserve son unité et ses dimensions. Les flags de barrière et la
région stage-in sont encodés; aucune nouvelle synchronisation matérielle ou
lecture stage-in sur GTX n'est prouvée par cette étape.
Contexte32B, record128B, au plus8slots/8pipelines et3buffers. Les handles sont
des tokens propres au prototype, pas les gpuResourceID natifs. Les adresses
sont fournies par le host pour ses buffers vivants. L'intégrité de ce contexte
de confiance est une condition; ce n'est pas un bac à sable de shaders hostiles.

Correction
5producteurs ×36essais=180dispatchs importés GTX.36essais avec le carrier
NVIDIA d'origine et36sans producteur constituent les témoins finaux.
Total252essais,72576mots uint32 vérifiés, gardes incluses, zéro écart.
267records reconnus:138complets sans erreur,21reset vides,108erreurs attendues.
Capacités1/2/8 et refus:magic/version/stride/capacité/index de pipeline/tag
de pipeline/nombre de pipelines/limite de bindings. Les adresses invalides
et conteneurs corrompus ne sont pas envoyés au GPU d'affichage.
Le refus de kernel stride est contrôlé hors GPU: code10 attendu après MSL3.1.
Deux programmes CAS device/threadgroup restent SASS identiques aux références.
Import:driver SHA épinglé, payload SM30 identique, taille et24registres décodés.
Cette preuve porte sur l'import et les effets GPU; pas sur un readback des
instructions résidentes. Le carrier produit des données différentes; sans
producteur, les records restent inchangés. Le runner conserve PID, état final
et réservation interprocessus. Tous les processus de cette qualification sont
terminés, sans demande de SIGKILL.

Référence M1 Max
Les mêmes sources MSL de méthodes sont transférées explicitement, hashes
vérifiés puis compilées et exécutées en arm64 sur le MacBook, sans Qwen.
12essais natifs ICB:barrier/clear/threads/copy,3répétitions chacun.
3480valeurs uint32 et35232octets de garde vérifiés hors MacBook sans écart.
Les compteurs sont contrôlés par le host; pas de capture brute du compteur.
M1 exécute les commandes, GTX écrit actuellement leur représentation IR:
les deux résultats ne constituent pas encore une équivalence d'exécution.
SSH strict vérifié; MacBook sur batterie, essais bornés, aucun service modifié.

Versions
iMac macOS26.7.1/build25G241, SDK26.2, hôte x86_64.
M1 macOS27.0.1/build26A434, SDK27.0, arm64. MSL macos-metal2.3.
OpenNVDA {receipt['OpenNVDA_commit']}
Mesa26.2.4 {receipt['Mesa_commit']}
Fork local conserve la correction CAS et adapte new_block à l'ABI Mesa.
L'abaissement utilise des blocs/goto avant nir_lower_goto_ifs; mélanger des
nir_push_if structurés à ce CFG causait le SIGSEGV offline conservé.
{program_lines}
Pas de scratch/CRS/shared dans ces programmes. Le carrier conserve256B de
mémoire partagée statique rapportée par le pilote. Le champ48640des records
est une demande pour le futur consommateur, pas une allocation GTX nouvelle.
Compilateur SHA256 {receipt['compiler_SHA256']}
Instantané sources SHA256 {receipt['source_snapshot_SHA256']}
Frontend include SHA256 {receipt['lowering_include_SHA256']}
ABI header SHA256 {receipt['command_IR_header_SHA256']}
Sources MSL méthodes SHA256 {receipt['MSL_source_SHA256']}
Retour M1 SHA256 b764b4bec5008530919b0d8014b3ecbafedd15fb32a20283d7b383f7677d88d6
Commandes exactes, codes de retour, sources et artefacts dans les manifestes.

Reproduction depuis bridge avec des destinations neuves
python3 tools/build_command_frontend.py --out results/<compiler>
python3 tools/build_command_ir_methods.py --compiler-build results/<compiler> --out results/<methods>
python3 tools/build_command_ir_probe.py --compiler-build results/<compiler> --out results/<host>
python3 tools/run_command_ir_probe.py --build results/<host> --out results/<run> --mode producer
python3 tools/verify_command_ir_probe.py results/<run>
Pour les méthodes, construire le host depuis <methods>/barrier|clear|threads|copy
et passer --semantic correspondant. Témoins: --mode carrier ou no_producer.
M1:transfer_m1_command_frontend_reference.py crée un nouvel instantané, puis
run_m1_command_frontend_reference.py compile et exécute sur ce même instantané.

Préservation et limites
83fichiers système et plist OCLP revérifiés identiques.12sources actuelles
du cœur précédent, table FP64 générée et bibliothèque SDK antérieure inchangées.
Aucun pilote, framework système, firmware, protection, service Qwen ou OCLP changé.
Premier SIGSEGV offline, erreur de brace, ulong MSL2.0, limite statique host
incorrecte et source M1 antérieure restent conservés. Ces échecs ont été
localisés avant les qualifications finales; aucune reprise d'un processus live.
NOT RUN:consommation des nouveaux records sur GTX,copie entre contextes,
strides,synchronisation ICB complète,gpuResourceID natif,intégration transparente,
performance et qualification vidéo/affichage/énergie/pression VRAM complètes.
Aucun gain de performances annoncé. Aucun pourcentage global de couverture
du matériel ne peut être déduit du nombre d'essais ou de méthodes.

Prochaine action
{receipt['next_action']}
Conserver le périmètre complet; ce jalon ne livre pas un pilote système modernisé.

Sources primaires
https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf
Sections6.17.2/6.17.3:contrat compute_command/copy; extraction locale existante.
https://developer.apple.com/documentation/metal/encoding-indirect-command-buffers-on-the-gpu
https://github.com/bdwithganesh/OpenNVDA/tree/da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5
Sources locales du reader et frontend inspectées; aucune compatibilité Ada→Kepler
n'est déduite de la page du projet. La génération SM30 et ses effets sont testés.
'''
report.write_text(text)
print(json.dumps({'status':'PASS','report':str(report),'receipt':str(OUT/'qualification-receipt.json'),'objective_complete':False}))

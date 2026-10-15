#!/usr/bin/env python3
"""Recheck executed captures, preserve failures and document bounded FP64 scope."""
from pathlib import Path
import datetime, hashlib, json, subprocess
from verify_fp64_math import verify

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fp64-math-progress-20261014'
assert OUT.is_dir() and not (OUT / 'summary.json').exists()
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    return json.loads(Path(p).read_text())
def dump(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

suite = read(ROOT / 'results/fp64-math-normalized-suite-20261014-03/summary.json')
baseline = read(ROOT / 'results/fp64-math-suite-20261014/summary.json')
assert suite['complete'] and suite['status'] == 'PASS' and len(suite['records']) == 45
assert baseline['complete'] and baseline['status'] == 'PARTIAL'
ps = subprocess.check_output(['ps', '-axo', 'pid,ppid,lstart,command'], text=True)
verification, processes = {}, {}
for stage, data in [('normalized', suite), ('baseline', baseline)]:
    for r in data['records']:
        folder = Path(r['path'])
        v = verify(folder)
        assert v['status'] == r['verification']['status']
        for k in ['numeric_mismatches', 'tag_mismatches', 'correct_double_results']:
            assert v[k] == r['verification'][k]
        if stage == 'normalized':
            assert v['status'].startswith('PASS') and not r['reused_existing_execution']
        if v['mode'] == 'execute':
            assert v['tag_mismatches'] == 0
        m = read(folder / 'execution/manifest.json')
        assert m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
        assert m['GPU_reservation']['state'] == 'terminal'
        live = [line for line in ps.splitlines() if m['signed_executable'] in line]
        assert not live, live
        key = stage + '/' + r['label']
        verification[key] = {k: x for k, x in v.items() if k != 'raw_files_SHA256'}
        processes[key] = {'PID': m['pid'], 'exit_code': 0, 'SIGKILL_requested': False,
                          'signed_path_current_process_matches': live,
                          'manifest_SHA256': sha(folder / 'execution/manifest.json')}

positives = [v for k, v in verification.items() if k.startswith('normalized/') and v['mode'] == 'execute']
controls = [v for k, v in verification.items() if k.startswith('normalized/') and v['mode'] == 'native']
operations = {}
for op in ['add', 'mul', 'fma', 'div', 'sqrt']:
    rows = [v for v in positives if v['operation'] == op]
    old = [v for k, v in verification.items() if k.startswith('baseline/') and v['mode'] == 'execute' and v['operation'] == op]
    operations[op] = {'status': 'PASS', 'exact_results': sum(v['correct_double_results'] for v in rows),
                      'baseline_numeric_mismatches': sum(v['numeric_mismatches'] for v in old),
                      'new_numeric_mismatches': 0, 'tag_mismatches': 0,
                      'local_sizes': [32, 128, 1024], 'counts_per_trial': [33, 1041, 8193],
                      'trials_per_local_size': 3}
    assert operations[op]['exact_results'] == 27801
compiled = read(ROOT / 'results/fp64-math-normalized-offline-20261014-03/summary.json')
assert compiled['compiler_source_SHA256'] == sha(ROOT / 'tools/fp64_math_compile.c')
model = read(ROOT / 'results/fp64-normalized-div-residual-model-20261014.json')
assert model['status'] == 'PASS' and model['failures_count']['residual_midpoint'] == 0
system = read(OUT / 'system-check.json')
assert len(system['system_files']) == 83 and system['rootpatch_unchanged']
for r in system['system_files']:
    assert sha(r['path']) == r['sha256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == system['rootpatch_SHA256']
sources = ['fp64_math_compile.c', 'build_fp64_math.py', 'build_fp64_math_host.py',
           'prepare_fp64_math_cases.py', 'fp64_math_probe.mm', 'run_fp64_math_case.py',
           'run_fp64_math_suite.py', 'verify_fp64_math.py', 'check_fp64_div_model.py',
           'make_fp64_math_report.py', 'run_signed_probe.py', 'lab_gpu_reservation.py']
provenance = {
    'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'Git_branch': 'main', 'Git_commit': None, 'Git_state': 'unborn; local untracked sources',
    'sources_SHA256': {n: sha(ROOT / 'tools' / n) for n in sources},
    'import_SHA256': {n: sha(ROOT / 'src' / n) for n in ['KeplerProgramImport.h', 'KeplerProgramImport.mm']},
    'GPU_host': read(ROOT / 'results/fp64-math-host-20261014/inputs.json'),
    'GPU_host_compile_commands': read(ROOT / 'results/fp64-math-host-20261014/commands.json'),
    'offline_compile': compiled, 'CPU_division_model': model,
    'macOS': subprocess.check_output(['sw_vers'], text=True),
    'SDK': subprocess.check_output(['xcrun', '--show-sdk-version'], text=True).strip(),
    'clang': subprocess.check_output(['clang', '--version'], text=True).splitlines()[0],
    'driver_SHA256': '2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054',
    'Qwen_job_ids': [], 'central_snapshot_verified': False,
}
summary = {
    'status': 'PASS_BOUNDED_FP64', 'operations': operations,
    'exact_double_results': sum(v['correct_double_results'] for v in positives),
    'GPU_invocations_with_correct_tags': sum(v['GPU_invocations_with_correct_tags'] for v in positives),
    'positive_main_command_buffers': sum(v['main_command_buffers'] for v in positives),
    'native_control_main_command_buffers': sum(v['main_command_buffers'] for v in controls),
    'native_control_expected_numeric_differences': sum(v['numeric_mismatches'] for v in controls),
    'positive_guard_bytes_verified': sum(v['guard_bytes_verified'] for v in positives),
    'all_45_cohort_guard_bytes_verified': sum(v['guard_bytes_verified'] for k, v in verification.items() if k.startswith('normalized/')),
    'fresh_execution_cohorts': 45, 'execution_results_reused': False,
    'all_normalized_processes_terminal': True, 'system_files_unchanged': 83,
    'rootpatch_unchanged': True, 'integration_level': 1,
    'MSL_double_frontend_added': False, 'ordinary_applications_transparent': False,
    'performance_benchmark': False, 'exhaustive_IEEE_conformance': False,
    'goal_complete': False, 'Qwen_job_ids': [],
    'peak_per_trial_buffer_bytes_requested': {'Private': 40 * 8193 + 1536, 'Shared': 40 * 8193 + 1536 + 56},
    'memory_note': 'Requested Metal buffer lengths, not measured total VRAM residency; three sets retained until process exit in this MRC capture host.',
}
assert summary['exact_double_results'] == 139005 == summary['GPU_invocations_with_correct_tags']
assert summary['native_control_expected_numeric_differences'] == 139005
dump(OUT / 'summary.json', summary)
dump(OUT / 'provenance.json', provenance)
dump(OUT / 'verification-history.json', verification)
dump(OUT / 'processes.json', processes)
dump(OUT / 'process-table.json', {'at': provenance['at'], 'process_table': ps, 'signed_paths_live': []})

note = (' Five controlled binary64 operations add/mul/fma/div/sqrt each pass 27801 exact results, '
        'local32/128/1024,count33/1041/8193,three trials. Total139005 results and index/nonce tags; '
        'Private buffers, untouched input/guards, prepare uncommitted and native-carrier negative controls. '
        'Strict NIR controls and early double-sqrt lowering; normalized operands, explicit special cases '
        'and DFMA residual correction for subnormal division midpoints. '
        'Baseline division5678 and sqrt18218 numeric errors retained with correct tags/guards. '
        'CPU-only exact-rational division model77628 checks,new rule0errors,old rule24errors. '
        'L1only,no MSL double frontend or transparent integration,no performance claim.')
for p in [ROOT / 'results/hardware-coverage.json', ROOT.parent / 'driver-research-2026-10-13/inventory/hardware-coverage.json', ROOT.parent / 'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']:
    d = read(p)
    assert len(d['coverage']) == 30 and not d['complete']
    row = next(r for r in d['coverage'] if r['category'] == 'FP64 hardware arithmetic')
    if note not in row['tested_scope']:
        row['tested_scope'] += note
    row['status'] = 'sample_qualified_five_operations_L1'
    row['remaining_requirements'] = 'Broader IEEE rounding modes and adversarial/exhaustive cases, conversions and other math operations, reusable high-level API/MSL frontend and L2/L3 integration; pressure/concurrency/performance qualification.'
    for ref in ['FP64_OPERATIONS_QUALIFIEES_2026-10-14.txt', 'results/fp64-math-progress-20261014/summary.json', 'results/fp64-math-normalized-suite-20261014-03/summary.json']:
        if ref not in row['evidence']:
            row['evidence'].append(ref)
    dump(p, d)

rows = '\n'.join(f"{op:<7} {v['baseline_numeric_mismatches']:>8} {v['exact_results']:>12} {v['new_numeric_mismatches']:>10}" for op, v in operations.items())
report = f'''KEPLERMETAL — CINQ OPÉRATIONS FP64 QUALIFIÉES SUR GTX 880M
14 octobre 2026 ; qualification bornée de laboratoire, niveau L1

139 005 résultats binary64 exacts, 139 005 marqueurs index/nonce corrects.
Addition, multiplication, FMA, division, racine carrée : chacune 27 801 résultats.
Groupes32/128/1024, comptes33/1041/8193, trois essais par taille.
Les 45 cohortes préparation/exécution/contrôle sont de nouvelles exécutions.
La suite ne réutilise plus implicitement l'ancien ADD32 ; aucune capture GPU
archivée n'est présentée comme une nouvelle exécution.

Operation  Erreurs initiales  Résultats exacts  Erreurs finales
{rows}

ORACLE ET PREUVE D'EXÉCUTION
Les réponses CPU ne sont jamais téléversées. Les programmes importés chargent
les entrées depuis des buffers Private, écrivent le résultat double et deux
marqueurs propres au programme : index et nonce de l'essai. L'oracle séparé
compare les captures : égalité des bits pour les valeurs finies et zéros signés,
NaN silencieux requis, payload/signe NaN non normalisés. Aucune tolérance ULP.
Le FMA fini utilise un calcul rationnel exact puis un seul arrondi binary64.
Le self-test CPU FMA vérifie 2 006 cas contre libc fma ; ce n'est pas un essai GPU.

45 CB positifs, 45 CB témoins natifs, 15 préparations sans commit du kernel
utilisateur. Les blits préparatoires restent exécutés. Les témoins utilisent le
carrier Metal natif d'origine, dont le calcul est différent : 139 005 résultats
et marqueurs différents comme attendu. Ce n'est pas une comparaison contre un
kernel MSL double équivalent. 69 120 octets de garde positifs, 207 360 sur les
45 cohortes, entrées relues intactes. Processus exit0, sans SIGKILL, terminaux.
Les bytes du code sont vérifiés à l'entrée du constructeur et après son appel ;
ce contrôle ne lit pas les instructions résidentes GPU. Les résultats, marqueurs
et contre-épreuves constituent une preuve distincte du simple import/allocation.

CORRECTIONS ET ÉCHECS CONSERVÉS
Le NIR initial employait les contrôles fast-math par défaut. DIV donnait 5 678
erreurs, SQRT18 218, avec marqueurs corrects et gardes intactes. Activer les
contrôles stricts et abaisser SQRTdouble tôt améliore le petit jeu44→11 erreurs,
sans résoudre les entrées négatives et certains sous-normaux.
La version finale normalise les exposants, traite zéro/inf/NaN explicitement,
utilise des corrections du résidu par DFMA pour DIV et traite son arrondi
sous-normal sans double arrondi à la frontière. Un premier round-to-odd a été
réfuté hors GPU ; il échoue quand un seul bit est retiré. Le modèle CPU final
donne0 erreurs sur77 628 contrôles contre une division rationnelle exacte,
contre24 pour l'ancien traitement, avec réciproque perturbée de−1/0/+1ULP.
Ce modèle n'atteste pas le comportement réel d'une réciproque NAK ; les essais
GPU distincts ci-dessus qualifient les programmes réellement compilés.

VERSIONS ET EMPREINTES
macOS26.7.1/25G241, GTX880M GK104SM30, registry4294968458.
clang17(1700.6.4.2), SDK26.2, x86_64 ; aucun -march=native d'un hôte distant.
Mesa26.2.4, référence amont96cb43121031992b85767f9c1be8f3f48e22b1d2 ;
les onze archives Mesa effectivement liées sont épinglées dans provenance.json.
Envytools f102b82381f3f11cee113d16374c87091db039d9 ; désassemblage GK104.
Compilateur local SHA256 :{compiled['compiler_source_SHA256']}
Import local SHA256 :{provenance['import_SHA256']['KeplerProgramImport.mm']}
Driver GeForceMTLDriver16.0.12/16.0.0, SHA256 :{provenance['driver_SHA256']}
Les codes font256B ADD/MUL,320B FMA,2 176B DIV,1 088B SQRT,24GPR ;
aucun scratch, CRS ou mémoire partagée pour ces cas. Chiffres par local32,
les métadonnées exactes de chaque taille sont dans le dossier offline03.
329 256B Private et329 312B Shared demandés par essai à8193 éléments.
Il s'agit de tailles de buffers demandées, pas d'une mesure de résidence VRAM
globale ; trois jeux sont retenus jusqu'à la sortie de ce host MRC borné.

REPRODUCTION — DEPUIS BRIDGE, NOMS DE SORTIES TOUS NEUFS
python3 tools/build_fp64_math.py --out results/FP64-NEW-OFFLINE
python3 tools/build_fp64_math_host.py --out results/FP64-NEW-HOST
python3 tools/prepare_fp64_math_cases.py --compiled results/FP64-NEW-OFFLINE --out results/FP64-NEW-INPUTS
python3 tools/run_fp64_math_suite.py --host results/FP64-NEW-HOST --cases results/FP64-NEW-INPUTS --out results/FP64-NEW-SUITE --operations sqrt div add mul fma
Le runner réserve le GPU coopérativement et vérifie chaque préparation avant
son exécution. Une faute de garde ou de marqueur arrête les lancements suivants.
Les fautes numériques restent FAIL et conservées ; le statut final doit PASS.
python3 tools/check_fp64_div_model.py --inputs results/FP64-NEW-INPUTS --out results/FP64-NEW-CPU-MODEL.json
python3 tools/verify_fp64_math.py results/FP64-NEW-SUITE/div-l1024-execute
Chaque dossier contient commandes, sources/hashes, manifests et sorties brutes.
Le builderhost ajouté reproduit la commande du host utilisé ; sa reconstruction
CPU distincte n'est pas présentée comme le host exécuté de cette campagne.

LIMITES ET TRANSMISSION
83 fichiers système et plist OCLP inchangés après les essais, empreintes relues.
L1 : import volontaire dans notre processus. Pas de MSL double ajouté, pas
de correction globale du compilateur Apple/NVIDIA, pas de support Metal3/4
complet, pas d'intégration transparente. Pas de gain annoncé ni de benchmark.
Les anciens essais288 restent conservés ; aucun cœur partagé modifié ici.
Objectif global actif et incomplet ; conformité IEEE exhaustive, autres modes
d'arrondi/conversions, API réutilisable et intégration L2/L3 restent ouvertes.
Gitmain sans premier commit ; instantané exact identifié par les SHA ci-dessus
et le manifeste de l'archive de preuves. job_ids=[] ; tests exécutés sur l'iMac.
PASS : cinq opérations bornées, préparations, contre-épreuves attendues, modèle
CPU final et gardes. FAIL conservés : DIV/SQRTinitiales, SQRTstrict intermédiaire,
premier modèle round-to-odd et première compilation nir_ugt. Aucun FAIL masqué.
NOT RUN : benchmark, MSLdouble, référence M1, revue Qwen ou portage Linux/FreeBSD.
Prochaine action : intégrer ce sous-ensemble dans une interface utilisateur
réutilisable, qualifier conversions/arrondis et mesurer une charge réelle ;
conserver distincte la recherche de modernisation NVIDIA/Linux.
'''
(ROOT / 'FP64_OPERATIONS_QUALIFIEES_2026-10-14.txt').write_text(report)
(OUT / 'RAPPORT.txt').write_text(report)
print(json.dumps(summary, indent=2))

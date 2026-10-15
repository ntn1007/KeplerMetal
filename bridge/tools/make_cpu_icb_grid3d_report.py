#!/usr/bin/env python3
"""Reconcile frozen 2D/3D GPU evidence, provenance and existing coverage."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent / 'driver-research-2026-10-13'
OUT = ROOT / 'results/cpu-icb-grid3d-progress'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

COHORTS = [
    'native-grid3d-pipeline-captured',
    'cpu-icb-grid3d-prepared', 'cpu-icb-grid3d-gpu-qualified',
    'cpu-icb-grid3d-buffer-regression-prepared',
    'cpu-icb-grid3d-buffer-regression-gpu-qualified',
    'cpu-icb-grid3d-dynamic-regression-prepared',
    'cpu-icb-grid3d-dynamic-regression-gpu-qualified',
]
GPU = read(ROOT / 'results/cpu-icb-grid3d-gpu-qualified/independent-verification.json')
BUFFERS = read(ROOT / 'results/cpu-icb-grid3d-buffer-regression-gpu-qualified/independent-verification.json')
SHARED = read(ROOT / 'results/cpu-icb-grid3d-dynamic-regression-gpu-qualified/independent-verification.json')
assert all(x['status'] == 'PASS' for x in (GPU, BUFFERS, SHARED))
assert GPU['GPU_invocations_counted'] == 18632 and GPU['correct_uint32_words'] == 149056
assert BUFFERS['correct_float32_values'] == 919040
assert SHARED['user_GPU_invocations'] == 5496 and SHARED['correct_uint32_words'] == 21984
history = []
ps = subprocess.check_output(['ps', '-axo', 'pid,stat,command'], text=True)
for cohort in COHORTS:
    folder = ROOT / 'results' / cohort
    m = read(folder / 'execution/manifest.json')
    assert m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert not any(m['signed_executable'] in line or m['original_executable'] in line
                   for line in ps.splitlines())
    hashes = read(folder / 'inputs.json')['source_hashes']
    for name, expected in hashes.items():
        assert sha(folder / name) == expected
        source_folder = 'src' if name.startswith('Kepler') or name.endswith(('.metal', '.json')) else 'tools'
        assert sha(ROOT / source_folder / name) == expected
    history.append({'cohort': cohort, 'pid': m['pid'], 'exit_code': 0,
                    'terminal': True, 'source_hashes': hashes})
baseline = read(RESEARCH / 'reports/STRATEGIE_PREUVES.json')
checked = []
for entry in baseline['system_files']:
    actual = sha(Path(entry['path']))
    assert actual == entry['sha256']
    checked.append({'path': entry['path'], 'sha256': actual})
rootpatch = Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')
assert len(checked) == 83 and sha(rootpatch) == baseline['rootpatch_sha256']
OUT.mkdir(exist_ok=True)
summary = {
    'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'goal_turn': 'PROGRESS', 'goal_complete': False,
    'Git_branch': 'main', 'Git_commit': None,
    'Git_state': 'UNBORN; lab untracked; exact references by frozen SHA snapshots',
    'integration_level': 1, 'native_2D_3D_grid_qualified': True,
    'user_command_buffers': 7, 'nonempty_command_buffers': 6,
    'native_user_dispatches': 28, 'GPU_invocations_counted': 18632,
    'correct_uint32_words': 149056, 'max_local_threads_tested': 1024,
    'max_local_Z_tested': 64, 'native_register_count': 21,
    'dimension_rejection_controls': 4,
    'reshape_CPU_copy_after_source_reset_and_empty_range_qualified': True,
    'buffer_regression_correct_float32_values': 919040,
    'shared_regression_invocations': 5496,
    'shared_regression_correct_uint32_words': 21984,
    'shared_regression_bytes': [1024, 32768, 49152],
    'native_shader_code_patched': False, 'ICB_contract_complete': False,
    'GPU_resident_command_indirection': False, 'GPU_generated_ICB': False,
    'render_ICB_qualified': False, 'performance_benchmark': False,
    'all_children_terminal': True, 'system_files_unchanged': 83,
    'rootpatch_unchanged': True, 'system_modified': False,
    'library_SHA256': '5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0',
    'manifest_SHA256': 'fa081fc43d24d54873d069006f9581f6b73b631f505ed9b854cb3429107ec4f3',
    'Qwen_job_ids': [],
    'Qwen_review_status': 'NOT RUN; authenticated MCP access confirmed, current central source copy not verified',
}
sources = [
    'src/KeplerCPUICB.h', 'src/KeplerCPUICB.mm',
    'src/KeplerNativeCommands.h', 'src/KeplerNativeCommands.mm',
    'src/cpu_icb_grid3d.metal', 'src/cpu_icb_grid3d.json',
    'tools/cpu_icb_grid3d_probe.mm', 'tools/native_grid3d_pipeline_probe.mm',
    'tools/reproduce_cpu_icb_grid3d.py', 'tools/reproduce_native_grid3d_pipeline.py',
    'tools/verify_cpu_icb_grid3d.py', 'tools/verify_cpu_icb_buffers.py',
    'tools/verify_cpu_icb_manifest.py', 'tools/decode_native_commands.py',
    'tools/run_signed_probe.py', 'tools/make_cpu_icb_grid3d_report.py',
]
provenance = {
    'macOS': subprocess.check_output(['sw_vers'], text=True),
    'clang': subprocess.check_output(['clang++', '--version'], text=True),
    'SDK_version': subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-version'], text=True).strip(),
    'Git_status': subprocess.check_output(['git', 'status', '--short', '--branch'], cwd=ROOT.parent.parent, text=True),
    'inputs': [{'path': str(ROOT / p), 'sha256': sha(ROOT / p)} for p in sources],
    'system_files': checked, 'rootpatch_sha256': sha(rootpatch),
    'system_modified': False, 'Qwen_job_ids': [],
}
dump(OUT / 'summary.json', summary)
dump(OUT / 'verification-history.json', history)
dump(OUT / 'provenance.json', provenance)
coverage = read(ROOT / 'results/hardware-coverage.json')
assert len(coverage['coverage']) == 30 and not coverage['complete']
for row in coverage['coverage']:
    if row['category'] != 'CPU-recorded compute ICB selectors and bounded resource lifetime':
        continue
    row['tested_scope'] += (' Latest extension: native uniform 2D/3D group/local geometry, '
        'coordinates/lane/group/grid builtins, local product1024 and localZ64. '
        'Seven CB (six nonempty/28 dispatches),18632 atomic-counted invocations/149056uint32 correct. '
        'Reshape/reset/CPU-copy after source reset/ranges/empty source verified. '
        'Four invalid dimensions rejected. Current-source four-buffer regression919040float32 '
        'and dynamic1/32/48KiB5496invocations/21984uint32 PASS.')
    row['remaining_requirements'] = ('Other types/indices/resource address spaces, multi-constant/argument-buffer/texture ABI, '
        'inherited state, nonuniform grids, combined static+dynamic shared, rendering, GPU timeline operations, '
        'GPU-resident/generation, concurrency/pressure/benchmarks and L2/L3 remain open. '
        'Uniform2D/3D qualified only for the captured program and configurations; registration alone is not GPU qualification.')
    for evidence in ['results/cpu-icb-grid3d-progress/summary.json',
                     'results/cpu-icb-grid3d-gpu-qualified/independent-verification.json',
                     'CPU_ICB_GRILLES_2D_3D.txt']:
        if evidence not in row['evidence']:
            row['evidence'].append(evidence)
for target in [ROOT / 'results/hardware-coverage.json', RESEARCH / 'inventory/hardware-coverage.json',
               RESEARCH / 'inventory/evidence-summaries/hardware-coverage.json']:
    dump(target, coverage)
report = f'''KEPLERMETAL — GRILLES NATIVES 2D/3D DANS LE SOUS-ENSEMBLE CPU ICB

État: PASS expérimental L1, objectif global incomplet.
Le module conserve désormais les trois axes MTLSize. Les produits et limites
d'axes sont contrôlés avant matérialisation; le manifeste doit autoriser ce
périmètre. Le pilote existant produit le QMD et les constantes builtin XYZ:
ils sont préservés, avec les seules relocalisations de ressources déjà qualifiées.
Le programme NVIDIA natif reste inchangé. Aucune écriture système ou OCLP.

Sept command buffers utilisateur, dont un vide: six non vides,28 dispatchs,
18632 invocations comptées par atomique et149056 mots uint32 corrects. Le CPU
recalcule chaque coordonnée globale, index, coordonnée locale/groupe et géométrie.
Les buffers Private sont relus par blit; toutes les gardes et sentinelles passent.
Les captures avant commit et matérialisations NOP gardent les sorties inchangées.
Le nouveau shader emploie21GPR natifs; aucun remplacement par NAK.

Groupes XYZ / threads par groupe XYZ, nombres d'invocations par commande:
(3,5,1)/(8,4,1):480; (2,3,4)/(4,2,2):384;
(3,2,2)/(5,3,2):360; (2,1,1)/(1,1,64):128;
(1,1,1)/(32,32,1):1024; (3,5,2)/(8,4,2):1920.
Le premier record est ensuite modifié en(2,2,2)/(4,4,4):512.
Plage sélective, nouveaux paramètres, rematérialisation, copie CPU conservant
la géométrie après reset complet du source, exécution d'une seule copie, source
vide: tous vérifiés. Quatre refus avant submission: axe nul,Zlocal65,
produitlocal1056 et produitgroupes66049 dépassant le contrat65536.
1024threads et Z64 sont des limites TESTÉES, pas de nouvelles capacités ajoutées.

Non-régression avec les mêmes sources actuelles:
- AXPY quatre buffers,128/8192/65536float4:919040valeurs float32 correctes;
  entrées identiques et gardes intactes.
- Shared dynamique1/32/48Kio, reuse/resize/copie et13refus:
  5496invocations/21984mots corrects.
Chaque cohorte a exit0, sources figées conformes aux modules actuels, enfants
terminés sans SIGKILL.83fichiers système et plist rootpatch rehashés inchangés.

Branche B: sous-ensemble de calcul CPU ICB étendu à des grilles uniformes2D/3D.
Les mots de commande sont copiés par le CPU: pas d'indirection ICB GPU-résidente,
ni génération ICB GPU. Rendu, grilles non uniformes, états hérités, autres ABI,
timeline, concurrence/pression et contrat ICB complet restent à établir.
L2 applications adaptées et L3 intégration transparente ne sont pas démontrés.
Branche A: aucune transposition Linux ni modification du pilote installé ici.
Benchmark NOT RUN; aucun gain CPU/GPU annoncé, aucun pourcentage global déduit.

Références exactes
Git main UNBORN, aucun commit; lab non suivi, références par SHA snapshots.
GeForceMTLDriver:2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Library:{summary['library_SHA256']}
Manifest:{summary['manifest_SHA256']}
macOS/clang/SDK, SHA des sources et83fichiers:results/cpu-icb-grid3d-progress/provenance.json.
NVIDIA QMD doc pin4de9b1af2ebcf610d8201af4ad07f7f2fb83b0f8,
Envytools pinf102b82381f3f11cee113d16374c87091db039d9:
results/pipeline-profile-references et decode_native_commands.py.
Les commandes exactes et processus signés sont dans chaque commands.json et
execution/manifest.json; vérificateurs indépendants des résultats observés.

Reproduction depuis {ROOT}, dossiers nouveaux uniquement:
python3 tools/reproduce_cpu_icb_grid3d.py --out results/NOUVEAU-grid-prepare
python3 tools/verify_cpu_icb_grid3d.py --input results/NOUVEAU-grid-prepare --check-current-sources
Après PASS:
python3 tools/reproduce_cpu_icb_grid3d.py --out results/NOUVEAU-grid-gpu --execute
python3 tools/verify_cpu_icb_grid3d.py --input results/NOUVEAU-grid-gpu --check-current-sources
La metallib figée est copiée de results/native-grid3d-pipeline-captured.
Pour recompiler: commandes clang/AIR/metallib du commands.json de cette capture;
une autre empreinte de library doit être qualifiée, pas acceptée artificiellement.

Coordination T-20261013-230031-fe3487, identité codex confirmée.
MCP qwen-local et qwen-mac-coder authentifiés; jeton privé0600, contenu non affiché.
Qwen job_ids=[]; contre-lecture NOT RUN: instantané actuel sur MrWhite non vérifié.
Les tests iMac ne sont pas assimilés à une exécution Windows/MacBook.
Prochaine action: capturer le contrat de commandes rendu natif en lecture seule,
puis définir une extension CPU ICB rendu bornée; génération GPU reste distincte.
'''
(ROOT / 'CPU_ICB_GRILLES_2D_3D.txt').write_text(report)
print(json.dumps(summary, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""Record bounded SDK client qualification against its immutable delivery."""
from pathlib import Path
import collections
import datetime
import hashlib
import importlib.util
import json
import stat
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/sdk-progress-20261014'
SDK_BUILD = ROOT / 'results/keplermetal-sdk-build-20261014-04'
CLIENT = ROOT / 'results/keplermetal-sdk-client-20261014-04'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

delivery = read(SDK_BUILD / 'delivery.json')
archive = Path(delivery['path'])
assert sha(archive) == delivery['SHA256']
manifest = read(SDK_BUILD / 'KeplerMetalSDK/FILE_MANIFEST.json')
with tarfile.open(archive) as tar:
    for entry in manifest['files']:
        raw = tar.extractfile('KeplerMetalSDK/' + entry['path']).read()
        assert len(raw) == entry['bytes']
        assert hashlib.sha256(raw).hexdigest() == entry['SHA256']
    assert len(tar.getmembers()) == delivery['files'] == 19
build = read(SDK_BUILD / 'KeplerMetalSDK/BUILD_MANIFEST.json')
for rel, expected in build['source_SHA256'].items():
    assert sha(ROOT / rel) == expected
for rel in ['README.md', 'examples/client.mm', 'examples/client.metal',
            'examples/build_example.py', 'examples/run_example.py',
            'examples/verify_example.py']:
    assert sha(ROOT / 'sdk' / rel) == sha(SDK_BUILD / 'KeplerMetalSDK' / rel)
spec = importlib.util.spec_from_file_location(
    'sdk_verify', CLIENT / 'KeplerMetalSDK/examples/verify_example.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
history, executions = {}, {}
for name in ['sdk-delivered-client-prepared-04',
             'sdk-delivered-client-gpu-qualified-04']:
    root = ROOT / 'results' / name
    history[name] = verifier.verify(root)
    execution = read(root / 'execution/manifest.json')
    observed = subprocess.run(['ps', '-o', 'stat=,command=', '-p',
                               str(execution['pid'])], capture_output=True,
                              text=True).stdout.strip()
    assert execution['signed_executable'] not in observed
    executions[name] = execution
gpu = history['sdk-delivered-client-gpu-qualified-04']
assert gpu['exact_BGRA8_components'] == 245760
assert gpu['core_source_compilations'] == 0
assert gpu['GPU_command_buffers'] == 5
assert not (CLIENT / 'KeplerMetalSDK/src').exists()
inputs = read(CLIENT / 'application/inputs.json')
assert inputs['SDK_archive_SHA256'] == build['static_archive_SHA256']
system = read(OUT / 'system-check.json')
assert system['system_files_unchanged'] == 83 and system['rootpatch_unchanged']
failed03 = ROOT / 'results/sdk-delivered-client-prepared'
failure_observation = {
    'path': str(failed03), 'status': 'NOT RUN / no qualification',
    'copied_binary_mode': oct(stat.S_IMODE((failed03 / 'keplermetal_example').stat().st_mode)),
    'signed_copy_mode': oct(stat.S_IMODE((failed03 / 'execution/keplermetal_example').stat().st_mode)),
    'manifest_present': (failed03 / 'execution/manifest.json').exists(),
    'GPU_results_present': (failed03 / 'results.json').exists(),
    'limitation': 'The interrupted orchestration output did not preserve an exit code. Copies are non-executable (0644); no successful launch or GPU execution is attested for this attempt.',
    'correction': 'run_example.py uses copy2 to preserve executable permissions; delivery04 independently extracted and qualified.'}
summary = dict(gpu)
summary.update({
    'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'goal_turn': 'PROGRESS', 'goal_complete': False,
    'Git_branch': 'main', 'Git_commit': None,
    'integration_scope': 'L2 only for an explicitly adapted SDK example and five bounded render scenarios',
    'ordinary_applications_transparent': False,
    'full_ICB_contract': False, 'all_hardware_functions_supported': False,
    'driver_modernization_installed': False,
    'system_files_unchanged': 83, 'rootpatch_unchanged': True,
    'Qwen_job_ids': [],
    'Qwen_access': 'Both health calls succeeded; coordination recognizes codex, task claimed, version32 before this milestone.',
    'Qwen_review_status': 'NOT RUN; exact current Windows source copy unverified',
    'SDK_tar_SHA256': delivery['SHA256'],
    'SDK_static_library_SHA256': build['static_archive_SHA256'],
    'creation_qualification_pending_flag_superseded_by': 'This external receipt; the frozen tar qualification.json was not rewritten.'})
dump(OUT / 'summary.json', summary)
dump(OUT / 'verification-history.json', history)
dump(OUT / 'qualification-receipt.json', {
    'summary': summary, 'archive': delivery,
    'extraction': read(CLIENT / 'extraction-verification.json'),
    'client_inputs': inputs, 'core_source_SHA256': build['source_SHA256'],
    'executions': executions, 'failure03_observation': failure_observation,
    'prior_failures_preserved': [
        'results/keplermetal-sdk-client-20261014-01/application/commands.json: -ObjC clang flag error; fixed with -Wl,-ObjC',
        'results/keplermetal-sdk-client-20261014-02/application/execution/manifest.json: prepare exit10, missing output directory; no user command buffer committed',
        'results/sdk-delivered-client-prepared: missing executable permissions; no successful launch attested'],
    'performance': 'NOT RUN; no speedup or lower CPU usage claimed'})
dump(OUT / 'provenance.json', {
    'SDK_build': build, 'client_build_commands': read(CLIENT / 'application/commands.json'),
    'machine': system, 'Git_status': subprocess.check_output(
        ['git', 'status', '--short', '--branch'], cwd=ROOT.parent.parent, text=True),
    'Qwen_job_ids': []})

coverage_path = ROOT / 'results/hardware-coverage.json'
coverage = read(coverage_path)
assert len(coverage['coverage']) == 30 and not coverage['complete']
addition = (' SDK delivery04 consumed by independently compiled adapted client, '
    'without core source compilation (implementation sources removed before client build). '
    'Client-specific vertex/fragment shader, BGRA8 128x96/scissor, five CB, '
    '245760 exact components; native, ICB, empty range, copy/reset, precommit closure. '
    'L2 qualification is limited to this documented example; no full API/L3/performance qualification.')
for row in coverage['coverage']:
    if row['category'] == 'CPU-recorded compute ICB selectors and bounded resource lifetime':
        if addition not in row['tested_scope']:
            row['tested_scope'] += addition
        row['SDK_client_integration'] = {
            'level': 2, 'scope': 'Five bounded render scenarios in adapted SDK example',
            'evidence': 'bridge/results/sdk-progress-20261014/qualification-receipt.json',
            'full_category_qualified': False}
research = ROOT.parent / 'driver-research-2026-10-13'
for path in [coverage_path, research / 'inventory/hardware-coverage.json',
             research / 'inventory/evidence-summaries/hardware-coverage.json']:
    dump(path, coverage)
dump(OUT / 'coverage-status-counts.json', dict(collections.Counter(
    row['status'] for row in coverage['coverage'])))

report = f'''KEPLERMETAL — PREMIER SDK POUR UNE APPLICATION ADAPTÉE
14 octobre 2026 — résultat borné, objectif global encore incomplet

Le paquet livraison04 est consommable par un client Objective-C++ lié à
libKeplerMetal.a. Les sources d'implémentation ont été retirées du dossier SDK
du client avant sa compilation. Seuls le client et son shader ont été compilés.
Le rendu est exécuté sur le device GTX 880M, registryID 4294968458.

RÉSULTAT ACTUEL
Préparation : PASS, PID 39710, exit0 ; aucun CB utilisateur commité.
GPU : PASS, PID 39754, exit0, cinq CB terminés, aucun SIGKILL.
245 760 composantes BGRA8 exactes (61 440 pixels), gardes intactes.
Rendu natif / ICB / copie après reset / fermeture avant commit : images
byte-identiques. Range vide : image noire. Classes d'instances restaurées.
Shader client : couleur (.375,.625,.875,1), BGRA8 attendu [223,159,96,255]
dans le scissor (32,24,64,48) d'une cible 128×96 ; noir ailleurs.
Le client écrit uniquement les gardes CPU. Le remplissage de la cible Private
passe par le rendu Metal et le readback par blit GPU. Le vérificateur Python
calcule ses attentes indépendamment à partir des captures brutes.

Ce résultat qualifie le niveau 2 pour le contrat documenté de cet exemple.
Il ne qualifie ni toutes les applications adaptées, ni toutes les API Metal,
ni le niveau 3 transparent. Le compilateur et le pilote installés sont inchangés.
La branche A (réparation native CAS générale, améliorations NVIDIA/Linux) reste
distincte. Aucun portage Linux, gain de performance ou allègement CPU nouveau
n'est démontré par ce SDK. L'ICB GPU-résident/généré reste non implémenté.

PROVENANCE
Git : main sans premier commit ; lab/opencl non suivis. Référence par SHA.
SDK livraison04 tar SHA256 : {delivery['SHA256']}
Bibliothèque statique SHA256 : {build['static_archive_SHA256']}
Shader client metallib SHA256 : {inputs['client_shader_SHA256']}
Driver GeForceMTL : 16.0.12 court / 16.0.0 bundle, SHA256
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
macOS 26.7.1 / 25G241 ; SDK26.2 ; Apple clang17 (1700.6.4.2).
83 fichiers système et plist rootpatch OCLP rehashés inchangés après les tests.
Les six sources runtime concordent avec le build de la bibliothèque réutilisée.
Les 19 fichiers du tar sont vérifiés ; BUILD_MANIFEST et FILE_MANIFEST inclus.
qualification.json dans le tar conserve l'état « pending » de sa création.
Le reçu externe qualification-receipt.json atteste les tests de ce même tar.

REPRODUCTION (dossier extrait neuf, sur l'iMac qualifié)
python3 examples/build_example.py --out /chemin/neuf/application
python3 examples/run_example.py --build /chemin/neuf/application --out /chemin/neuf/prepare
python3 examples/verify_example.py /chemin/neuf/prepare
python3 examples/run_example.py --build /chemin/neuf/application --out /chemin/neuf/gpu --execute
python3 examples/verify_example.py /chemin/neuf/gpu
Le lien inclut -Wl,-ObjC. La signature ad hoc porte uniquement sur la copie
de l'application dans son dossier. Ni installation ni changement de protection.

ÉCHECS CONSERVÉS
Client01 : compilation FAIL, -ObjC interprété comme option frontend Objective-C.
Client02 premier prepare : FAIL exit10, dossier outputs oublié par le coordinateur.
Lanceur03 : copies0644, aucun résultat d'exécution attesté ; état NOT RUN.
Le lanceur04 préserve les permissions et crée le dossier ; préparation et GPU PASS.
Les anciens dossiers ne sont ni écrasés ni transformés en réussites.

QWEN
Les deux MCP et moteurs répondent ; libres/file0 à l'observation du 14 octobre.
Coordination authentifiée codex, tâche T-20261013-230031-fe3487 prise.
Jeton existant présent0600 ; contenu non affiché, non renouvelé.
job_ids=[] ; contre-lecture NOT RUN. Une copie exacte vérifiée sur MrWhite
reste nécessaire. Le raisonnement MLX du MacBook ne représente aucun test GPU
sur l'iMac. Le travail de ce jalon a été fait en solo conformément au repli autorisé.

CE QUI RESTE
Qualification élargie de clients compute/rendu, combinaisons de ressources/états,
mémoire/pression/concurrence et erreurs ; contrat CPU ICB plus complet ; format
ICB GPU/génération ; modernisation CAS générale ; voie vidéo hardware encore
bloquée ; intégration transparente et benchmarks réels. Aucun fichier système
ne doit être déployé à partir de ce paquet expérimental.
La couverture canonique comporte30 catégories, complete=false. Un pourcentage
global fiable du pilote final n'est pas calculable avec ce périmètre ouvert.
5/5 scénarios client réussis mesure ces essais, pas 100% des fonctions de la880M.
Prochaine action : élargir le client SDK vers compute/ressources et appliquer
les contrôles de durée de vie avant d'étudier une intégration plus générale.

PREUVES
results/sdk-progress-20261014/qualification-receipt.json
results/sdk-progress-20261014/verification-history.json
results/sdk-progress-20261014/system-check.json
results/sdk-delivered-client-gpu-qualified-04/outputs/trial-*.image.bin
results/sdk-delivered-client-gpu-qualified-04/execution/manifest.json
results/keplermetal-sdk-client-20261014-04/application/commands.json
'''
(ROOT / 'SDK_APPLICATION_ADAPTEE.txt').write_text(report)
print(json.dumps(summary, ensure_ascii=False, indent=2))

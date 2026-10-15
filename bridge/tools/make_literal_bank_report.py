#!/usr/bin/env python3
"""Recheck raw evidence/current sources, processes and system before reporting."""
from pathlib import Path
import datetime,hashlib,json,subprocess
from verify_cpu_icb_literal_lut import verify as lut
from verify_cpu_icb_dependency import verify as dependency
from verify_cpu_icb_native_cas import verify as cas
from verify_cpu_icb_mixed import verify as mixed
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/literal-bank-progress';OUT.mkdir(exist_ok=True)
groups={
 'lut':['literal-lut-prepared-20261014-02','literal-lut-reject-unqualified-20261014','literal-lut-reject-size-20261014','literal-lut-gpu-qualified-20261014','literal-lut-native-reference-20261014'],
 'dependency':['literal-bank-dependency-regression-prepared-20261014','literal-bank-dependency-regression-gpu-20261014'],
 'cas':['literal-bank-cas-regression-prepared-20261014','literal-bank-cas-regression-gpu-20261014'],
 'mixed':['literal-bank-mixed-regression-prepared-20261014','literal-bank-mixed-regression-gpu-20261014'],
}
verifiers={'lut':lut,'dependency':dependency,'cas':cas,'mixed':mixed};verified={};processes={}
for kind,names in groups.items():
 for name in names:
  verified[name]=verifiers[kind](ROOT/'results'/name,current=True)
  assert verified[name]['status']=='PASS'
  m=json.loads((ROOT/'results'/name/'execution/manifest.json').read_text())
  state=subprocess.run(['ps','-o','pid=,lstart=,command=','-p',str(m['pid'])],capture_output=True,text=True).stdout.strip();assert not state
  assert m['GPU_reservation']['state']=='terminal' and m['reservation_module_SHA256']==hashlib.sha256((ROOT/'tools/lab_gpu_reservation.py').read_bytes()).hexdigest()
  processes[name]={'PID':m['pid'],'exit_code':m['exit_code'],'SIGKILL_requested':m['SIGKILL_requested'],'actual_ps_status':state,'manifest_SHA256':hashlib.sha256((ROOT/'results'/name/'execution/manifest.json').read_bytes()).hexdigest()}
old=json.loads((ROOT/'results/icb-dependency-progress/system-check.json').read_text())
for row in old['system_files']:assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
assert hashlib.sha256(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist').read_bytes()).hexdigest()==old['rootpatch_sha256']
system={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_files':old['system_files'],'system_files_unchanged':83,'rootpatch_unchanged':True,'rootpatch_SHA256':old['rootpatch_sha256'],'macOS':subprocess.check_output(['sw_vers'],text=True)}
reservation=json.loads((ROOT/'results/gpu-reservation-cpu-tests-20261014-03/verification.json').read_text());assert reservation['status']=='PASS' and len(reservation['cases'])==7
summary={k:v for k,v in verified['literal-lut-gpu-qualified-20261014'].items() if k!='raw_SHA256'}
summary.update(at=system['observed_at'],goal_turn='PROGRESS',goal_complete=False,native_ICB_byte_identical_files=54,positive_processes_terminal=len(processes),reservation_CPU_cases=7,
 CAS_regression_uint32_words=verified['literal-bank-cas-regression-gpu-20261014']['exact_uint32_words'],
 dependency_regression_uint32_words=verified['literal-bank-dependency-regression-gpu-20261014']['exact_uint32_words'],
 mixed_regression_float32_words=verified['literal-bank-mixed-regression-gpu-20261014']['correct_float32_channels'],
 system_files_unchanged=83,rootpatch_unchanged=True,Qwen_job_ids=[],ordinary_applications_transparent=False,SDK_contains_new_CB0=False,Git_branch='main',Git_commit=None)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'verification-history.json').write_text(json.dumps(verified,indent=2)+'\n')
(OUT/'processes.json').write_text(json.dumps(processes,indent=2)+'\n')
(OUT/'system-check.json').write_text(json.dumps(system,indent=2)+'\n')
note=' Native literal CB0 pools expanded in scoped compute ICB to pinned256/512/1024-byte layouts:4native LUT functions,9CB/30records,1296472uint32 exact,324118atomic-counted invocations,54native/ICBcapturesbyteidentical. Random32bit static tables16/64/128/256entries,rotates and varying inputs/seeds,locals32/128/256/1024,partial/empty/copy-reset/precommit restoration qualified. CB0 remains native and held through actual variant owner;wrong registered size and unqualified384 octets refused before user dispatch,negative-size raw guards/counters independently checked. Shared-core dependencies1184256uint32,CAS169404uint32,mixed110592float32 regressions PASS. Lab launches now share flock with inherited FD and conservative persistent unresolved state;7CPU-only lifecycle cases,not GPU stress/exclusive hardware reservation. L1,newbanklayouts not in frozenSDK,L3/performance/fullAPI remain open.'
for p in [ROOT/'results/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']:
 data=json.loads(p.read_text());assert not data['complete'] and len(data['coverage'])==30
 for row in data['coverage']:
  if row['category'] in ['CPU/GPU memory and DMA','CPU-recorded compute ICB selectors and bounded resource lifetime']:
   if note not in row['tested_scope']:row['tested_scope']+=note
   for ref in ['CB0_TABLES_NATIVES_RESERVATION.txt','results/literal-bank-progress/summary.json']:
    if ref not in row['evidence']:row['evidence'].append(ref)
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
report=f'''KEPLERMETAL — TABLES CONSTANTES NATIVES CB0 ET RÉSERVATION DES ESSAIS
14 octobre 2026 — extension de laboratoire de la branche B

Le transport des ICB CPU accepte désormais les banques CB0 de 256, 512 et
1 024 octets, avec taille explicitement enregistrée et contrôlée. Il conserve
le code et les données du compilateur NVIDIA. Le pilote Metal natif savait
déjà exécuter ces programmes ; l'extension lève leur refus dans notre transport.
Elle ne remplace pas le pilote et n'ajoute aucune famille Metal annoncée.

QUATRE PROGRAMMES ET LEUR PREUVE D'EXÉCUTION
Tables constantes de 16 / 64 / 128 / 256 entiers, avec indices GPU dynamiques,
additions/XOR/multiplications et rotations. Tables et oracle générés séparément.
Les quatre programmes natifs ont 14 registres et 576 octets de code ; CB0 se
trouve après le code aligné sur 256. Tailles observées : 256 / 256 / 512 / 1024.
Classes/offsets privés restent ceux du pilote épinglé. Le véritable propriétaire
NVMTLFunctionVariant est retenu par chaque record ; contenu CB0 ni lu par le
CPU, ni déplacé, ni réécrit. Code-adresse/taille/registres et QMD vérifiés.

9 command buffers / 30 records : 1 296 472 mots uint32 exacts,
324 118 invocations GPU comptées, 16 779 472 octets de garde vérifiés.
54 fichiers de résultats/entrées/compteurs identiques à Metal natif.
Tailles 129 / 8 193 / 32 768 / 1 025 ; groupes locaux 32 / 128 / 256 / 1024 puis 1024 partout.
Paramètres aux offsets 512 / 768, sorties/entrées/counters aux offsets 64.
Plages partielles et vides, copie/reset, renouvellement des constantes et
restauration/release du scope avant le dernier commit testés.
Les préparations ne soumettent aucun CB principal : sorties et compteurs
inchangés. NOP/blits préparatoires conservés ; ce n'est pas zéro activité GPU.
Deux refus attendus :384 octets non qualifiés à l'enregistrement ;256 octets déclarés
pour un programme512 octets refusés à la préparation, avec raw sorties/compteurs
intacts vérifiés indépendamment. Un premier build a échoué sur BOOL/bool
dans un lambda ; corrigé avant toute exécution de la sonde et trace conservée.

NON-RÉGRESSION DU CŒUR PARTAGÉ
Chaîne Private Untracked :1 184 256 uint32 exacts /287 872 invocations.
CAS natif intégré :169 404 uint32 exacts /42 351 opérations.
Calcul/rendu :110 592 float32 exacts /192 invocations compute comptées.
Préparation/oracle validés avant chaque cohorte GPU. Les11 processus positifs
de ces cohortes sont terminaux, exit 0 sans SIGKILL. Le CPU réutilise parfois un
exécutable précisément épinglé ; chaque exécution GPU et signature est neuve.
Il s'agit d'une réutilisation explicite, pas d'un cache général des dépendances.

RÉSERVATION COOPÉRATIVE SUR L'HÔTE
Le lanceur commun prend un flock exclusif non bloquant, transmis au processus
enfant par FD. La fermeture du FD parent ne libère pas celui d'un enfant vivant.
Un registre de session atomique conserve identité, démarrage, chemin et résultat.
Une session interrompue/inconnue reste bloquée ; disparition ou demande de kill
ne devient jamais automatiquement un succès. Aucun moteur partagé n'est tué.
Un seul tableau ps vérifie tous les chemins signés connus, indépendamment des
anciens hashes/PID ; l'historique reste conservé sans un ps par ancienne entrée.
7 cas CPU réels/simulés qualifiés : concurrence de réservation, reprise terminale,
PID réutilisé/autre chemin, chemin vivant/autre hash, parent réellement sorti
avec enfant tenant le FD, outcome orphelin inconnu, état SIGKILL simulé.
Les deux premiers essais de fixture CPU échoués sont conservés et n'ont utilisé
aucun GPU : alias de chemin Python, puis copy2 de flags système protégés.
Cette réservation concerne les utilisateurs du lanceur commun, pas WindowServer,
les applications non coopérantes ou les vieux exemples SDK autonomes figés.

PROVENANCE ET REPRODUCTION — DEPUIS BRIDGE, DOSSIERS NEUFS
macOS 26.7.1 / build 25G241 ; GeForceMTL 16.0.12 / 16.0.0, SHA256
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
Compilation Metal -std=macos-metal2.4 ;clang 17 / SDK 26.2. Commandes et fichiers
AIR/metallib dans results/native-literal-bank-passive-20261014.
python3 tools/test_lab_gpu_reservation.py --out results/LOCK-NEW
python3 tools/reproduce_cpu_icb_literal_lut.py --out results/LUT-PREP-NEW --mode prepare
python3 tools/verify_cpu_icb_literal_lut.py results/LUT-PREP-NEW --current
python3 tools/reproduce_cpu_icb_literal_lut.py --out results/LUT-GPU-NEW --mode execute --reuse-host-from results/LUT-PREP-NEW
python3 tools/verify_cpu_icb_literal_lut.py results/LUT-GPU-NEW --current
Modes native /reject-size /reject-unqualified à lancer dans d'autres dossiers.
N'exécuter le mode execute qu'après préparation et contrôles validés.

TRANSMISSION
Objectif global : fonctions matérielles réalisables de la GTX 880M sous macOS.
Git main sans premier commit ; sources locales non suivies, références parSHA.
Actions : réservation des essais, profils CB0 et LUT, contrôles/refus/régressions.
PASS : 11 oracles des cohortes,7 casCPU de réservation, comparaison native.
FAIL conservés :buildBOOL/bool et deux fixtures CPU ; aucun échec GPU nouveau.
BLOCKED :aucun nouveau blocage de cette extension ; limites vidéo antérieures.
NOT RUN :autres tailles/dispositions CB0, concurrence GPU, mémoire sous pression,
benchmark, SDK actualisé, Metal 3/4 complet, port Linux, intégration transparente.
83 fichiers système/rootpatch OCLP inchangés après les essais. Aucun pilote,
framework, kext, firmware, VBIOS ou réglage matériel modifié. Qwen job_ids=[] / solo.
Niveau L1 pour cette nouvelle qualification ; SDK précédent L2 figé conservé.
Couverture : 30 catégories, complete=false ; objectif global actif. Aucun gain annoncé.
Suite : dispositions constantes restantes et intégration au SDK, puis fonctions
matérielles non couvertes et benchmarks représentatifs avec exigences identiques.
'''
(ROOT/'CB0_TABLES_NATIVES_RESERVATION.txt').write_text(report)
print(json.dumps(summary,indent=2))

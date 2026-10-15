#!/usr/bin/env python3
"""Write this milestone report only from the completed qualification receipt."""
from pathlib import Path
import hashlib,json

r=Path(__file__).resolve().parents[1]
p=r/'results/gpu-generated-geometry-progress-20261014/final-qualification'
d=json.loads((p/'qualification-receipt.json').read_text());assert d['status']=='PASS'
assert d['independent_oracles_PASS']==137 and not d['objective_complete']
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
sdk=r/'results/gpu-generated-geometry-sdk-build-20261014-07/KeplerMetalSDK'
summary=json.loads((r/'results/gpu-generated-geometry-progress-20261014/primary-summary.json').read_text())
text=f'''KEPLERMETAL — GRILLE CALCULÉE SUR GPU, GTX 880M / M1 MAX
14 octobre 2026 — résultat expérimental de niveau 2

Objectif : prendre en charge les fonctionnalités matérielles de la GTX 880M
sur macOS. L’objectif complet reste ACTIF et non réalisé.
Ce jalon appartient à l’extension Metal (branche B), pas à un portage Linux.

Avancée
Le GPU réduit un jeu de données Private, choisit l’un de trois programmes
NVIDIA natifs préparés et calcule un nombre de groupes X. Il copie la commande
validée puis remplace le mot de grille du QMD à l’offset 0x30. Le programme,
les adresses des ressources, la taille locale, les registres et l’allocation
de mémoire partagée sont conservés. Le CPU ne lit ni le choix ni la grille
avant la consommation de la commande.
Le M1 emploie les opérations MSL natives compute_command.copy_command puis
concurrent_dispatch_threadgroups avec la même règle, les mêmes données et
le même client/source d’interface. Sa compilation utilise MSL 2.3 ; ce banc
ne qualifie pas une nouvelle fonction Metal 4 sur Kepler.

Le nombre de groupes est borné à 1..nombre original (au plus7). Le manifest
existant limite toujours à4096 invocations, donc4 groupes pour local1024.
Les valeurs observées sont {d['observed_group_counts']}. La valeur7 et tous les
couples possibles n’ont pas été exhaustivement exécutés par ce jalon.
Les fonctions admissibles sont shared_mix_s128, shared_mix_s1024 et
shared_mix_s4096 de la bibliothèque b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd.
Elles possèdent512/4096/16384 octets statiques ; les candidats utilisent
49152 octets partagés au total, en conservant leur base dynamique validée.

Preuves
PASS : 8 cohortes GTX primaires, 1 cohorte de refus, 120 cohortes GTX de
non-régression et8 cohortes M1 ; 137 vérifications indépendantes.
115988 mots uint32 corrects dans les positifs ; 18432 dans les contrôles
causaux ;22528 dans le témoin GPU suivant les refus.
60 refus d’API attendus : identités binaires invalides,8groupes, destination
modifiée, entrées/ranges, buffers/queues, re-encodage et modifications CPU
d’un emplacement dont l’état a été calculé par GPU.
300 fichiers de sortie identiques GTX/M1. 3253 fichiers de non-régression
identiques aux captures précédentes ; les flux contenant des adresses GPU
sont vérifiés par leurs décodeurs, sans exiger leur identité binaire.
21 clients ont compilé avec les en-têtes, assets et bibliothèque publique,
sans compiler les sources du cœur. Les processus sont terminés et la
réservation coopérative a été libérée ; elle n’exclut pas WindowServer.
Les83 fichiers système surveillés et le plist OCLP ont les mêmes empreintes.

Deux échecs conservés
Les deux premiers essais prepare ont été refusés pendant l’encodage, avant
la soumission du command buffer expérimental. Le second diagnostic localise
les seules différences aux octets356/360 (QMD+0x8c/0x90, adresse CB3 inactive).
Le pointeur des limites a été changé de constant à device const. Cela évite
une banque de constantes supplémentaire et rétablit la comparaison exacte
du primer ; aucun contrôle d’identité de commande n’a été relâché.
Une borne de fixture a aussi été corrigée :7groupes de1024 auraient dépassé
les4096 invocations du manifest ; la fixture en utilise4.
Le libellé initial PASS_CAUSAL_CONTROL du vérificateur de refus a été corrigé
en PASS_REFUSALS_WITH_VALID_GPU_WITNESS lors de la relecture des mêmes données,
sans réexécuter le GPU pour ce changement de présentation.

Versions exactes
Git : main, dépôt sans commit, modifications locales non suivies.
SDK07 SHA256 : {d['SDK_archive_SHA256']}
Bibliothèque statique SHA256 : {d['static_library_SHA256']}
Shader de géométrie SHA256 : {d['geometry_library_SHA256']}
Shader source SHA256 : {sha(r/'src/gpu_command_geometry.metal')}
Client source SHA256 : {sha(r/'sdk-combined/examples/gpu_command_geometry_client.mm')}
Transfert source M1 SHA256 : 701c4d52fc765c00ffa9b8dd951b896c25602114086928f412ee8be008c27908
Retour M1 SHA256 : {summary['M1_return']['SHA256']}
Les13 empreintes de sources du cœur, outils/SDK et artefacts effectivement
liés figurent dans BUILD_MANIFEST.json et qualification-receipt.json.
job_ids=[] : travail réalisé en solo. Qwen accessibles ; aucune analyse
des sources de cet instantané n’a été exécutée sur MrWhite.

Reproduction depuis bridge, dossiers de résultats neufs requis
SDK livré : results/gpu-generated-geometry-sdk-build-20261014-07/KeplerMetalSDK
Compiler un client en utilisant le paquet extrait et ses en-têtes/lib/assets :
python3 <SDK>/examples/build_gpu_command_geometry_client.py --out <nouveau_build>
python3 tools/run_gpu_command_geometry.py --build <nouveau_build> --out results/<nouveau_cas> --mode select
python3 tools/verify_gpu_command_geometry.py results/<nouveau_cas>
Modes : prepare, select, range, split, completed, copy, no_producer, no_selector.
Pour les refus : build_gpu_command_geometry_refusals_client.py, mode refusals,
puis verify_gpu_geometry_refusals.py.
Les commandes exactes de compilation, signature, lancement et transfert sont
archivées dans commands.json, manifest.json et transfer-commands.json.
Les sources M1 se trouvent dans le bundle GPUGeometryReference ; son runner
vérifie les SHA avant compilation/exécution native arm64.

Limites et prochaine action
FAIL conservés : les deux refus de primer précédents, terminal exit_code -6.
BLOCKED : aucun obstacle empêchant la suite de la recherche.
NOT RUN : benchmark de cette bibliothèque, construction générale MSL des
commandes, autres bibliothèques/ABI, intégration transparente aux applications.
Le chemin split soumet producteur, générateur et consommateur sur une même
queue sans attente CPU intermédiaire. La préparation froide et le readback
final comportent des attentes. Le mode completed attend volontairement puis
réinitialise les sources avant consommation, pour tester leur ownership.
Les contrôles sans producteur et sans générateur produisent les sorties
alternatives attendues ; leur succès ne signifie pas des données aléatoires.
Ce module est une interface pour application adaptée, pas un nouveau pilote
système. Il n’implémente pas toutes les commandes Metal ni toutes les fonctions
matérielles (vidéo, affichage, énergie et autres domaines restent à traiter).
Suite : généraliser les états de commande certifiés, puis qualifier l’usage
par un client utilisant les appels Metal publics visés. Préserver le pilote
existant et distinguer modernisation NVIDIA, extension Metal et performances.

Sources officielles pour le contrat, distinctes des preuves matérielles
https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf
Sections6.17.2/6.17.3 : copie et encodage des commandes de calcul.
https://developer.apple.com/documentation/metal/encoding-indirect-command-buffers-on-the-gpu
https://developer.apple.com/documentation/metal/mtlcomputecommandencoder/dispatchthreadgroups(indirectbuffer:indirectbufferoffset:threadsperthreadgroup:)
La dernière API existait avant Metal3/4. Ce jalon étend le chemin ICB du
laboratoire ; il ne revendique pas l’invention de l’indirect dispatch natif.
'''
out=r/'ICB_GEOMETRIE_GPU_M1_GTX_2026-10-14.txt'
with out.open('x')as f:f.write(text)
print(out)

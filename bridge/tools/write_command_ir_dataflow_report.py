#!/usr/bin/env python3
"""Write the bounded dataflow milestone only after current-runtime qualification."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'results/command-ir-dataflow-progress-20261015';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(out/'qualification-receipt.json');assert r['status']=='PASS'and not r['objective_complete'];lib=r['library_SHA256'];shader=r['materializer_v2_SHA256'];compiler=read(ROOT/'results/command-ir-dataflow-compiler-build-20261015/manifest.json')['compiler_SHA256']
text=f'''KEPLERMETAL — COMMANDES GPU, BINDINGS NATIFS ET CHAÎNE DE CALCUL
15 octobre 2026 — branche B, qualification L2 dans une application adaptée

RÉSULTAT
Le GPU encode les commandes de trois kernels NVIDIA natifs dépendants :
seed → gather → finish. Le résultat d'une étape est lu par la suivante,
sans lecture CPU ni réponse CPU téléchargée entre les étapes. Constantes au
slot2, compteur atomique au slot3, premier kernel avec entrée inactive.
La metallib native archivée est conservée sans recompilation de sa source.
Les pipelines sont créés avec le compilateur NVIDIA en place ; aucun code
SASS n'est substitué aux trois consommateurs. NAK produit les commandes.

NOUVEAU DÉFAUT IDENTIFIÉ ET CORRECTION
Les premiers essais terminent avec des compteurs corrects, mais gather et
finish lisent encore les canaris. Ces échecs numériques sont conservés :
results/command-ir-dataflow-progress-20261015/preserved-failures.json.
Le défaut se situe dans notre matérialiseur KeplerMetal, qui ne réécrivait
que les adresses des bindings.
La capture CB1 confirme les VA réécrites et les autres champs natifs anciens.
Une adresse64 seule ne représente donc pas un binding natif complet dans
ces cas. Le sens exact des champs opaques n'est pas établi par cette capture.

Le catalogue prépare désormais une entrée32B complète avec le pilote natif,
pour chaque couple pipeline/ressources autorisé. Les préparations suppriment
le lancement utilisateur (NOP), comme les templates existants. Le GPU choisit
et copie ces entrées complètes, sans synthétiser de handles arbitraires.
Le CB2 constant et les métadonnées du pipeline restent ceux du candidat.
Le CB0 littéral natif actif du premier kernel garde son propriétaire et ses
contrôles stricts. L'exception limitée au CB0 inactif n'est pas élargie.

Contrôle causal apparié :8 essais supplémentaires, mêmes préparations et
mêmes deux copies GPU8B. Le témoin réécrit les huit octets corrects ; le
négatif remet seulement les huit premiers octets du binding de lecture
préparé avec dummySrc. Les VA et autres champs restent corrects. Le négatif
retrouve les lectures de canaris, tandis que seed et les compteurs des trois
étapes sont identiques au positif. Chaque variante concorde avec son oracle.
Ce contrôle isole l'effet des champs opaques, sans leur attribuer un format
général ni confondre le négatif attendu avec une réussite de la chaîne complète.

Le runtime utilise l'index constant réfléchi plutôt que la dernière position
supposée. Les slots inactifs sont comptés dans l'étendue du profil. Un même
buffer et offset exacts peuvent être partagés entre entrées du catalogue,
pour le flux de données ; alias intra-entrée, chevauchements partiels,
entrées dupliquées et alias avec les descripteurs restent refusés.

PREUVES DE CETTE VERSION
16 cohortes, {r['dataflow_trials']} essais GTX :
{r['dataflow_exact_uint32_results']:,} résultats uint32 exacts ;
{r['dataflow_consumer_invocations']:,} invocations de kernels comptées ;
{r['dataflow_guard_bytes']:,} octets de garde vérifiés.
Tailles256/1024/4096/32768, groupes locaux32/33/128/256/512/1024.
Modes barrières, copie/reset, soumissions séparées sans attente intermédiaire,
omission de chaque étape/producteur/consommateur, six commandes mutées rejetées.
Huit précontrôles API négatifs et un flux positif dans la même cohorte.
L'oracle reconstruit aussi toutes les banques CB1 : seuls les champs attendus
changent, les entrées complètes correspondent au catalogue natif capturé.

M1 Max : {r['dataflow_M1_native_trials']} nouveaux essais avec les mêmes sources
host/header/MSL, API Metal ordinaires. {r['dataflow_M1_files_identical']} fichiers
de sorties, compteurs et gardes identiques octet par octet sur les trois modes
no_producer/barrier/no_consumer. La synchronisation de la référence positive
emploie set_barrier. Aucune comparaison de vitesse entre architectures.

Non-régression sur EXACTEMENT la bibliothèque ci-dessous :
132 essais XYZ,60 v1,60 v2 trois buffers,24 v2 avec mémoire partagée ;
11 précontrôles API historiques avec6 témoins XYZ positifs ;
129 cohortes historiques/185 étapes et129 oracles hors GPU ;
60 comparaisons de primer et9 contrôles de politique CB0.
La référence M1 XYZ antérieure est réutilisée à sources identiques :
42 essais,1278 fichiers à nouveau comparés aux nouvelles sorties GTX.
83 fichiers système surveillés et plist OCLP inchangés.
Les PID sont terminaux, sans SIGKILL, avec réservation GPU commune libérée.

VERSIONS ET EMPREINTES
GTX880M,registry4294968458 ; iMac macOS26.7.1/build25G241,x86_64,
SDK26.2,Apple clang17.0.0(1700.6.4.2), vérifiés dans environment.json.
La provenance M1 native, son SDK et les empreintes retournées sont archivés
dans command-ir-dataflow-M1-return-20261015/Reference/results/provenance.json.
Git main sans premier commit ; versionnement par instantanés SHA256.
Instantané complet des sources : {r['source_snapshot_SHA256']}
Bibliothèque qualifiée : {lib}
Matérialiseur v2 : {shader}
Compilateur de commandes : {compiler}
Consommateur natif : 7b415aef3f5feb660698dfa0816b11a62d35da9ccc71cd83be170fabd904349f
Pilote inchangé : 2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Mesa26.2.4 /96cb43121031992b85767f9c1be8f3f48e22b1d2.
OpenNVDA /da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5, fork local isolé.
Les manifestes de builds listent toutes les sources, outils, flags et SHA.
L'identité du code importé décrit le payload constructeur ; les résultats,
compteurs et contrôles d'omission établissent séparément le calcul GPU.

REPRODUCTION — DEPUIS BRIDGE, DOSSIERS DE SORTIE NEUFS
python3 tools/build_command_ir_dataflow_client.py \\
 --library results/command-ir-dataflow-library-build-20261015-03 \\
 --compiler results/command-ir-dataflow-compiler-build-20261015 \\
 --materializer results/command-ir-dataflow-materializer-build-20261015-02 \\
 --out results/DATAFLOW-CLIENT-NEW
python3 tools/run_command_ir_dataflow_qualification.py \\
 --build results/DATAFLOW-CLIENT-NEW --out results/DATAFLOW-SUITE-NEW \\
 --prefix DATAFLOW-GPU-NEW
python3 tools/verify_command_ir_dataflow.py results/DATAFLOW-GPU-NEW-barrier \\
 --receipt results/DATAFLOW-GPU-NEW-barrier/recheck.json
Les commandes argv, exécutables signés et empreintes réellement employés
sont conservés dans chaque dossier, y compris pour M1 et les échecs.

LIMITES ET TRANSMISSION
PASS : calcul dépendant, profils/constants2et3 testés, bindings natifs complets,
contrôles de rejet, non-régression citée et comparaison M1.
FAIL conservés : anciennes tentatives ne réécrivant que les VA.
BLOCKED : aucun obstacle empêchant la prochaine expérimentation.
NOT RUN : benchmark de cette version, concurrence/stress prolongé,
groupes partiels, autres espaces/bindings, contrat ICB complet, intégration
transparente des applications habituelles, vidéo/affichage/énergie/8GiB complets.
Catalogue limité à4 entrées,8 candidats et8 commandes ;3ou4 slots contigus,
position constante commune au plan. Buffers Private, alias intra-commande
refusés ; partage inter-entrées seulement au même objet et offset exacts.
Les dispatchs sont sérialisés par WAIT_FOR_IDLE ; pas de gain CPU ou GPU
annoncé. Le coût de préparation supplémentaire n'est pas un gain mesuré.
Niveau2 seulement ; aucune mise à jour installée de pilote ou de Metal.
Branche A : recherche NVIDIA/Linux/FreeBSD distincte, aucun port de code
Linux démontré ici. L'objectif matériel complet reste ouvert.
Qwen job_ids=[] : les deux workers sont accessibles ; aucun instantané de
cette version n'a été transféré à MrWhite. Exécution et intégration en solo.
Prochaine action : élargir les contrats de ressources et durées de vie,
puis la géométrie/les commandes et l'intégration aux applications, en conservant
les chantiers pilote, vidéo, affichage, énergie et mémoire de l'objectif complet.
'''
p=ROOT/'COMMANDES_GPU_FLUX_NATIFS_2026-10-15.txt'
with p.open('x')as f:f.write(text)
print(str(p))

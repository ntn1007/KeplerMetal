#!/usr/bin/env python3
"""Write the bounded engineering report only after final raw-data qualification."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/command-ir-multidimensional-progress-20261015';d=json.loads((OUT/'qualification-receipt.json').read_text());assert d['status']=='PASS'
text=f'''KEPLERMETAL — IR V2, BUFFERS RÉFLÉCHIS ET GÉOMÉTRIE XYZ
15 octobre 2026. Objectif matériel complet ACTIF et NON atteint.

Résultat de la branche B
Le producteur public MSL compute_command peut maintenant alimenter un runtime
v2 qui consomme des programmes NVIDIA natifs avec3ou4buffers contigus,
constantes en dernière position. Les allocations sont validées selon chaque
profil réfléchi enregistré; les noms de fonctions ne sont plus la règle
d'admission de cette voie. Six fonctions sont effectivement qualifiées:
grid_coordinates,manifest_mix,manifest_dynamic et les3shared_mix historiques.
La qualification ne s'étend pas automatiquement aux autres shaders enregistrables.

L'IR version2 conserve128octets par record et ajoute le quatrième pointeur
à l'offset104,avec son propre bit de présence. Le contexte porte explicitement
la version2 et le nombre de bindings. Le frontend exige la version correspondante;
le backend désactivé refuse toujours ces intrinsics. La voie v1 reste distincte.
La géométrie complète X/Y/Z est validée contre les modèles natifs possédés,
avec local/shared identiques au modèle. Les grilles en threads doivent être
divisibles par chaque dimension locale. Groupes partiels NON implémentés.
Le matérialiseur écrit les dimensions QMD et les groupes/threads CB1 cohérents.
Les données de records ne deviennent jamais des adresses arbitraires exécutables:
pipeline,ressources,paramètres et limites proviennent des catalogues détenus.
Le CPU initialise les handles; la géométrie est calculée sur GPU à partir de
mots Private. Pas de lecture CPU des records ou grille avant consommation,
pas de réponses attendues CPU téléversées au GPU.

Preuves de calcul
Le shader grid_coordinates existait déjà dans le projet et reste identique.
Il écrit séparément coordonnées,indices linéaires,indices locaux,indices de
groupes,nombre de groupes et dimensions locales; son compteur est atomique.
Six géométries comprennent du2D/3D,30threads locaux non multiples du warp,
1024threads en32×32 et profondeur locale64. L'oracle CPU reconstruit toutes
les sorties et vérifie tous les octets de garde. Le consommateur est compilé
par NVIDIA; NAK ne remplace pas son programme. Le producteur MSL passe par
notre frontend AIR/NIR/SM30 et le matérialiseur par le compilateur Metal natif.
L'identité du code importé et les métadonnées sont contrôlées au constructeur;
aucune lecture indépendante des instructions résidentes n'est revendiquée.

Qualification sur la bibliothèque finale corrigée
XYZ/quatre buffers:132essais,{{gridwords}}uint32 exacts,
{{gridinvocations}}invocations consommateurs comptées,15types d'IR invalides refusés.
V2/trois buffers:60essais,{{threewords}}uint32 exacts.
V2/mémoire partagée statique et dynamique:24essais,{{combinedwords}}uint32 exacts.
Compatibilité IRv1:60essais,{{v1words}}uint32 exacts.
API:11refus avant producteur/consommateur invalides,suivis de6calculs XYZ corrects.
Historique:129cohortes/185étapes sur23clients nouvellement reliés à cette
même bibliothèque;129oracles réexécutés horsGPU pendant l'audit final.
Cela couvre la suite historique nommée,pas toutes les expériences graphiques
plus récentes du workspace ni toutes les fonctions matérielles de la carte.
M1:42essais natifs nouveaux,{{equal}}fichiers de sorties/compteurs/gardes
identiques à la GTX; mêmes sources client et MSL. macOS27.0.1/build26A434,
SDK27.0,arm64. Les comportements M1 ne sont pas des exécutions Kepler.
Tous les hôtes qualifiés terminent normalement,sansSIGKILL. Réservation commune
pour chaque essai GTX; elle n'exclut pas WindowServer de l'utilisation du GPU.

Contrôles de transport et défaut corrigé
Capture du premier refus XYZ:464octets,masque de banques6 dans les deux flux,
seuls QMD+0x74/+0x78 diffèrent. La normalisation CB0 est désormais fondée sur
la propriété du pipeline,de sa bibliothèque et du profil réfléchi; absence
de littéraux CB0,masques VALID6 dans les deux flux,autres octets intégralement identiques.
60comparaisons de paquets et9contrôles de politique passent. Aucun flux natif
courant différent n'est rejoué; seul le lancement des modèles possédés est écrit.

Le nouveau test d'alias a révélé une erreur réelle de notre fabrique v2:
elle excluait tous les objets égaux au buffer de records,ce qui excluait aussi
un descripteur ou binding natif passé à tort comme records. Le test a arrêté
le processus avant tout producteur/consommateur invalide. La correction ne
saute que l'entrée initiale de la liste et compare les entrées protégées,même
quand elles sont le même objet. Les11refus API passent après correction.
La qualification entière est rejouée sur le nouveau hash. Les129cohortes
de l'ancienne bibliothèque7947557e ne sont pas réattribuées rétroactivement.
Échecs de compilation,de refus primer et de garde d'alias conservés.

Versions et empreintes
Git main,sans commit; sources non suivies identifiées par instantanés SHA256.
Runtime {{library}}
Matérialiseurv2 {{materializer}}
Instantané source {{snapshot}}
ConsommateurXYZ5c35418c2465d1fa87396419c165ac33b5005937e8623fc40329fef30be99de0.
OpenNVDA da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5.
Mesa26.2.4 96cb43121031992b85767f9c1be8f3f48e22b1d2.
ProducteurXYZ4096octets,24GPR,SM30,scratch/CRS/shared0;binding racine48octets.
iMac macOS26.7.1/build25G241,SDK26.2,clang17,x86_64,GTX880M/GK1048Go.
83fichiers système et OCLP revérifiés inchangés. Aucun pilote,kext,framework,
firmware,VBIOS,horloge,protection,WindowServer,SSH ou service Qwen/MLX modifié.
Qwen:job_ids=[]; instantané de revue préparé mais non transféré à MrWhite,
aucune analyse worker revendiquée. Travail et validation assumés en solo.

Reproduction,destinations neuves depuis bridge
python3 tools/build_command_ir_materializer.py --source src/command_ir_materializer_v2.metal --out results/<materializer>
python3 tools/build_command_ir_runtime_library.py --out results/<library>
python3 tools/build_command_frontend.py --source src/gpu_command_frontend_grid3d.metal --entry encode_grid_basic --ir-version 2 --out results/<compiler>
python3 tools/build_command_ir_grid3d_client.py --out results/<client> --library results/<library> --compiler results/<compiler> --materializer results/<materializer>
python3 tools/run_command_ir_runtime.py --build results/<client> --out results/<run> --mode basic
python3 tools/verify_command_ir_grid3d.py results/<run>
Commandes exactes des autres modes,reliages,versions1/2 et129cohortes dans
results/command-ir-v2-final-qualification-20261015 et le reçu de qualification.
Le hash du matérialiseur est épinglé:un rebuild de hash différent doit être
qualifié explicitement; ne pas désactiver le contrôle. Dépendances Mesa/Xcode
du workspace requises; le paquet n'est pas un installateur autonome.

Limites et suite
Extension niveau2 explicitement chargée par une application adaptée. Aucun
pilote installé modernisé,aucun support Metal3/4 global ou transparent.
Constantes actuellement en dernier slot; slots contigus3/4,8records maximum,
modèles natifs et ressources détenus,WAIT_FOR_IDLE après chaque commande.
Restent:autres positions de constantes/layouts,groupes partiels,stage-in,
strides,copies entre contextes,concurrence/dépendances et durées de vie longues,
autres cohortes render/tessellation récentes,client réel aux appels ordinaires.
Vidéo,affichage,énergie et stressVRAM complet restent ouverts. Aucun benchmark
de cette bibliothèque:aucun gain CPU/GPU annoncé.

Branche A indépendante
Le paquet FreeBSD470.256.02 et son checksum officiel sont récupérés sans
installation;51sources publiques sont extraites et33en-têtes sont identiques
à Linux de même version. Les wrappers allocation/sémaphore diffèrent et certains
helpers sont des stubs malgré les déclarations identiques. Aucun portage ou
équivalent XNU n'est établi. Voir le rapport séparé:
../driver-research-2026-10-13/reports/FREEBSD_LINUX_470_256_02_2026-10-15.txt.
Ne pas attribuer les progrès Metal à ce téléchargement de références.
'''
for key,value in {'gridwords':d['grid3d_exact_uint32_words'],'gridinvocations':d['grid3d_consumer_invocations'],'threewords':d['v2_three_buffer_exact_words'],'combinedwords':d['v2_combined_exact_words'],'v1words':d['v1_regression_exact_words'],'equal':d['M1_GTX_raw_files_identical'],'library':d['library_SHA256'],'materializer':d['materializer_v2_SHA256'],'snapshot':d['source_snapshot_SHA256']}.items():text=text.replace('{'+key+'}',str(value))
target=ROOT/'COMMANDES_GPU_XYZ_IR_V2_2026-10-15.txt';target.write_text(text);print(target)

#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];p=r/'results/gpu-generated-bindings-progress-20261014/final-qualification'
d=json.loads((p/'qualification-receipt.json').read_text());assert d['status']=='PASS'and d['independent_oracles_PASS']==146
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ret=json.loads((r/'results/gpu-generated-bindings-M1-return-20261014/M1-freeze.stdout').read_text())
body=f'''KEPLERMETAL — LIAISONS DE RESSOURCES CALCULÉES SUR GPU
Travaux commencés le14 octobre2026, qualification terminée le15 octobre2026
(heure de Paris). Objectif complet : toutes les fonctionnalités matérielles
de la GTX880M sur macOS. Objectif ACTIF, non réalisé. job_ids=[].

Avancée qualifiée, branche B, niveau2
Le GPU réduit les données Private, choisit un programme natif préparé,
calcule le nombre de groupes X et choisit indépendamment une paire
sortie/compteur dans un catalogue borné. Il copie64KiB de constantes,
réécrit les deux adresses de buffers dans CB1 (+8,+40) et l’adresse CB1
du QMD (+0x7c,+0x80), puis le mot de grille (+0x30).
Programme, paramètre constant CB2, tailles locales et allocations
statiques/dynamiques sont conservés. Les candidats utilisent48KiB au total.
Le CPU fournit des buffers et des bornes ; il ne fournit pas de choix résolu
et ne lit aucun choix avant la consommation. Trois programmes et trois
paires de buffers distinctes sont exercés avec des offsets128/160/192
pour les sorties et128/132/136 pour les compteurs.
Le M1 utilise les mêmes sources client/interface, compile en MSL2.3 et
emploie copy_command, set_kernel_buffer et concurrent_dispatch_threadgroups.
Ce banc ne qualifie pas une nouvelle famille Metal ni une API Metal4.

Contrat et limites
Fonctions shared_mix_s128/s1024/s4096, bibliothèque NVIDIA native
b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd.
Grille1D,1..nombre original de groupes, au plus7 et4096 invocations.
Catalogue1..4paires Private, alignements16/4, bornes de la plus grande grille
originale et absence d’alias avec commandes/entrée/autres ressources.
Le scope retient/déclare les6buffers possibles, et cet ownership traverse
les copies. Le client GTX ne déclare pas ces buffers sur son encodeur de
calcul consommateur. Il encode le readback avant d’abandonner ses références.
Les copies de readback peuvent également retenir les ressources ; ce test
ne prouve pas que le scope constitue leur seul propriétaire.
La préparation froide comporte des attentes. Le mode split sépare trois CB
sur la même queue sans attente CPU intermédiaire. Les buffers conservent
le contrat Metal de durée de vie jusqu’à la fin du travail soumis.
Construction MSL générale et intégration transparente restent non réalisées.

Mesures de correction
PASS :8cohortes GTX primaires,1cohorte de refus,129cohortes GTX de
non-régression,8références M1 :146oracles indépendants.
115988 mots uint32 corrects dans les positifs,18432 dans les témoins
causaux,22528 dans le témoin valide suivant105refus d’API attendus.
444 fichiers bruts identiques GTX/M1.3589 fichiers de non-régression
identiques aux captures précédentes. Les flux contenant des adresses GPU
sont vérifiés par décodeur, sans comparer ces adresses entre processus.
23types de clients compilés contre le SDK public sans compiler le cœur ;
le client de refus a été reconstruit après correction de sa fixture.
12contrôles du comparateur de primer passent hors GPU.
83fichiers système surveillés et le plist OCLP sont inchangés.

Échecs conservés, corrections et prudence
FAIL conservé : prepare initial, code-6, avant soumission expérimentale,
différences aux octets332/336 du flux (QMD+0x74/+0x78, CB0).
Le nouveau shader avait laissé une description de CB0 alors que le
consommateur possède un masque6, CB1+CB2. Le comparateur permet désormais
ces seuls deux mots inactifs pour cette bibliothèque certifiée, avec masque6
dans les deux flux. Tous les champs actifs et les autres octets restent exacts.
Les mutations CB0actif, CB1, masque, programme, grille, partagé, registres,
header et CB3 sont refusées. L’hypothèse d’une description inactive sans
effet est étayée par ces contrôles et les résultats GPU ; elle n’est pas
généralisée à d’autres programmes. Ce changement concerne notre transport,
il ne démontre pas un défaut du pilote NVIDIA installé.
FAIL conservé : premier select, code-6, assertion de destruction d’un
encodeur du banc après une tentative de readback au-delà de la durée de vie.
Correction : readback encodé dans le CB consommateur avant perte des références.
FAIL conservé : premier test de refus, code51 ; un buffer de65535octets était
valide pour certaines grilles. La fixture négative utilise maintenant
la borne exacte par essai moins1octet, sans durcir artificiellement l’API.
Deux erreurs de compilation ont été corrigées avant GPU : adresses en mots
uint32 pour MSL2.0 et array<T,N> pour les arguments M1.

Versions, preuves et reproduction
Git main sans commit, laboratoire non suivi ; versions par SHA256.
SDK06 : {d['SDK_archive_SHA256']}
Bibliothèque : {d['static_library_SHA256']}
Shader binaire : {d['bindings_library_SHA256']}
Shader source : {sha(r/'src/gpu_command_bindings.metal')}
Client source : {sha(r/'sdk-combined/examples/gpu_command_bindings_client.mm')}
Bundle source M1 : bc1c910e9cb9e4c6b59c79287bfbdf526a988b625710ca22eb55d928b47756e4
Retour M1 : {ret['SHA256']}
Les13sources du cœur, toolchain/SDK et artefacts liés sont épinglés dans
BUILD_MANIFEST.json et les manifestes d’exécution. Les commandes exactes
figurent dans commands.json/manifest.json/transfer-commands.json.
Paquet SDK : results/gpu-generated-bindings-sdk-build-20261014-06/KeplerMetalSDK
Depuis bridge, avec des dossiers de résultats neufs :
python3 <SDK>/examples/build_gpu_command_bindings_client.py --out <build>
python3 tools/run_gpu_command_bindings.py --build <build> --out results/<cas> --mode select
python3 tools/verify_gpu_command_bindings.py results/<cas>
Modes :prepare/select/range/split/completed/copy/no_producer/no_selector.
Refus :build_gpu_command_bindings_refusals_client.py, mode refusals,
puis verify_gpu_bindings_refusals.py. Le runner M1 du bundle vérifie les
empreintes avant compilation/exécution native arm64.

Sources primaires et méthode
https://developer.apple.com/metal/Metal-Shading-Language-Specification.pdf
Sections6.17.2/6.17.3 : commandes de calcul, bindings et copie.
https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/setkernelbuffer(_:offset:at:)
https://download.nvidia.com/open-gpu-doc/qmd/1/cla0c0qmd.h
QMDv00_06 : CONSTANT_BUFFER_VALID, ADDR_LOWER/UPPER et SIZE.
Skill appliqué : reverse-engineer-anything (local analysis workflow).
REA non connecté/CLI absent ; aucune décompilation ni Evidence REA revendiquée.
Analyse manuelle de captures propres, définitions publiques et contrôles
hors GPU ; aucune modification de configuration ou d’annotations.

Suite
BLOCKED :aucun obstacle empêchant la suite.
NOT RUN :benchmark de cette bibliothèque, programmes arbitraires, autres ABI,
concurrence/pression et intégration transparente aux applications ordinaires.
Ce module étend une application adaptée. Il ne livre pas un pilote système
global ni toutes les fonctions matérielles. Aucun gain de performance annoncé.
Prochaine action : généraliser les états de commande certifiés et qualifier
le chemin de compilation/runtime pour un client utilisant les appels Metal
visés, en conservant les capacités natives existantes et la séparation des
branches modernisation NVIDIA, extension Metal et optimisation applicative.
'''
out=r/'ICB_LIAISONS_GPU_M1_GTX_2026-10-14.txt'
with out.open('x')as f:f.write(body)
print(out)

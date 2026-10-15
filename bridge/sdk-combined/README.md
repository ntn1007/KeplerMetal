# KeplerMetal — SDK expérimental combiné

Cette bibliothèque statique x86_64 contient le scope CPU ICB, ses transports
compute/rendu et la réparation CAS NVIDIA native optionnelle. Elle s'utilise
explicitement depuis une application Objective-C++ adaptée sur l'iMac qualifié.
Le pilote installé, OCLP, les frameworks et les familles Metal restent inchangés.

Le client livré utilise uniquement le header public du scope et les API Metal.
Sa compilation ne recompile aucun fichier d'implémentation du SDK. `-Wl,-ObjC`
est nécessaire pour charger les classes optionnelles découvertes par leur nom,
notamment la factory CAS. Les sources sont incluses pour revue et reconstruction.

Dans le dossier extrait, avec Xcode/SDK macOS :

```sh
python3 examples/build_example.py --out /chemin/neuf/application
python3 examples/run_example.py --build /chemin/neuf/application --out /chemin/neuf/prepare --reservation-root /chemin/bridge --mode prepare
python3 examples/verify_example.py /chemin/neuf/prepare
python3 examples/run_example.py --build /chemin/neuf/application --out /chemin/neuf/gpu --reservation-root /chemin/bridge --mode execute
python3 examples/verify_example.py /chemin/neuf/gpu
```

Le mode `native` conserve le même client/workload et utilise les programmes non
corrigés : l'oracle attend alors les défauts CAS observés. La préparation n'est
pas CPU seule : le transport conserve ses GPU NOP et copies auxiliaires. Aucun
kernel utilisateur ne doit écrire les sorties avant le commit principal.
Le lanceur signe uniquement une copie locale de l'application, conserve PID,
stdout/stderr/statut/SHA, et refuse une observation non terminale. Aucun secret
ni réglage système n'est nécessaire à ces commandes.

L'exemple utilise cinq fonctions, dont quatre certificats CAS, deux groupes,
64/256/1024/128/64 threads selon le record, puis1024 pour tous. Les paramètres
sont liés à l'offset512, les sorties Private à64. Six scénarios couvrent réemploi,
copie/reset, range partiel/vide, rebind et fermeture avant commit. Les données
appelantes bibliothèque/manifeste/certificats sont effacées avant matérialisation.

La reconnaissance CAS reste bornée à une CAS locale weak uint32 publiée dans un
uint4 selon les formes qualifiées. Les certificats sont des diagnostics approuvés
par le développeur ; ils ne sont ni des signatures d'une autorité ni une preuve
générale de sûreté. Le chargeur crée les fonctions depuis ses bytes vérifiés,
conserve la réflexion native et vérifie les programmes/métadonnées reçus par le
constructeur. Les GPR/lancement/shared restent natifs ; seul le compte
d'instructions est normalisé. Les arguments inactifs doivent être déclarés et
correspondre à la réflexion ; ils ne sont pas des bindings ICB requis.

Le profil épingle GeForceMTLDriver16.0.12/16.0.0 SHA
`2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054`.
Une autre version doit être auditée. Sérialiser l'utilisation du scope et toute
interposition du constructeur dans ce processus. Sur une erreur d'encodage,
abandonner le command buffer. Les ressources/indices doivent respecter le
manifeste ; il ne fournit pas une validation générale des shaders arbitraires.

Ce paquet ne fournit pas un contrat ICB complet ni une construction générale des ICB par GPU,
ni une intégration transparente dans les applications ordinaires. Les autres
fonctions du matériel, les CFG/alias/types/orders CAS, les erreurs et les charges
sous pression/concurrence restent à qualifier. Aucun gain de vitesse annoncé.
Le drapeau qualification-pending conserve l'état de création ; le reçu externe
de test atteste les octets du paquet sans réécrire l'archive.

## Client de tables constantes CB0

La bibliothèque contient aussi le transport des banques natives CB0 de 256,
512 et 1024 octets. Les profils épinglent le code, la taille et le propriétaire
NVMTLFunctionVariant ; les données de la banque sont conservées natives.
Ce support est qualifié sur les quatre fonctions LUT incluses, sans revendiquer
toutes les tailles, allocations ou programmes possibles.

Le client public utilise des tables16/64/128/256, des tailles65/4113/16321,
des groupes64/256/128/512 puis1024, et des offsets distincts du laboratoire.
Les données appelantes de bibliothèque/manifeste sont effacées après leur
chargement. Il couvre reset d'un slot, plage vide, copie/reset et fermeture
avant commit. La référence native crée directement les pipelines Metal.

```sh
python3 examples/build_literal_client.py --out /chemin/neuf/client-lut
python3 examples/run_literal_client.py --build /chemin/neuf/client-lut --out /chemin/neuf/prepare-lut --reservation-root /chemin/bridge --mode prepare
python3 examples/verify_literal_client.py /chemin/neuf/prepare-lut
python3 examples/run_literal_client.py --build /chemin/neuf/client-lut --out /chemin/neuf/gpu-lut --reservation-root /chemin/bridge --mode execute
python3 examples/verify_literal_client.py /chemin/neuf/gpu-lut
```

Lancer `native` dans un autre dossier pour la référence numérique. Valider
la préparation et l'oracle avant toute exécution du programme utilisateur.
`--reservation-root` doit être le même dossier pour les lanceurs coopérants,
avec un sous-dossier results existant. Le verrou est transmis à l'enfant ;
un résultat interrompu/non attesté reste bloqué. Cela ne réserve pas tout
le matériel contre WindowServer ou les applications non coopérantes.
Les anciennes archives SDK restent figées et n'utilisent pas ce nouveau protocole.

## Sous-ensemble FP64 optionnel

Un paquet construit avec `--fp64-programs` contient `KeplerFP64.h` et les
programmes SM30 approuvés. `KPBinary64Library` copie et vérifie les empreintes
du carrier et des quinze programmes avant leur import. Il réutilise le même
mutex d'import et la restauration du constructeur que le module CAS.

Les opérations sont addition, multiplication, FMA, division et racine carrée,
arrondi au plus proche pair. Entrées : doubles contigus (pas8) ou champs `value`
de `KPBinary64Record` (pas16). Sorties : records16octets contenant la valeur,
l'index et un témoin d'exécution choisi par l'appelant. Cela permet d'enchaîner
les opérations sur buffers GPU sans compaction ou lecture intermédiaire CPU.
Le client possède commit/wait ; l'API encode dans son command buffer Metal.
Les tailles de groupes32/128/1024 et ressources Shared/Private avec tracking
sont acceptées. Ranges, alignement, chevauchement, arité et profils sont vérifiés
avant de créer l'encoder. Voir le header pour les bornes et responsabilités.
Le plafond de count est une borne du contrat, pas une qualification de chaque
taille ou pression mémoire jusqu'à ce plafond.

Le client indépendant teste les22combinaisons de pas pour les cinq opérations
puis une chaîne DIV→SQRT→FMA→ADD→MUL. Il efface ses bytes source après chargement
et libère la bibliothèque avant le dernier commit. Les refus d'empreinte,
stride, alignement, chevauchement, arité, range et profil sont vérifiés. Le
contrôle `no_producer` omet le premier maillon et doit produire la différence
attendue, avec les gardes intactes. Le premier essai peut utiliser `--trials 1`.

```sh
python3 examples/build_fp64_client.py --out /chemin/neuf/client-fp64
python3 examples/run_fp64_client.py --build /chemin/neuf/client-fp64 --out /chemin/neuf/prep-fp64 --reservation-root /chemin/bridge --mode prepare
python3 examples/verify_fp64_client.py /chemin/neuf/prep-fp64
python3 examples/run_fp64_client.py --build /chemin/neuf/client-fp64 --out /chemin/neuf/gpu-fp64 --reservation-root /chemin/bridge --mode execute
python3 examples/verify_fp64_client.py /chemin/neuf/gpu-fp64
```

Ces extensions s'utilisent explicitement dans une application adaptée. Elles
n'ajoutent pas le type `double` au frontend MSL, une conformité IEEE exhaustive
ou une capacité déclarée aux applications ordinaires. La qualification publiée
doit attester les bytes précis du paquet avec un reçu externe ; l'archive garde
son drapeau pending à la création. Aucun gain de performances n'est déduit.

Les commandes résidentes copiées par GPU acceptent aussi le profil dynamique
enregistré dans `cpu_icb_dynamic_resident_manifest.json`. Les deux programmes
natifs de cet exemple utilisent trois buffers, avec paramètres à un offset non
nul. L'allocation du groupe est portée par le QMD copié. Le runtime vérifie le
mot de longueur dans les commandes courantes et leurs propriétaires retenus
avant copie et exécution. Ce mot doit être lisible par le CPU ; les buffers
Private sont refusés pour ce paramètre. Le client doit conserver les contenus
et respecter leur synchronisation jusqu'à la fin du travail GPU.

```sh
python3 examples/build_cpu_icb_dynamic_copy_client.py --out /chemin/neuf/client-dynamic
python3 examples/run_dynamic_resident_copy.py --build /chemin/neuf/client-dynamic --out /chemin/bridge/results/NEW-DYNAMIC --reservation-root /chemin/bridge --mode range
python3 examples/verify_dynamic_resident_copy.py /chemin/bridge/results/NEW-DYNAMIC
```

Les six modes de copie sont `prepare`, `chain`, `range`, `chain_completed`,
`range_completed` et `no_second`. Le client de refus se construit avec
`build_cpu_icb_dynamic_bounds_client.py` et utilise le même lanceur, avec
`prepare_bound`, `prepare_private`, `copy_bound`, `owner_bound` ou
`execute_owner_bound`. Son vérificateur est `verify_dynamic_resident_bounds.py`.
Les preuves incluent 48 Kio et 1 024 threads dans un même groupe sur la GTX.
Le reçu externe décrit les essais réalisés sur les octets du SDK. Les autres
ABI et les ICB générés par GPU restent à qualifier. Cette interface reste une
extension applicative.

Le profil `cpu_icb_combined_shared_manifest.json` ajoute trois kernels avec
512, 4 096 ou 16 384 octets statiques, plus l'argument dynamique0. La base de cet
argument est vérifiée contre la taille statique réfléchie, le prélude natif et
le snapshot de constantes. Les deux régions sont contrôlées par des sommes et
lectures croisées. Leur total peut atteindre 48 Kio dans les scénarios qualifiés.
Les six modes de `build_cpu_icb_combined_shared_copy_client.py` utilisent
`run_combined_shared_copy.py` et `verify_combined_shared_copy.py`. Le client
`build_cpu_icb_combined_shared_bounds_client.py` reprend les cinq contrôles de
refus avec `verify_combined_shared_bounds.py`. La qualification est bornée aux
profils et séquences attestés par le reçu externe.

`KPGPUCommandSelection` ajoute un chemin de sélection GPU entre des commandes
natives préparées. Le kernel de décision réduit 32 entiers Private par ligne ;
le kernel suivant copie le QMD du candidat choisi. Les bornes, le domaine de
registration et le kernel de sélection sont vérifiés avant encodage. La
bibliothèque de ce kernel est épinglée dans le runtime. Les ressources de tous
les candidats sont retenues jusqu'à la fin ; aucune lecture CPU du choix
n'intervient entre les étapes.

Après `enableGPUCommandSelectionWithLibraryData:expectedSHA256:error:`, créer le
plan avec `newGPUCommandSelectionFromBuffer:sourceRange:destination:destinationRange:input:inputOffset:nonce:error:`.
Encoder son producteur puis sa sélection dans le même command buffer, ou dans
des buffers commités dans cet ordre sur la même queue. Les compteurs et choix
Private peuvent être lus par blit après completion pour vérifier les résultats.
Sans producteur, la sélection utilise le choix0 initialisé : c'est un contrôle
causal explicite. La préparation froide utilise des blits et des attentes.

Le CPU doit reset un slot choisi par GPU avant de le réencoder. Un snapshot CPU
ne peut pas recopier son état inconnu ; la copie GPU de ce slot est disponible
et conserve les propriétaires possibles. L'exécution reste sérielle dans ce
transport. Ce chemin sélectionne des commandes existantes et ne fournit pas un
frontend MSL général pour créer des commandes arbitraires.

```sh
python3 examples/build_gpu_command_selection_client.py --out /chemin/neuf/client-selection
python3 examples/run_gpu_command_selection.py --build /chemin/neuf/client-selection --out /chemin/bridge/results/NEW-SELECTION --reservation-root /chemin/bridge --mode select
python3 examples/verify_gpu_command_selection.py /chemin/bridge/results/NEW-SELECTION
```

Les modes sont `prepare`, `select`, `range`, `split`, `completed`, `copy`,
`no_producer` et `no_selector`. Le client de refus utilise
`build_gpu_command_selection_refusals_client.py`, le mode `refusals` et
`verify_gpu_selection_refusals.py`. La référence M1 encode les copies avec
`compute_command.copy_command` natif, selon la spécification MSL §6.17.
Le reçu externe atteste les octets, le niveau applicatif2 et les limites.

La génération GPU d’un préfixe de grille est une extension distincte de la copie
de commandes. Après activation du module `enableGPUCommandGeometryWithLibraryData`,
`newGPUCommandGeometryFromBuffer` crée un plan pour les trois fonctions `shared_mix`
de la bibliothèque b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd.
Le GPU réduit des données Private, choisit un candidat et calcule le nombre de groupes X
entre 1 et le nombre original, limité à 7. La taille des groupes, les programmes,
les ressources et la mémoire partagée sont conservés. Les bornes originales du
manifest restent requises (4096 invocations, donc au plus 4 groupes de 1024).
Les deux machines utilisent la même règle ; le M1 emploie `compute_command.copy_command`
puis `concurrent_dispatch_threadgroups`, la GTX copie le QMD validé et modifie son
seul mot X à l’offset 0x30. La table de limites utilise un pointeur `device const`
pour conserver la banque de constantes native ; la vérification stricte des commandes
reste active. `generatedGeometry` contient un témoin Private par ligne à l’offset64,
à lire uniquement après la fin de l’exécution. Les emplacements deviennent inconnus
pour le CPU et doivent être réinitialisés avant toute modification partielle CPU.
Ce module ne fournit pas une implémentation générale des commandes MSL ni une
intégration transparente aux applications ordinaires. La qualification matérielle
est fournie séparément du manifeste de build ; aucun gain de performance n’est promis.

Le module `enableGPUCommandBindingsWithLibraryData` et le plan
`newGPUCommandBindingsFromBuffer` ajoutent la sélection de ressources sur GPU
aux kernels shared_mix certifiés. Un catalogue comporte1..4paires
`output`, `counter`, `outputOffset`, `counterOffset` ; les buffers Private
doivent être disjoints et dimensionnés pour la plus grande grille originale.
Le GPU choisit le programme, la grille et une paire de ressources, puis
réécrit la table CB1 et l’adresse CB1 du QMD. Les buffers possibles sont
retenus/déclarés par le scope, et l’ownership traverse les copies GPU.
`generatedGeometry` utilise deux uint4 par destination à l’offset64.
Les données de retour doivent être copiées avant d’abandonner les ressources ;
la durée de vie requise va jusqu’à la fin du travail soumis.
Le comparateur de primer admet exclusivement les deux mots de description
CB0 lorsque cette banque est désactivée dans les deux masques6 et que le
consommateur est un programme shared_mix certifié. Tous les autres octets
restent exacts, notamment les champs actifs et les banques de literals CB0.
Cette interface reste une extension pour application adaptée, sans contrat
MSL général, changement de famille GPU ou déploiement dans le pilote système.

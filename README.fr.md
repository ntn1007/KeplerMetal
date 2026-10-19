# KeplerMetal

**Objectif ultime : créer un pilote NVIDIA modernisé pour macOS qui exploite au maximum les capacités matérielles des GPU Kepler et prenne en charge le plus grand nombre de fonctionnalités Metal réellement réalisables sur ce matériel.** La carte de référence est une GeForce GTX 880M, GK104 / SM30, de 8 Gio de VRAM dans un iMac Intel.

À terme, nous visons une intégration native à macOS permettant aux applications Metal habituelles de bénéficier de ces capacités sans adaptation spécifique. Les progrès sont évalués par la justesse des calculs GPU, la stabilité et des benchmarks sur des charges précises.

Le travail suit deux axes complémentaires :

1. **Moderniser le pilote NVIDIA :** corriger le compilateur et le runtime natifs, améliorer la gestion du GPU et de la mémoire, la soumission des commandes et la synchronisation, puis vérifier la stabilité et les performances.
2. **Étendre les fonctionnalités Metal :** faire évoluer le compilateur, le runtime, les ressources et les commandes, en évaluant les fonctions de Metal 2/3/4 une par une selon les capacités réelles du matériel.

**État actuel : recherche et prototypes expérimentaux validés.** Le dépôt partage le code lisible, les correctifs ciblés, les outils de reproduction et les preuves GPU qui préparent ce pilote. L’intégration actuelle passe encore par des applications adaptées ; le pilote système complet et la prise en charge générale de Metal 3/4 restent à réaliser. Les composants propriétaires Apple/NVIDIA sont récupérés séparément et ne sont pas redistribués ici.

[English](README.md) · [Compilation](docs/BUILDING.md) · [Dépendances](docs/DEPENDENCIES.md) · [État des travaux](docs/STATUS.md) · [Architecture](docs/ARCHITECTURE.md)

## Avancées récentes

L’import explicite accepte maintenant des profils de mémoire privée de 8 et 16 Kio par thread. L’archive publique reconstruite avec ses sept objets passe 226 dispatchs sur la GTX 880M, 612 120 valeurs exactes et les contrôles de coexistence CAS. [Commandes, empreintes et limites](docs/LARGE_LOCAL_MEMORY.md). Cette extension reste expérimentale ; aucun pilote système ni gain de performances n’est annoncé.

Le nouveau module SDK conserve un instantané des commandes natives et respecte les frontières demandées, y compris `setBarrier`. Quatre commandes s’entrelacent correctement ; deux groupes séparés respectent l’ordre atomique attendu. La qualification laboratoire couvre 292 dispatchs corrects, avec une qualification distincte de l’artefact public. [API, sources et limites](docs/NATIVE_RESIDENT_BATCH.md). Le témoin administrateur exécuté par l’utilisateur réussit aussi l’ouverture/fermeture du port ; la vidéo matérielle reste non démontrée. [Preuves d’accès](docs/VIDEO_ADMIN_ACCESS.md).

Deux kernels compilés par NVIDIA présentent maintenant des durées d’exécution entrelacées sur la GTX 880M, avec des descripteurs et constantes indépendants. Le prototype borné passe 34/34 paires au laboratoire ; une reconstruction distincte depuis les sources publiques passe 16/16 paires et 62 dispatchs corrects, contrôles séquentiels compris. L’encodeur Metal ordinaire reste séquentiel ; aucun gain de vitesse n’est annoncé. [Sources, preuves et reproduction](docs/NATIVE_RESIDENT_OVERLAP.md).

Le démarrage natif du décodeur est maintenant observé. Trois essais finaux créent correctement le premier pixel buffer dans AppleGVA, puis la création du décodeur refuse encore-12913. Les17nouveaux processus produisent18images logicielles exactes, aucune image matérielle. [Preuves et prochaine dépendance](docs/VIDEO_NATIVE_START.md).

La fabrique vidéo native est maintenant identifiée et renvoie un pointeur valide. Une entrée de politique AppleGVA ajoutée uniquement dans notre processus change le refus matériel de-12906 à-12913 dans trois essais ; quatre témoins gardent-12906. Aucun décodage matériel n'est encore obtenu. Les19processus produisent30images logicielles exactes et conservent explicitement20réponses internes FinF/Inva en erreur. [Preuves, code et prochaine cible](docs/VIDEO_FACTORY_POLICY.md).

Le gestionnaire vidéo natif fonctionne maintenant dans notre processus de test :24images logicielles correspondent exactement au CPU sur ce chemin. Le refus matériel-12906 persiste ; AppleGVA10.0.20 est désormais observé dans ce processus. [Preuves, sources et limites](docs/VIDEO_LOCAL_SERVICE.md).

Dépendance GPU : le rôle de `IOGVACodec` dans la sélection GVA est confirmé par trois essais contrôlés, avec le même binaire. Le décodage matériel reste en échec ; 24 images logicielles sont exactes. [Preuves et reproduction](docs/VIDEO_DEPENDENCIES.md).

Les essais par l’API publique H.264 et MPEG‑2 produisent des images CPU exactes, mais les neuf créations avec matériel obligatoire échouent encore sans image. L’entrée modèle qui corrige la disponibilité VP3 ne suffit donc pas pour ces chemins. [Résultats et prochaine cible](docs/VIDEO_CODEC_SELECTION.md).

Une barrière d’éligibilité vidéo est maintenant reproduite : la requête AppleVA passe de −8973 à 0 dans trois processus de test recevant seulement une entrée `iMac11,1` en mémoire. Sept contrôles gardent le refus. Le système reste inchangé et le décodage matériel demeure non démontré. [Preuves et limites](docs/VIDEO_ELIGIBILITY.md).

Dernière enquête vidéo : six images décodées en logiciel sur l’iMac correspondent exactement à une référence CPU FFmpeg indépendante. Le décodage matériel reste refusé. Le WebVA NVIDIA officiel contient les mêmes deux stubs que la copie de support examinée ; aucun remplacement vidéo fonctionnel ni gain n’est annoncé. [Sources, preuves et suite](docs/VIDEO_TRANSPORT.md).

## Démarrer

```sh
git clone https://github.com/ntn1007/KeplerMetal.git
cd KeplerMetal
python3 tools/check_publication.py
python3 -m unittest discover -s tests -v
python3 tools/build_from_source.py --out build/source-local
```

La dernière commande exige macOS, Xcode et sa chaîne Metal. Elle compile les sources et vérifie l'édition de liens sans lancer de calcul GPU ni modifier le système.

- [Compilation et limites de reproduction](docs/BUILDING.md)
- [Récupérer les dépendances Apple/NVIDIA](docs/DEPENDENCIES.md)
- [Fonctions validées et travaux restants](docs/STATUS.md)
- [Architecture et séparation des deux branches](docs/ARCHITECTURE.md)
- [Raccordement des pipelines par l'API publique](docs/NATIVE_FUNCTION_PIPELINES.md)
- [Contribuer](CONTRIBUTING.md)

Après **un seul enregistrement de bibliothèque**, les appels Metal ordinaires chargent la bibliothèque et créent les fonctions, pipelines et encodeurs adaptés. Les alias et appels asynchrones sont conservés ; le client ne fait plus d'enregistrement manuel par fonction ni d'adaptation manuelle par encodeur. La qualification couvre **296 essais GTX**, 31 583 232 valeurs exactes et 12 essais M1 avec 156 fichiers communs identiques. Les six fonctions et programmes restent épinglés : les shaders arbitraires et l'intégration transparente aux applications ordinaires restent à réaliser. [Preuves et limites](docs/library-function-validation.json).

Le transport accepte aussi les programmes SM30 à mémoire locale et débordements de registres : **180 essais de calcul et 48 contrôles sans dispatch**, jusqu'à 4 Kio privés par thread et 1 024 threads par groupe. Les fonctions natives existantes sont conservées. Cette étape étend notre backend ; elle ne remplace pas le pilote installé. [Contrat et reproduction](docs/LOCAL_MEMORY.md).

La correction de réservation native dispose maintenant d'une API dans le transport MRC commun : instantanés immuables, verrou partagé et contexte par thread. Elle conserve le code NVIDIA et passe228essais sur17profils, complétés par les refus, la durée de vie, le CAS, la mémoire locale et une concurrence contrôlée des créations de pipelines. Un défaut de concurrence de notre adaptateur CAS a été corrigé. L'archive laboratoire totalise383command buffers, dont359dispatchs de calcul, et822 116valeurs exactes. Les composants système restent inchangés. Aucun gain de vitesse n'est annoncé. [Contrat et limites](docs/NATIVE_ALLOCATION_API.md).

Deux programmes nouveaux, aux niveaux source104et120, passent aussi par cette API inchangée :24essais supplémentaires de durée de vie pour chacune des archives laboratoire et publique. Quatre seuils entre réservations adjacentes sont mesurés, sans transformer leur corrélation en règle universelle. [Résultats et reproduction depuis les sources](docs/NATIVE_ALLOCATION_THRESHOLDS.md).

La lecture des commandes natives préparées identifie maintenant les champs de mémoire locale et de CRS sur deux profils. Une réserve de métadonnées de4 096 produit un champ CRS de4 608 : neuf calculs corrigés passent, six échecs natifs restent conservés. Aucun paquet n’est modifié ou rejoué ; la règle générale reste à établir. [Cartographie, preuves et reproduction](docs/NATIVE_ALLOCATION_QMD.md).

Deux blocs successifs de 65 et 55 niveaux passent avec la réserve testée de 2 560, alors que l’ancien programme à 120 niveaux imbriqués échouait à 3 584. Le programme segmenté contient pourtant davantage de `joinat` : le comptage total n’explique pas ces réservations suffisantes différentes. Neuf nouveaux calculs passent, six échecs numériques restent conservés. Aucun estimateur automatique ni gain de VRAM n’est annoncé. [Expérience, sources et limites](docs/NATIVE_SEGMENTED_CONTROL.md).

Aucun pilote propriétaire, firmware, SDK, exécutable ou résultat binaire n'est publié. Les liens et empreintes permettent de retrouver les références séparément. Le code original est sous licence MIT ; les dépendances conservent leurs propres licences.

La chaîne MSL → AIR → NIR → SM30 couvre maintenant les tableaux privés et les débordements de registres du profil testé : 180 essais de calcul, 48 contrôles sans dispatch et résultats identiques au chemin natif. [Contrat, limites et reproduction](docs/AIR_LOCAL_MEMORY.md).

Contrôle de flot profond : les imports testés avec une pile externe jusqu’à2Kio passent. Un programme natif à96niveaux démarre puis ne produit pas son résultat final ; cet échec reste ouvert et conservé. [Investigation et limites](docs/CONTROL_FLOW.md).

La première expérience distincte corrige les programmes NVIDIA natifs65/96 en augmentant leur réservation mémoire, sans remplacer leur code GPU :24 essais corrects,35 872 valeurs exactes. Les48 contrôles de rejeu et d’arrondi restent défectueux. Le même metallib d’origine passe sur le M1 Max, avec adaptation explicite de certains groupes. À cette première étape, la correction était limitée au processus de test et à deux profils ; elle n’est pas installée dans le système et aucun gain de vitesse n’est annoncé. [Preuves, sources et reproduction](docs/NATIVE_CONTROL_RESERVE.md).

La qualification suivante couvre17 profils natifs et228 essais GPU corrects, dont24 essais après effacement des entrées du client et vidage du pool de construction :340 784 valeurs exactes et85 196 témoins d’invocation. Dix contrats invalides sont réellement refusés avant dispatch. Le runtime commun et le pilote installé restent inchangés ; leur raccordement et sa qualification constituent la prochaine étape. [Résultats actuels et limites](docs/NATIVE_CONTROL_RESERVE_QUALIFICATION.md).

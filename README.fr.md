# KeplerMetal

Registre des décodeurs : 25 processus terminés, 3 715 contrôles ABI et 42 images logicielles exactes. Les neuf demandes matérielles restent en échec, y compris avec les deux flags publics. La dépendance IOGVA absente reste une piste à vérifier. [Preuves et reproduction](docs/VIDEO_REGISTRY.md).

Les essais par l’API publique H.264 et MPEG‑2 produisent des images CPU exactes, mais les neuf créations avec matériel obligatoire échouent encore sans image. L’entrée modèle qui corrige la disponibilité VP3 ne suffit donc pas pour ces chemins. [Résultats et prochaine cible](docs/VIDEO_CODEC_SELECTION.md).

Une barrière d’éligibilité vidéo est maintenant reproduite : la requête AppleVA passe de −8973 à 0 dans trois processus de test recevant seulement une entrée `iMac11,1` en mémoire. Sept contrôles gardent le refus. Le système reste inchangé et le décodage matériel demeure non démontré. [Preuves et limites](docs/VIDEO_ELIGIBILITY.md).

Recherche open source pour moderniser la pile NVIDIA Kepler sous macOS, avec une GTX 880M GK104 / SM30 de 8 Gio comme matériel de référence.

Dernière enquête vidéo : six images décodées en logiciel sur l’iMac correspondent exactement à une référence CPU FFmpeg indépendante. Le décodage matériel reste refusé. Le WebVA NVIDIA officiel contient les mêmes deux stubs que la copie de support examinée ; aucun remplacement vidéo fonctionnel ni gain n’est annoncé. [Sources, preuves et suite](docs/VIDEO_TRANSPORT.md).

Deux branches restent distinctes : corriger ou améliorer la pile NVIDIA existante, et étendre les fonctions Metal accessibles aux applications. Le dépôt partage le code lisible, les tests, les vérificateurs CPU et les correctifs des outils libres.

**État expérimental :** intégration dans des applications adaptées. Le projet ne fournit pas encore un pilote système de remplacement ni une compatibilité Metal 3/4 complète. Les essais historiques qualifient des fonctions précises ; ils ne prouvent pas un gain général de performances.

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

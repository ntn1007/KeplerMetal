# KeplerMetal

Recherche open source pour moderniser la pile NVIDIA Kepler sous macOS, avec une GTX 880M GK104 / SM30 de 8 Gio comme matériel de référence.

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

La dernière qualification couvre six variantes de création de pipelines, dont les appels asynchrones, pour six fonctions explicitement enregistrées : 128 essais GTX et 12 comparaisons M1. Les limites et les empreintes des sources sont documentées ; l'intégration transparente aux applications ordinaires reste à réaliser.

Aucun pilote propriétaire, firmware, SDK, exécutable ou résultat binaire n'est publié. Les liens et empreintes permettent de retrouver les références séparément. Le code original est sous licence MIT ; les dépendances conservent leurs propres licences.

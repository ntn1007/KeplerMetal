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

Après **un seul enregistrement de bibliothèque**, les appels Metal ordinaires chargent la bibliothèque et créent les fonctions, pipelines et encodeurs adaptés. Les alias et appels asynchrones sont conservés ; le client ne fait plus d'enregistrement manuel par fonction ni d'adaptation manuelle par encodeur. La qualification couvre **296 essais GTX**, 31 583 232 valeurs exactes et 12 essais M1 avec 156 fichiers communs identiques. Les six fonctions et programmes restent épinglés : les shaders arbitraires et l'intégration transparente aux applications ordinaires restent à réaliser. [Preuves et limites](docs/library-function-validation.json).

Le transport accepte aussi les programmes SM30 à mémoire locale et débordements de registres : **180 essais de calcul et 48 contrôles sans dispatch**, jusqu'à 4 Kio privés par thread et 1 024 threads par groupe. Les fonctions natives existantes sont conservées. Cette étape étend notre backend ; elle ne remplace pas le pilote installé. [Contrat et reproduction](docs/LOCAL_MEMORY.md).

Aucun pilote propriétaire, firmware, SDK, exécutable ou résultat binaire n'est publié. Les liens et empreintes permettent de retrouver les références séparément. Le code original est sous licence MIT ; les dépendances conservent leurs propres licences.

La chaîne MSL → AIR → NIR → SM30 couvre maintenant les tableaux privés et les débordements de registres du profil testé : 180 essais de calcul, 48 contrôles sans dispatch et résultats identiques au chemin natif. [Contrat, limites et reproduction](docs/AIR_LOCAL_MEMORY.md).

Contrôle de flot profond : les imports testés avec une pile externe jusqu’à2Kio passent. Un programme natif à96niveaux démarre puis ne produit pas son résultat final ; cet échec reste ouvert et conservé. [Investigation et limites](docs/CONTROL_FLOW.md).

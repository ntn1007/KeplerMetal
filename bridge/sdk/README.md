# KeplerMetal SDK expérimental — applications adaptées

Ce paquet expose le sous-ensemble KeplerMetal déjà qualifié sur cet iMac GTX
880M. Il s'utilise explicitement depuis une application Objective-C++ adaptée.
Il ne remplace ni le pilote NVIDIA, ni Metal, ni OCLP. Les capacités déclarées
par le device restent celles du système. L'objectif du projet reste plus large
que ce SDK.

Le paquet contient une bibliothèque statique x86_64, le header public, les
sources exactes, les assets SHA vérifiés, le catalogue de qualification et un
exemple indépendant. Le runtime reste lié à la disposition privée du pilote
qualifié : une autre version de pilote doit être auditée avant utilisation.

## Construire et vérifier l'exemple

Dans un dossier extrait neuf, sur l'iMac qualifié avec Xcode/SDK macOS :

```sh
python3 examples/build_example.py --out /chemin/absolu/dossier-neuf
python3 examples/run_example.py --build /chemin/absolu/dossier-neuf --out /chemin/absolu/prepare-neuf
python3 examples/verify_example.py /chemin/absolu/prepare-neuf
python3 examples/run_example.py --build /chemin/absolu/dossier-neuf --out /chemin/absolu/gpu-neuf --execute
python3 examples/verify_example.py /chemin/absolu/gpu-neuf
```

Le build compile uniquement le client et son shader, puis lie la bibliothèque
livrée. Il ne recompile aucun fichier d'implémentation KeplerMetal. `-Wl,-ObjC` est
nécessaire : le transport rendu est découvert par nom de classe dans l'archive
statique. Omettre ce flag peut retirer ce composant à l'édition de liens.

Le runner crée le dossier de sortie et conserve PID, statut, argv, stdout,
stderr et empreintes de la copie signée localement. Sa signature ad hoc porte
sur l'application seule. Il ne modifie aucune protection du système. Si une
observation n'est pas terminale, inspecter ce processus avant une reprise.

L'exécutable prend l'asset de préparation, la bibliothèque du client, son
manifeste, un dossier de résultats et le mode `prepare` ou `execute`. Lancer
d'abord `prepare` et vérifier ses résultats avant une soumission GPU. Le
vérificateur indépendant fourni explique aussi les commandes de reproduction.

## Contrat public

1. Créer le device et la queue Metal ordinaires.
2. Installer un `KPCPUICBScope` sur ce device avec l'asset natif qualifié.
3. Enregistrer des shaders et leur ABI manifeste à partir d'instantanés SHA
   vérifiés. Un enregistrement n'atteste pas leur justesse GPU.
4. Utiliser les objets CPU ICB via les sélecteurs Metal publics dans ce scope,
   puis créer l'encodeur avec `renderEncoderWithDescriptor:commandBuffer:error:`.
5. Garder les ressources valides et sérialiser les opérations du scope.
6. Appeler `restore` quand le scope doit fermer. Les leases des soumissions
   déjà encodées sont conservés jusqu'à leur completion.

Le scope pose ses méthodes sur des sous-classes sans ivar de ses propres
instances ; les classes natives partagées ne sont pas modifiées. Un device ne
peut pas servir simultanément à plusieurs scopes indépendants.

L'exemple utilise un shader client différent des fixtures et un rendu BGRA8
128×96, puis vérifie les cas natif, ICB, range vide, copy/reset et fermeture
avant commit. Cela qualifie un client adapté et ce contrat borné ; une réussite
n'établit pas la compatibilité de toutes les applications Metal.

## Périmètre qualifié et limites

Consulter `qualification.json` et les rapports d'origine pour les nombres,
formats et limites exacts. Les principales fonctions sont les ICB CPU compute
et rendu, les profils déclarés, les ressources natives, les tableaux privés
copiés/sélectionnés sur GPU et les états profondeur/stencil dans les fixtures.
Le coût CPU et les gains de performances de ce SDK ne sont pas mesurés.

Les tables privées retournées ne doivent pas être écrites par le client. Ce
contrat est coopératif ; le runtime ne détecte pas toute mutation privée
arbitraire. Les commandes restent matérialisées et copiées par le CPU, avec une
amorce native par record. Le format ICB GPU-résident, la génération GPU des
commandes, la conformité complète, la pression/concurrence et l'intégration
transparente dans les applications habituelles restent ouverts.

Les APIs unsupported peuvent lever `KeplerCPUICBUnsupported`. Sur un échec de
validation pendant l'encodage, abandonner le command buffer : ne pas soumettre
un enregistrement partiellement encodé. Les manifests sont des engagements
d'ABI et de ressources ; ils ne rendent pas sûrs des indices privés hors bornes.

Ne copier aucun fichier du SDK dans `/System/Library` et ne charger aucun kext.

## Provenance

`BUILD_MANIFEST.json` conserve SHA sources, objet/archive, compilateur/SDK et
commandes. `FILE_MANIFEST.json` inventorie chaque fichier livré. Le carrier et
le selector livrés ont les SHA des versions GPU qualifiées. Les sources
du runtime et des shaders sont incluses pour contre-lecture. Le SDK n'est pas
un portage de corrections propriétaires NVIDIA Linux.

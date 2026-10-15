# KeplerMetal — module expérimental de réparation CAS native

Ce module optionnel de la branche A s'appelle explicitement depuis un client
Objective-C++ adapté. Il corrige le code produit par le backend NVIDIA pour une
fonction et un certificat AIR/SASS approuvés. Il n'installe aucun pilote et ne
change aucune famille Metal. L'intégration transparente reste à développer.

`KPCreateCertifiedNativeCASPipeline` prend les octets de la bibliothèque et du
certificat, avec leurs SHA256 attendus. Il copie les entrées, vérifie l'entrée
AIR indexée, le programme original et les métadonnées effectivement reçus du
pilote, puis importe le trampoline. Seul le compte d'instructions est normalisé
dans les métadonnées. GPR, lancement et mémoire partagée restent natifs.
Le constructeur NVIDIA est temporairement interposé dans ce processus puis
restauré ; sa présence dans d'autres processus est inchangée.

Les certificats sont des diagnostics approuvés par le développeur, pas des
signatures d'une autorité ni une preuve générale de sûreté d'un shader. La
reconnaissance est limitée à une CAS locale weak uint32 et sa publication dans
un uint4. Les alias, CFG, types, ordres et autres profils restent à qualifier.
Un certificat doit être qualifié sur GPU avant usage applicatif. Le drapeau
`GPU_qualification_pending` conserve son état de création ; le reçu externe
de qualification relie les octets livrés aux tests réellement exécutés.

L'application doit sérialiser ce module avec toute autre interposition du
constructeur dans son processus. Une importation sans callback vérifié retourne
nil. Une autre version de pilote doit être auditée : le profil actuel épingle
GeForceMTLDriver16.0.12/16.0.0, SHA
`2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054`.

Le header déclare le pipeline retenu, y compris sous ARC. Les copies immuables
et les programmes sont associés au pipeline pour leur durée de vie. L'exemple
efface les entrées appelantes avant commit et teste 33/128/1024 threads,
trois groupes, deux variantes, trois graines et quatre formes réparées.
Le cinquième shader conserve volontairement le comparand : il est refusé par
la réparation et reste exécuté par Metal natif dans les tests positifs.

Dans le SDK extrait :

```sh
python3 examples/build_example.py --out /chemin/neuf/application
codesign --force --sign - /chemin/neuf/application/cas_example
mkdir -p /chemin/neuf/prepare-outputs
/chemin/neuf/application/cas_example /chemin/SDK/assets /chemin/SDK/assets/client-manifest.json /chemin/neuf/prepare-outputs prepare
```

La signature ad hoc ne porte que sur l'application. Pour un test GPU, employer
le lanceur surveillé `tools/run_native_cas_sdk.py` du workspace et l'oracle
`tools/verify_native_cas_sdk.py`, selon le rapport joint. Vérifier la préparation
avant de passer au mode execute. Aucun fichier ne doit être copié dans le
système ni chargé comme kext. Aucun benchmark de ce module n'est revendiqué.

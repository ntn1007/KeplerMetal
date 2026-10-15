#!/usr/bin/env python3
"""Write the scope and caller ownership contract after final verification."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/command-ir-lifetime-progress-20261015';r=json.loads((OUT/'qualification-receipt.json').read_text());assert r['status']=='PASS'and not r['objective_complete']
text=f'''KEPLERMETAL — DURÉE DE VIE DES COMMANDES ET RETOURS MRC/ARC
15 octobre 2026 — correction de notre SDK et de ses exemples, niveau2

Deux défauts de notre code sont corrigés. Aucun pilote NVIDIA installé,
framework, OCLP, service ou firmware n'est modifié.

1. ABANDON D'UN COMMAND BUFFER NON SOUMIS
L'exemple retenait le plan depuis le callback de terminaison. Le plan retient
son command buffer : CB → callback → plan → CB. Sans commit, le callback
ne s'exécute pas et les objets restent vivants. Le témoin conserve ce comportement.
Le callback retient maintenant root, push, pipeline et la liste immuable
commandIRProducerResources. Il ne retient ni le plan ni le command buffer.
La correction couvre les exemples dataflow/XYZ et le générateur des clients v1/v2.
Dans4 abandons corrigés, les références faibles plan/scope/ICB/record/binding/
root/buffer Private/pipeline deviennent nulles après libération des propriétaires.
Dans4 abandons témoins, le cycle et les objets retenus restent observés.
Les command buffers principaux abandonnés ont le statut NotEnqueued et ne sont
jamais commit. Aucun résultat numérique GPU n'est attribué à ces huit cas.

2. CONVENTION DES SIX FONCTIONS C D'IMPORT
Les fonctions MRC renvoient des objets +1, comme leur commentaire le promet.
La déclaration ne transmettait pas cette convention à l'appelant ARC.
NS_RETURNS_RETAINED est ajouté aux fonctions compute/fragment/vertex/
tessellation/graphics/host-buffer. Les corps MRC sont inchangés.
Le contrôle CPU utilise exactement le même objet MRC +1 :6objets non détruits
avec l'ancienne déclaration,6 détruits avec la déclaration annotée.
Ce modèle teste la convention C, pas une exécution des six factories NVIDIA.
Le même défaut est observé sur le vrai pipeline compute GTX :4anciens
pipelines restent vivants,4annotés sont libérés ;16fichiers de résultats et
compteurs sont identiques. Même objet MRC, même code GPU et même bibliothèque.
La recompilation MRC avec le nouvel en-tête conserve aussi exactement les
mêmes octets objet :e88a2c7e1538798e9635c37e2a91b9d4d31f6fc85352853a00bea629c35341e6.
Les appelants ARC recompilés prennent correctement la propriété +1.
Les anciens exécutables ne sont pas corrigés rétroactivement.

QUALIFICATION FINALE DES APPELANTS RECOMPILÉS
{r['final_GPU_cohorts']} cohortes/{r['final_trials']} essais avec la bibliothèque inchangée.
36essais de durée de vie :28 command buffers principaux soumis,8 abandonnés.
Vidage du pool de l'appelant avant commit, fermeture explicite ou destruction
du scope, séparation producteur/consommateur, copie/reset et omissions.
32scénarios corrigés concordent ;4contrôles reproduisent la rétention ancienne.
64essais du client de calcul complet, contrôles d'omission/rejet et gardes.
69essais de clients XYZ,v1,v2 trois buffers et mémoire partagée combinée.
{r['exact_uint32_results']:,} résultats uint32 exacts et
{r['counted_consumer_invocations']:,} invocations consommatrices comptées.
M1 Max :12 nouveaux essais avec le même host/MSL/header applicable,
156fichiers de sorties, compteurs et gardes identiques à la GTX.
Toute observation faible est bornée aux objets de ces tests ; elle ne prouve
pas la purge des caches internes NVIDIA ni la libération physique de toute VRAM.
Pas de benchmark, de gain CPU/VRAM chiffré ni de conformité ICB complète.

PROVENANCE
Git main sans premier commit. Sources/versionnées par instantané SHA256 :
{r['source_snapshot_SHA256']}
En-tête d'import :{r['import_header_SHA256']}
Implémentation MRC inchangée :{r['import_implementation_SHA256']}
Bibliothèque KeplerMetal inchangée :{r['library_SHA256']}
Matérialiseur inchangé :{r['materializer_SHA256']}
La qualification antérieure de129cohortes concerne exactement ce même binaire
de bibliothèque. Elle n'a pas été réexécutée et ne qualifie pas, à elle seule,
les nouveaux appelants. Ceux-ci sont couverts par les43cohortes ci-dessus.
Les83fichiers système surveillés et le plist OCLP sont de nouveau identiques.
macOS26.7.1/build25G241,SDK26.2,clang17,x86_64 ; pilotes épinglés comme au jalon
précédent. Commandes, outils, sources, exécutables signés et PID sont archivés.

CONTRAT D'UTILISATION
Conserver useResource pour les ressources indirectes et retainedReferences=YES.
La rétention protège leur durée de vie ; elle ne remplace pas leur déclaration
au GPU. Exemple de conservation du producteur :
 NSArray *keep = @[root, pushBuffer, producerPipeline,
                   plan.commandIRProducerResources];
 [producerCB addCompletedHandler:^(id<MTLCommandBuffer> completed) {{
     (void)keep.count;
 }}];
Ne pas capturer le plan ou le command buffer depuis ce callback.
Le scope peut être restauré après tout l'encodage, avant commit, dans les
scénarios qualifiés. Après restore, ne pas encoder de nouvelles commandes via
ce scope. En cas d'abandon non soumis, restaurer le scope et relâcher les
propriétaires du plan, des ICB et du command buffer. Un ICB conservé conserve
volontairement ses templates et ressources. Les appels MRC gardent leur gestion
manuelle +1 ; les appelants ARC doivent inclure le nouvel en-tête et être recompilés.

REPRODUCTION — DOSSIERS NEUFS, DEPUIS BRIDGE
python3 tools/check_import_return_ownership.py --out results/RETURN-CPU-NEW
python3 tools/build_command_ir_lifetime_client.py \\
 --client results/command-ir-dataflow-client-build-20261015-04 \\
 --library results/command-ir-dataflow-library-build-20261015-03 \\
 --return-header src/KeplerProgramImport.h --recompile-import \\
 --out results/LIFE-CLIENT-NEW
python3 tools/run_command_ir_lifetime_cases.py --full \\
 --build results/LIFE-CLIENT-NEW --out results/LIFE-SUITE-NEW --prefix LIFE-NEW
python3 tools/verify_command_ir_lifetime.py results/LIFE-NEW-restore \\
 --receipt results/LIFE-NEW-restore/recheck.json
Les variantes cancel_legacy et cancel_leases gardent des attendus distincts.
Le lanceur doit rester unique sur la GTX ; le verrou coopératif est conservé.

SOURCE DE LA CONVENTION ARC
Clang, Automatic Reference Counting, Retained return values :
https://clang.llvm.org/docs/AutomaticReferenceCounting.html#retained-return-values
L'attribut indique au compilateur la propriété du résultat. Les observations
CPU et GTX ci-dessus vérifient séparément notre implémentation et ses limites.

TRANSMISSION
Objectif matériel complet conservé. Actions : correction annulation, propriété
ARC/MRC, reliaison et qualification des appelants. job_ids=[] ; aucun travail
Qwen délégué, aucune copie actuelle transférée à MrWhite. Deux MCP accessibles.
PASS :43cohortes finales, convention CPU6factories, comparaison réelle compute,
M1 et vérification système. FAIL conservés :ancienne rétention circulaire et
retour C implicite, comme contre-exemples étiquetés. BLOCKED :aucun.
NOT RUN :durée de vie GPU des factories graphiques/tessellation/NoCopy sous ARC,
concurrence/pression/VRAM complète, identité ICB dans MTLArgumentEncoder,
intégration transparente, performances, vidéo/affichage/énergie et port Linux.
L2 uniquement ; l'objectif d'une pile/pilote général reste incomplet.
Prochaine action :qualifier les autres factories puis le contrat argument-encoder/
ICB utilisé par une application réelle, sans modifier les composants système.
'''
with(ROOT/'COMMANDES_GPU_DUREE_VIE_2026-10-15.txt').open('x')as f:f.write(text)
print('lifetime report written')

#!/usr/bin/env python3
"""Freeze compiled-library repair and native indirect-transport evidence."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/metallib-transport-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
cas=read(ROOT/'results/metallib-native-preservation/independent-verification.json');indirect=read(ROOT/'results/indirect-compute-native-qualified/independent-verification.json')
symbols=read(ROOT/'results/indirect-transport-audit/symbol-resolution-rechecked/verification.json');liveness=read(ROOT/'results/metallib-liveness-final/verification.json');clobber=read(ROOT/'results/native-cas-clobber-rejection/verification.json')
assert cas['status']=='PASS' and cas['correct_CAS_operations']==8694 and cas['all_native_metadata_preserved']
assert indirect['status']=='PASS' and indirect['consumer_invocations_counted']==11580 and not indirect['ICB_implemented']
assert symbols['MetalOld']['selector_resolved']=='doesNotRecognizeSelector:' and clobber['status']=='PASS' and not clobber['GPU_dispatch']
strategy=read(LAB/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json');system=[]
for row in strategy['system_files']:
 actual=sha(Path(row['path']));assert actual==row['sha256'];system.append({'path':row['path'],'sha256':actual})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert sha(rootpatch)==strategy['rootpatch_sha256']
assert len(system)==len({r['path'] for r in system})==83
archives=[]
for name,expected in [('KEPLERMETAL_CAS_RESSOURCES_CPU_2026-10-13.zip','d217b82cf46c6285c884a921641928e16e5824b76ba1d4f770b74ba9637a7c04'),('KEPLERMETAL_CAS_SEMANTIQUE_ICB_2026-10-13.zip','77f383018c38db7c6c0f2028bd64d4bf988fe48628805650b5d013153fc8be59')]:
 p=ROOT/name;assert sha(p)==expected;archives.append({'path':str(p),'sha256':expected})
inputs=[];children=[]
cohorts=['metallib-native-preservation','metallib-planner-positive','metallib-planner-semantic-control','metallib-liveness-final','native-cas-clobber-rejection','indirect-transport-audit','indirect-compute-native','indirect-compute-native-corrected','indirect-compute-native-qualified']
for name in cohorts:
 for p in (ROOT/'results'/name).rglob('*.json'):
  inputs.append({'path':str(p),'sha256':sha(p)})
  m=read(p)
  if isinstance(m,dict) and 'signed_executable' in m:
   assert not m['SIGKILL_requested'] and not m['authoritative_ps_status']
   current=subprocess.run(['ps','-o','stat=,command=','-p',str(m['pid'])],capture_output=True,text=True).stdout.strip();assert m['signed_executable'] not in current
   children.append({'PID':m['pid'],'exit_code':m['exit_code'],'terminal':True,'current_ps':current})
head=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=ROOT,capture_output=True,text=True)
provenance={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'objective':'Toutes les fonctionnalités matérielles de GTX880M sur macOS; objectif global toujours incomplet.',
 'Git':{'repository':str(LAB.parent),'branch':subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip(),'commit':head.stdout.strip() if head.returncode==0 else None,'local_changes':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)},
 'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),
 'SDK':subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip(),'OpenNVDA_commit':'da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5','envytools_commit':'f102b82381f3f11cee113d16374c87091db039d9',
 'NAK_used_for_new_repairs':False,'system_files':system,'system_files_unchanged':83,'rootpatch_sha256':sha(rootpatch),
 'unchanged_previous_packets':archives,'own_signed_children':children,'inputs':inputs,'Qwen_job_ids':[],'system_modified':False}
dump(OUT/'provenance.json',provenance)
summary={'library_native_CAS':{k:v for k,v in cas.items() if k!='results'},'native_GPU_indirect_compute':{k:v for k,v in indirect.items() if k!='results'},
 'ICB_transport_static':symbols,'register_liveness':liveness,'clobber_rejection':clobber,
 'all_hardware_functions_supported':False,'Metal3_or_4_qualified':False,'transparent_integration':False,'system_modified':False,'Qwen_job_ids':[]}
dump(OUT/'summary.json',summary)
report=f'''KEPLERMETAL — METALLIB ET TRANSPORT INDIRECT, 13 octobre 2026

Objectif conservé: toutes les fonctions matérielles de GTX880M sur macOS,
modernisation native A et extensions Metal B. L’état global reste incomplet.
Tour précédent classé PROGRESS: correcteur AIR/SASS, trois-mode benchmark et
lacunes ICB localisées. Ce tour ajoute les preuves suivantes, exécutées sur iMac.
Git main sans commit; Qwen job_ids aucun; sources exécutées archivées et hashées.
Les 83 fichiers système inventoriés et le plist OCLP sont inchangés.

Branche A: correction depuis une bibliothèque compilée, sans source séparée

Une metallib contient quatre fonctions nommées, dont trois CAS à réparer et
un témoin qui conserve volontairement le comparand. Le lecteur utilise la
table NAME/TYPE/OFFT/MDSZ, vérifie HASH SHA256 du module AIR inclus et les bornes;
aucune recherche aveugle de magic bitcode. Un conteneur corrompu, un offset hors
borne, une longueur incohérente et une fonction absente sont refusés sans GPU.
Le format thin MTLB actuel est qualifié; universal et native-only restent refusés.
Les sidecars .metal/.air ne sont pas des entrées du plan d’exécution. Le module
AIR dérivé et le JSON typé restent conservés comme preuves internes générées.

Sélection explicite des noms: cas_slot_one, cas_noise_live, cas_result_swizzle,
keep_original_comparand. Le candidat valide non défectueux est refusé avant
pipeline. Le correcteur découvre adresse partagée, registres et composante.
Une vérification de liveness refuse aussi une mutation correctement décodée
qui détruit old avant sa comparaison tardive. Ce contre-exemple n’est pas exécuté.

L’import isolé conserve désormais les 232 octets de métadonnées d’origine,
comparés au payload arrivant réellement au constructeur; GPR natifs 7/8 et
launch words 736/544. La version précédente utilisait GPR24 et 576/576.
Les ressources, LDS et ABI natives restent celles de la fonction compilée.
Les tailles/lien du conteneur changent pour le code étendu; un mot original
redirige vers la membar rejouée et le MOV de réparation, suivis du retour.
12 configurations GPU, 36 captures, 8694 CAS et 34776 mots uint32 corrects,
33/128 threads × trois groupes, contention, equal/miss, trois graines.
4608 octets de garde intacts; registres décodés 7/8 et metadata préservée vérifiés.
Aucun gain de débit mesuré. Ces opérations répètent les shapes précédents
avec le nouveau chemin bibliothèque/metadata; ce ne sont pas trois nouvelles
familles d’atomiques. Les autres erreurs Invalid Resource restent distinctes.
Le mot metadata0 est corrélé à code_words-1 dans les captures originales;
sa signification complète et les effets d’une extension de code restent à
auditer avant généralisation, malgré la justesse des captures de ce profil.

Outil générique de diagnostic: plan_native_metallib_repair.py reçoit seulement
library et function, extrait l’AIR exact, contrôle sa sémantique, capture le
programme natif et classe sa structure. Il ne dispatch pas et ne déploie pas
un candidat nouveau. Client automatique L2 et intégration transparente L3
restent à construire; la pile installée est inchangée.

Branche B: primitives natives de transport réellement utilisables

GPU produce_grid écrit trois uint32 (groups,1,1) dans un buffer Private,
puis le même command buffer encode un consume_grid indirect sans lecture
de ces valeurs par notre CPU. Le kernel rapporte sa géométrie et local size,
incrémente un compteur global, puis écrit un témoin déterministe par invocation.
Direct et indirect utilisent le même consumer. Résultats et géométrie identiques.
Neuf formes: local32/33/128, groups1/3/5, trois graines chaque fois.
Neuf contrôles directs, neuf GPU-indirect et six contrôles sans producteur;
216 captures brutes (sortie, arguments, compteur), 11580 invocations comptées,
41688 mots positifs corrects, gardes et espaces de sortie non écrits intacts.
Sans producteur, les arguments restent à un groupe et les sorties destinées
à trois/cinq groupes comptent 15054 mots incorrects: négatifs préservés.
Cette capacité était déjà native; aucun objet ICB ajouté, aucun benchmark.

Échecs de préparation conservés: première compilation rejetait un mélange
d’attributs scalaires/vectoriels, corrigé avant GPU. Ensuite une garde supposait
Private.contents==nil et a arrêté avec exit4 avant upload/dispatch. L’inventaire
de rendu antérieur indiquait déjà Private.storageMode2 avec contents disponible.
La garde corrigée vérifie storageMode2; le CPU ne lit pas les arguments avant
exécution. Le prototype positif prouve la consommation des dimensions écrites
par GPU, sans tirer de conclusion du seul getter ou de l’allocation.

Audit de transport, sans soumission ou copie de command stream:
GeForceMTLDriver SHA2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054,
UUIDdc9e7ee82b923fc39524fcae13d2f69d.
dispatchThreadgroups direct0xd57fa; indirect0xd5e53, fin voisine0xd68b9;
draw indirect0x111ed6; indexed indirect0x1120e1. IMP et image UUID concordent.
L’indirect compute accède au descripteur MTLIOAccelResource._res (symbole GOT
0x1c0240), additionne l’offset à son adresse et enregistre la ressource via
IOAccelResourceListAddResource0x187574/MTLResourceListAddResource0x18760a.
Le code émet des mots de command buffer; l’ABI privée du contexte, les paquets
et leur réutilisation restent à qualifier. Aucun appel à un helper privé fait.

ICB rendu: méthodes0xced53 et0xced68 héritées de MTLIOAccelRenderCommandEncoder
dans MetalOld, pas dans NVMTLRenderCommandEncoder_KEPLER_A.
Les chaînes dyld sont résolues avec le format6 du SDK fixup-chains.h: cellule
0x230110 → doesNotRecognizeSelector:, cellule0x1e0b60 → objc_msgSend.
Ce sont des chemins de refus, pas une exécution native de commandes indirectes.
Compute ICB demeure no-op; factories maxCount manquent; command_buffer compilé
pour GPU demeure refusé dans le chemin natif. Trois obstacles logiciels,
aucune incapacité GK104 inférée. CPU ICB et génération GPU restent distincts.

Commandes reproductibles, depuis le bridge, répertoires de sortie frais:
python3 tools/reproduce_metallib_native_repair.py --out results/metallib-repro-NEW
python3 tools/verify_metallib_native_repair.py --input results/metallib-repro-NEW
python3 tools/plan_native_metallib_repair.py --library results/metallib-native-preservation/library.metallib --function cas_noise_live --out results/plan-NEW
python3 tools/reproduce_indirect_transport_audit.py --out results/transport-repro-NEW
python3 tools/resolve_indirect_symbols.py --out results/symbols-repro-NEW
python3 tools/reproduce_indirect_compute.py --out results/indirect-repro-NEW
python3 tools/verify_indirect_compute.py --input results/indirect-repro-NEW
Sources/arguments/SHA exacts dans chaque commands.json et provenance.json.
Upstreams: OpenNVDA da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5, Envytools
f102b82381f3f11cee113d16374c87091db039d9. Clang17.0.0/clang-1700.6.4.2,
SDKMacOSX26.2, macOS26.7.1/25G241; MSL2.4 CAS et2.0 indirect.
L’archive nécessite le workspace et les dépendances épinglées; aucun pilote
ou exécutable système installable n’est livré.
Référence officielle de l’API indirecte:
https://developer.apple.com/documentation/metal/mtlcomputecommandencoder/dispatchthreadgroups(indirectbuffer:indirectbufferoffset:threadsperthreadgroup:)

Prochaine action A: auditer les champs de metadata liés à taille/instructions,
élargir liveness/CFG/alias et contraintes ABI, puis composant d’intégration L2
avec correcteur natif et client distinct. Ne pas appliquer un candidat non qualifié.
Prochaine action B: lire le command stream créé par le transport NVIDIA dans
le seul processus, identifier adresses/ressources à retenir/relocaliser et contrat
de réutilisation avant implémentation ICB. Aucun objet vide ou simple rejeu CPU
présenté comme support ICB natif. Génération GPU exige ensuite ABI/compiler.
L’histoire des améliorations Linux reste indépendante; aucun port appliqué.

PASS: bibliothèques indexées et HASH, correction GPU avec metadata d’origine,
contre-exemples de sémantique/liveness, GPU-indirect exact et contrôles de manque
de producteur, identité/symboles et 83 empreintes système.
FAIL conservés: préparation scalar/vector puis garde Private trop stricte;
les autres témoins natifs fautifs restent dans les archives antérieures.
BLOCKED: ICB natif actuel (factory, exécution/compilation).
NOT RUN: vraie réutilisation command stream, ICB ajouté, L2/L3 et gain pilote.
L’objectif matériel complet reste ACTIVE et NON ATTEINT.
'''
(ROOT/'METALLIB_TRANSPORT_NATIF.txt').write_text(report);(OUT/'RAPPORT.txt').write_text(report);(OUT/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
coverage_path=ROOT/'results/hardware-coverage.json';coverage=read(coverage_path)
updates=[{'category':'Compiled-library native CAS repair with original metadata','status':'sample_qualified_application_local',
 'tested_scope':'Selected function from four-entry indexed metallib; embedded AIR HASH and bounds verified. Three repaired shapes,12GPU configurations,36captures,8694CAS correct. Original metadata232B preserved, native7/8GPR, launch736/544. Semantic/control and malformed container refusals.',
 'remaining_requirements':'Universal/native-only libraries, broader CFG/alias/ABI/types/orders; code-size-related metadata audit and independent L2 client integration. Current candidates not automatically deployed to applications.',
 'evidence':['results/metallib-native-preservation/independent-verification.json','results/metallib-liveness-final/verification.json','results/native-cas-clobber-rejection/verification.json']},
 {'category':'Native GPU-produced indirect compute geometry','status':'sample_qualified_native_API',
 'tested_scope':'Private args produced on GPU then indirect consumer on same command buffer;9forms local32/33/128 groups1/3/5,3seeds, exact direct-match output/geometry/counter;6missing producer controls,11580invocations,41688positivewords,guards unchanged.',
 'remaining_requirements':'Broader resource/stage/control patterns, reusable native command representation and actual ICB CPU/GPU contracts; performance not benchmarked.',
 'evidence':['results/indirect-compute-native-qualified/independent-verification.json','results/indirect-transport-audit/analysis.json']}]
names={r['category'] for r in updates};coverage['coverage']=[r for r in coverage['coverage'] if r['category'] not in names]+updates;coverage['complete']=False;dump(coverage_path,coverage)
dump(OUT/'delivery.json',{'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in [ROOT/'METALLIB_TRANSPORT_NATIF.txt',OUT/'RAPPORT.txt',OUT/'summary.json',OUT/'provenance.json',coverage_path]],'system_files_unchanged':83,'all_hardware_functions_supported':False})
print(json.dumps({'report':str(ROOT/'METALLIB_TRANSPORT_NATIF.txt'),'CAS_operations':8694,'indirect_invocations':11580,'system_files_unchanged':83,'global_complete':False},indent=2))

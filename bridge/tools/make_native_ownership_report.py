#!/usr/bin/env python3
"""Freeze the current verified branch A/B progress without rewriting old cohorts."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/native-ownership-progress';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
gpu=read(ROOT/'results/indirect-descriptor-gpu-readback/independent-verification.json');owners=read(ROOT/'results/native-command-ownership/independent-verification.json');count=read(ROOT/'results/native-metadata-count-normalized/independent-verification.json')
assert all(r['status']=='PASS' for r in [gpu,owners,count]);assert gpu['consumer_invocations']==4917 and gpu['QMD_words_changed']==24 and gpu['constant_state_words_changed']==108
baseline=read(LAB/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json');system=[]
for row in baseline['system_files']:
 path=Path(row['path']);actual=sha(path);assert actual==row['sha256'];system.append({'path':str(path),'sha256':actual})
assert len(system)==83 and len({r['path'] for r in system})==83
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert sha(rootpatch)==baseline['rootpatch_sha256']
cohorts=['driver-runtime-layout','native-command-capture','native-command-relocation-capture','native-metadata-count-normalized','native-resource-ownership','native-command-ownership','native-retention-observed','indirect-descriptor-gpu-readback']
inputs=[];children=[]
for name in cohorts:
 for path in (ROOT/'results'/name).rglob('*.json'):
  inputs.append({'path':str(path),'sha256':sha(path)});obj=read(path)
  if isinstance(obj,dict) and 'signed_executable' in obj:
   assert obj['exit_code']==0 and not obj['SIGKILL_requested'] and not obj['authoritative_ps_status']
   state=subprocess.run(['ps','-o','stat=,command=','-p',str(obj['pid'])],capture_output=True,text=True).stdout.strip();assert obj['signed_executable'] not in state
   children.append({'pid':obj['pid'],'terminal':True,'signed_executable':obj['signed_executable']})
gitroot=LAB.parent;head=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=gitroot,capture_output=True,text=True)
provenance={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Git':{'repository':str(gitroot),'branch':subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=gitroot,text=True).strip(),'commit':head.stdout.strip() if head.returncode==0 else None,'local_changes':subprocess.check_output(['git','status','--short'],cwd=gitroot,text=True)},'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'system_files':system,'system_files_unchanged':83,'rootpatch_sha256':sha(rootpatch),'inputs':inputs,'children':children,'Qwen_job_ids':[],'system_modifications':False}
dump(OUT/'provenance.json',provenance)
summary={'native_CAS':{k:v for k,v in count.items() if k!='results'},'ownership':{k:v for k,v in owners.items() if k not in ['records','lifetime_records']},'native_indirect_readback':{k:v for k,v in gpu.items() if k!='records'},'all_hardware_functions_supported':False,'ICB_implemented':False,'system_files_unchanged':83,'system_modifications':False,'Qwen_job_ids':[]}
dump(OUT/'summary.json',summary)
report='''KEPLERMETAL — RESSOURCES NATIVES ET MODIFICATIONS DE DESCRIPTEURS SUR GPU
13 octobre 2026 — Travail solo; objectif global ACTIVE, PROGRESS réel, non terminé.

Objectif conservé: toutes les fonctionnalités matérielles de GTX880M sous macOS,
avec branche A modernisation NVIDIA et branche B extension Metal distinctes.
Git main sans commit: instantanés et SHA256, aucun commit inventé; aucun job Qwen.

A — Métadonnées du shader CAS natif corrigées dans notre processus

Le mot0 de metadata 0x10004 alimente FunctionVariant+44 et le champ de performance
_MTLPipelinePerformanceKeyInstructionCount (loader0x177fdf, consommateur0x109289).
Après extension SASS64B, instruction-count103→111 ou111→119, selon la convention
code_words-1 qualifiée. GPR7/8, launch736/544 et autres bytes metadata préservés.
Six configurations,18captures,1782CAS et7128uint32 corrects,2304octets de garde.
Le compilateur installé reste inchangé; généralisation AIR/SASS/ABI limitée,
autres erreurs Invalid Resource non résolues. Pas de gain CAS mesuré.
Voir METADATA_COMMAND_STREAM.txt et native-metadata-count-normalized.

B — Allocation, propriété et durée de vie du transport NVIDIA

NVMTLCommandQueue._queue est à+680; son type runtime déclare InternalTextures,
cinq références ObjC à+8/+16/+24/+32/+40. Dans nos observations ce sont cinq
NVMTLBuffer. Le champ+16 est le backing QMD4096B, le champ+32 le backing de
constant buffers393216B (six zones64K). Adresses et spans des uploads/CB des
descripteurs correspondent aux gpuAddress/length des objets vivants, pas à
des allocations inventées. Le mapping vendor.reserved[1] de _res à gpuAddress
est vérifié dans les snapshots bruts des buffers.

Trois command buffers simultanément retenus ont des objets/PushBuffer/State
distincts. Les pointers nativeCompute+8/+16/+24/+32/+40 recoupent Device,
CommandQueue, CommandBuffer, PushBuffer, State. Le layout CommandBuffer typé
donne2664B, les champs+0x118/+0x120/+0x128/+0x130 recoupent les mêmes pointers.
Les backings GPU de la file sont partagés; le stream direct identique est
retrouvé malgré des objets de commande distincts.

Correction de nomenclature: dans le snapshot initial, la clé device_cpp
nommait prématurément State+8. Ce n'est pas le Device global. State+0 pointe
vers le vrai Device et State+8 vers un grand état de dispatch distinct par CB.
Le vérificateur refuse cette confusion; les captures originales restent intactes.

Qualification de rétention, sans submission: après drainage des autorelease
pools et suppression des références locales, le CB retainedReferences=true
garde output/counter/args vivants (trois répétitions, neuf références privées).
Le contrôle unretained a ces neuf références faibles nulles avant submission,
comme attendu. Après libération du CB, les privés sont tous libérés. Paramètres
Shared restent vivants; libération immédiate de queue/QMD varie (couplée dans
nos observations). Aucune garantie universelle de cache/destruction ou résidence
après complétion n'est extrapolée. Le contrôle unretained n'a jamais été soumis.

Correction du décodeur: CB_CONFIG_1.SIZE[31:15] est une taille en octets,
confirmée Envytools et Mesa nve4_cp_launch_desc_set_cb(...size). L'ancien x256
était une erreur d'unité; corrected decode conservé séparément du premier JSON.
CB1=65536B, CB2=512B dans la capture précédente, et non16M/128K. Alignement
d'adresse256B distinct de cette taille; longueur MTLBuffer applicative distincte
du span CB arrondi annoncé au matériel. Calculs/mesures GPU précédents inchangés.

B — Ce que l'indirect modifie réellement sur le GPU

Nous réutilisons produce_grid/consume_grid natifs MSL2.0 et leurs oracles déjà
qualifiés. Le producer écrit des arguments Private, puis le consumer utilise
dispatchThreadgroupsWithIndirectBuffer dans le même CB, sans lecture CPU de
ces arguments. La capture CPU des paquets est prise immédiatement autour de
l'appel public consumer, avant commit, sans écritures de mémoire privée.

Après completion, un deuxième CB blit copie les buffers QMD et CB vivants de
notre file vers des buffers Managed gardés; synchronizeResource puis lecture.
Aucun paquet injecté ou rejoué, aucune modification d'une allocation interne.
Programmes NVIDIA natifs, aucun import NAK dans ce chemin.

Six configurations: direct, GPU_indirect, contrôle sans producteur, pour
local33/groupes3 et local128/groupes5; trois graines chacune,18exécutions.
4917 invocations consumers comptées;17736uint32 positifs exactement corrects;
7419mots incorrects attendus contre l'oracle complet des contrôles négatifs.
108captures brutes (sortie/args/compteur/QMD/CB/stream); gardes intactes.

Direct: un QMD et un lancement, descriptor CPU/GPU identique. Indirect:
helperQMD+0x100 et userQMD+0x0; helper lancé avant utilisateur. Le QMD CPU
utilisateur a une grid nulle. RelectureGPU: seuls mots+0x30 et+0x34 passent
à groups et0x10001 (X,Y=1,Z=1); le contrôle sans producer donneX=1. HelperQMD
reste identique. Douze exécutions indirectes,24mots QMD modifiés, autres bytes
exacts. Programme helper SM30 résidant non désassemblé dans cette expérience.

Le bloc de constantes natif utilisateur128B, à CBbase+0x6f0, change neuf mots:
+0x10/+0x14/+0x18: groups,1,1;
+0x30/+0x34/+0x38: groups*local,1,1;
+0x50/+0x54/+0x58: groups,1,1.
Les placeholdersCPU étaient nuls.108mots CB modifiés en douze exécutions;
les autres bytes des trois uploads de constantes (helper128B, table96B,
état utilisateur128B) sont exactement préservés. C'est une preuve GPU plus
précise que la seule géométrie de sortie. Une extension ICB devra traiter les
constantes builtin, pas uniquement le QMD ou le nombre de threads.

Limites et suite

PASS: correction metadata CAS; matching objects/ranges; rétention bornée;
GPU indirect, QMD et constantes, oracles et négatifs;83empreintes système.
BLOCKED dans la pile actuelle: factory ICB maxCount absente; compute/blit
execute no-op; render execute forward doesNotRecognizeSelector:; compiler
air.command_buffer refusé. Aucun de ces obstacles remplacé par un objet vide.
NOT RUN: replay persistant, nouvel objet ICB CPU/GPU, helper SASS, runtime L2/L3,
conformité globale, Linux port, performances. Objectif global incomplet.

Prochaine expérience: représentation native persistante avec références fortes
aux pipelines/resources et backings dédiés, puis qualification des modifications
de bindings et réutilisation dans notre processus. Tout client de test devra
annoncer son niveau L1; la cible reste l'usage par les applications habituelles.
Ne pas recopier un stream avec adresses d'un CB libéré, ni prétendre qu'une
séquence d'appels CPU est un ICB matériel ou une intégration transparente.

Reproduction depuis le bridge, dossiers neufs, aucune installation système:
python3 tools/reproduce_native_metadata_count.py --out results/count-REPRO-NEW
python3 tools/verify_native_metadata_count.py --input results/count-REPRO-NEW
python3 tools/reproduce_native_resource_ownership.py --out results/owner-REPRO-NEW
python3 tools/reproduce_native_retention.py --out results/life-REPRO-NEW
python3 tools/verify_native_ownership.py --input results/owner-REPRO-NEW --retention results/life-REPRO-NEW
python3 tools/reproduce_indirect_descriptor_readback.py --out results/readback-REPRO-NEW
python3 tools/verify_indirect_descriptor_readback.py --input results/readback-REPRO-NEW
Les snapshots exécutés, commandes, source originale et SHA sont dans les cohortes.
Le paquet est incrémental: il requiert le workspace/toolchain épinglé existant,
et n'est pas un pilote à installer. Aucun gain de débit annoncé.

Références du format:
Envytools f102b82381f3f11cee113d16374c87091db039d9, gk104_compute.xml,
gk104_p2mf.xml et demmt/pushbuf.c.
Mesa26.2.4,96cb43121031992b85767f9c1be8f3f48e22b1d2,nve4_compute.c.
https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/rnndb/graph/gk104_compute.xml

Provenance: macOS26.7.1/25G241; clang17.0.0(1700.6.4.2), SDK26.2.
GeForceMTLDriver16.0.12 SHA2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
GTX880M registry4294968458;83fichiers système et rootpatch plist inchangés.
Tous les nouveaux enfants signés sont terminalement vérifiés. Pas de jobs Qwen.
'''
(OUT/'RAPPORT.txt').write_text(report);(ROOT/'RESSOURCES_COMMANDES_NVIDIA.txt').write_text(report);(OUT/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
coverage=ROOT/'results/hardware-coverage.json';cov=read(coverage)
new_titles=['Native indirect QMD/constant-state GPU writes','Native queue backing and retained-reference lifetimes']
# Maintain the existing canonical coverage schema, including previous entries.
if 'entries' in cov:
 cov['entries']=[r for r in cov['entries'] if r.get('feature') not in new_titles]
 if not cov['entries']:del cov['entries']
for title,status,proof,scope in [('Native indirect QMD/constant-state GPU writes','qualified_native_existing',ROOT/'results/indirect-descriptor-gpu-readback/independent-verification.json','6GPU configurations,18iterations;24QMD words and108native builtin-state words changed exactly;17736positiveuint32 correct, negative producer controls preserved.'),('Native queue backing and retained-reference lifetimes','qualified_bounded',ROOT/'results/native-command-ownership/independent-verification.json','Three uncommitted typed contexts mapped to five queue backing buffers; three retained/three unretained lifetime controls, no released-memory traversal.')]:
 if not any(r.get('category')==title for r in cov['coverage']):
  cov['coverage'].append({'category':title,'status':status,'tested_scope':scope,'remaining_requirements':'Persistent representation, complete resource residency/reuse and ICB CPU/GPU contracts; shared-resource/cache/destruction behavior and transparent integration remain unqualified.','evidence':[str(proof.relative_to(ROOT))]})
cov['complete']=False;dump(coverage,cov)
files=[ROOT/'RESSOURCES_COMMANDES_NVIDIA.txt',OUT/'RAPPORT.txt',OUT/'summary.json',OUT/'provenance.json',coverage]
dump(OUT/'delivery.json',{'files':[{'path':str(p),'SHA256':sha(p),'bytes':p.stat().st_size} for p in files],'global_complete':False,'system_files_unchanged':83})
print(json.dumps({'GPU_cases':6,'iterations':18,'consumer_invocations':4917,'CAS_operations':1782,'system_files_unchanged':83,'global_complete':False},indent=2))

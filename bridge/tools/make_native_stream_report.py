#!/usr/bin/env python3
"""Reconcile native metadata normalization and read-only packet observations."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/native-stream-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
count=read(ROOT/'results/native-metadata-count-normalized/independent-verification.json');assert count['status']=='PASS' and count['correct_CAS_operations']==1782
metadata=read(ROOT/'results/driver-runtime-layout/instruction-count-verification.json');assert metadata['performance_symbol']=='_MTLPipelinePerformanceKeyInstructionCount'
capture=read(ROOT/'results/native-command-capture/capture.json');launch=read(ROOT/'results/native-command-capture/launches.json');relocations=read(ROOT/'results/native-command-relocation-capture/independent-verification.json')
assert relocations['status']=='PASS' and not capture['committed'] and not capture['GPU_dispatch']
baseline=read(LAB/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json');system=[]
for row in baseline['system_files']:
 actual=sha(Path(row['path']));assert actual==row['sha256'];system.append({'path':row['path'],'sha256':actual})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert sha(rootpatch)==baseline['rootpatch_sha256'] and len(system)==83
inputs=[];children=[]
for cohort in ['driver-runtime-layout','native-command-capture','native-command-relocation-capture','native-metadata-count-normalized']:
 for p in (ROOT/'results'/cohort).rglob('*.json'):
  inputs.append({'path':str(p),'sha256':sha(p)});obj=read(p)
  if isinstance(obj,dict) and 'signed_executable' in obj:
   assert not obj['SIGKILL_requested'] and not obj['authoritative_ps_status'];state=subprocess.run(['ps','-o','stat=,command=','-p',str(obj['pid'])],capture_output=True,text=True).stdout.strip();assert obj['signed_executable'] not in state;children.append({'PID':obj['pid'],'terminal':True,'exit_code':obj['exit_code']})
head=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=ROOT,capture_output=True,text=True)
provenance={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Git':{'repository':str(LAB.parent),'branch':subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip(),'commit':head.stdout.strip() if head.returncode==0 else None,'local_changes':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)},
 'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),
 'system_files':system,'system_files_unchanged':83,'rootpatch_sha256':sha(rootpatch),'inputs':inputs,'children':children,'Qwen_job_ids':[],
 'envytools_commit':'f102b82381f3f11cee113d16374c87091db039d9','system_modified':False,'scope':'Native GPU count-field qualification plus uncommitted own-process packet snapshots. No stream replay, kernel patch or system framework modification.'}
dump(OUT/'provenance.json',provenance)
summary={'metadata_count':{k:v for k,v in count.items() if k!='results'},'metadata_static':metadata,
 'packet_capture':{'direct_bytes':464,'direct_packets':9,'indirect_bytes':1052,'indirect_packets':21,'repetitions':3,'GPU_dispatch':False,
                  'direct_launches':1,'indirect_launches':2,'helper_GPR':14,'user_GPR':7,'helper_grid':[1,1,1],'user_placeholder_grid':[0,0,0]},
 'offset_relocation':{k:v for k,v in relocations.items() if k!='records'},'all_hardware_functions_supported':False,'ICB_implemented':False,'system_modified':False,'Qwen_job_ids':[]}
dump(OUT/'summary.json',summary)
report='''KEPLERMETAL — MÉTADONNÉES ET FLUX NVIDIA NATIF, 13 octobre 2026

Objectif: toutes les fonctionnalités matérielles de GTX880M sur macOS.
Le tour précédent constitue PROGRESS. Objectif complet toujours ACTIVE,
non atteint; aucune intégration système, aucune famille Metal supplémentaire.
Travail solo; Git main sans commit, sources/instantanés hashés, job_ids Qwen aucun.

A — Champ de métadonnées instruction count localisé et recalculé

Le constructeur NVMTLFunctionVariant::initWithCompilerOutput:size:device:
est à0x10aa03 dans GeForceMTLDriver. La vtable compute0x1c20e8 mène au loader
0x177f50. Celui-ci cherche la section0x10004; à0x177fdf/0x177fe2, son payload
word0 est copié à FunctionVariant+44. À0x109289, cette valeur alimente NSNumber;
la référence0x109293 est _MTLPipelinePerformanceKeyInstructionCount.
Les captures originales à quatre noms donnent103/111/103/103, concordant avec
code_bytes/8-1. Ce n’est plus une simple corrélation sans consommateur identifié.
Tous les usages éventuels hors statistiques n’ont pas été inventoriés.

Nouvelle copie expérimentale du correcteur: GPR natifs7/8, launch736/544, LDS
et tous les autres octets metadata préservés. Seul le premier word est recalculé
selon la convention qualifiée code_words-1:103→111 ou111→119, puisque64octets
de code sont ajoutés. Une convention d’entrée différente est refusée.
Le décodeur du pilote rapporte les nouveaux comptes à+44, contrôlés avant dispatch.
Cette version remplace l’approche «tout préserver» pour ce champ lié au code.
Anciennes versions conservées dans leurs dossiers/archives, pas écrasées.

Six configurations GPU (trois formes, equal/miss, local33, trois groupes,
trois graines),18captures,1782CAS et7128mots uint32 corrects,2304octets de garde
intacts. Statique, metadata et oracle brut concordent. Aucun benchmark de débit,
aucune prise en charge CAS générale/transparent app/L3. Compilateur installé
inchangé; erreurs Invalid Resource distinctes encore non résolues.

B — Command stream émis par le vrai pilote, sans submission/rejeu

Layout runtime de notre NVMTLComputeCommandEncoder_KEPLER_COMPUTE_A: instance
128octets, m_compute à+120. Son header typé contient PushBuffer à+32.
Le snapshot sécurisé mach_vm_read de ce PushBuffer donne cursor à+0 et end à+136,
concordant avec l’assembleur du dispatch natif. Aucune écriture privée faite.
Les appels sont les APIs publiques de dispatch; command buffers non commités.

Captures répétées: direct464octets/9paquets, indirect1052octets/21paquets;
trois répétitions identiques par mode dans ce contexte. La forme des paquets
est décodée selon Envytools GF100+; tous les mots et limites sont consommés.
Sur subchannel1, les méthodes upload0x180/0x184/0x188/0x18c/0x1b0/0x1b4
décrivent la taille et l’adresse GPU des données inline. Les méthodes0x2b4 et
0x2bc sélectionnent le descripteur de lancement et lancent le programme.
Ce sont des interprétations fondées sur les définitions GK104 épinglées,
pas une preuve de conformité complète du contexte/firmware du pilote Apple.

Le direct upload un état128B, puis un descripteur256B: programme offset1fe000,
grid3/1/1, block32/1/1,7GPR, un lancement. L’indirect prépare deux descripteurs:
helper offset1fd000, grid1/1/1, block1/1/1,14GPR; utilisateur1fe000, grid0/0/0
en placeholder, block32/1/1,7GPR. La séquence lance d’abord helper puis utilisateur.
Un payload96B porte l’adresse GPU du buffer d’arguments+64, retrouvée exactement
à l’offset476 du stream. Des CB et allocations internes distinctes sont référencés.
Les anciennes exécutions indirectes surGPU ont déjà vérifié les dimensions finales.
L’interprétation «helper interne prépare les dimensions/descripteur» est une
inférence appuyée par la séquence et ces résultats; les écritures intermédiaires
du helper et son SASS résidant n’ont pas été relus dans cette capture CPU.

Contre-vérification des dépendances: offset de buffer64→128, local32→33 et
groupes directs3→5 changent les mots attendus et le pointer d’arguments à476.
Restauration des valeurs initiales: stream exactement identique aux octets près.
Six nouvelles captures, parsing/geometry/pointers/restauration PASS, sans GPU.
Un template fixe ne peut donc ignorer ces bindings; allocations internes,
résidence/ownership/lifetime et adresse des CB/descripteurs doivent être traitées.
Le contexte a une représentation native stable sur ces captures, mais aucun
template n’a été copié dans le pilote, injecté, soumis ou rejoué.
Un vrai ICB CPU/GPU reste non implémenté; on ne retourne pas un objet vide.

Références de format, commit f102b82381f3f11cee113d16374c87091db039d9:
https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/demmt/pushbuf.c
https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/rnndb/graph/gk104_compute.xml
https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/rnndb/graph/gk104_p2mf.xml

Provenance système: macOS26.7.1/25G241, clang17.0.0 clang-1700.6.4.2,
SDK26.2, GeForceMTLDriver16.0.12, SHA
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
Les83empreintes système et le plist rootpatch OCLP sont inchangés.
Les nouveaux processus signés sont tous terminalement vérifiés.

Commandes reproductibles, dans le bridge et dossiers frais:
python3 tools/reproduce_native_metadata_count.py --out results/metadata-repro-NEW
python3 tools/verify_native_metadata_count.py --input results/metadata-repro-NEW
python3 tools/decode_native_commands.py --input results/native-command-capture
python3 tools/analyze_native_launches.py --input results/native-command-capture
python3 tools/verify_native_command_relocations.py --input results/native-command-relocation-capture
Le build et le lancement des deux probes runtime/capture sont archivés dans
commands.json avec les snapshots exacts; aucun driver à installer.

PASS: mapping instruction-count natif et normalization GPU, code/metadata/guards,
capturing/framing/QMD/pointers et restauration,83empreintes.
BLOCKED actuel: objets/exécution/compiler ICB absents de la pile en place.
NOT RUN: replay natif, ressources/CB persistants adaptés à ICB, lecture helperGPU,
intégration transparente L2/L3, conformité globale et gains de performance.
Prochaine action: relier les allocations de CB et QMD aux propriétaires et
identifier leur rétention/réallocation. Construire ensuite une représentation
native réutilisable, avant un client ICB et avant toute intégration système.
Branche Linux reste distincte; aucun port appliqué. Objectif global non réduit.
'''
(ROOT/'METADATA_COMMAND_STREAM.txt').write_text(report);(OUT/'RAPPORT.txt').write_text(report);(OUT/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
coverage_path=ROOT/'results/hardware-coverage.json';coverage=read(coverage_path)
updates=[{'category':'Native repair instruction-count metadata','status':'sample_qualified_application_local','tested_scope':'Metadata.word0 copied to FunctionVariant+44 and reported as pipeline instruction count; convention code_words-1 normalized after adding64B. Six GPU configs,18captures,1782CAS correct, nativeGPR/launch/remaining metadata retained.',
 'remaining_requirements':'Full metadata use audit and other shader/stage conventions, wider ABI/semantic/correctness qualification and supported L2/L3 integration.',
 'evidence':['results/driver-runtime-layout/instruction-count-verification.json','results/native-metadata-count-normalized/independent-verification.json']},
 {'category':'Read-only native command stream templates','status':'observed_not_replayed','tested_scope':'Own uncommitted encoder128B/m_compute+120/PushBuffer+32, bounded cursor/end snapshots. Direct464B/9packets vs indirect1052B/21packets with two launch descriptors;6offset/geometry changes/restoration snapshots verified.',
 'remaining_requirements':'Native ownership/residency/lifetime and relocation of CB/QMD/resources, actual safe replay and ICB object/encoding/execution/GPU compiler contracts.',
 'evidence':['results/native-command-capture/decoded-packets.json','results/native-command-capture/launches.json','results/native-command-relocation-capture/independent-verification.json']}]
names={r['category'] for r in updates};coverage['coverage']=[r for r in coverage['coverage'] if r['category'] not in names]+updates;coverage['complete']=False;dump(coverage_path,coverage)
dump(OUT/'delivery.json',{'files':[{'path':str(p),'SHA256':sha(p),'bytes':p.stat().st_size} for p in [OUT/'RAPPORT.txt',ROOT/'METADATA_COMMAND_STREAM.txt',OUT/'summary.json',OUT/'provenance.json',coverage_path]],'global_complete':False,'system_files_unchanged':83})
print(json.dumps({'report':str(ROOT/'METADATA_COMMAND_STREAM.txt'),'CAS_operations':1782,'native_streams_captured_not_replayed':12,'system_files_unchanged':83,'global_complete':False},indent=2))

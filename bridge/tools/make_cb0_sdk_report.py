#!/usr/bin/env python3
"""Attest exact SDK archive, isolated public clients and their raw GPU results."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/combined-cb0-sdk-progress';OUT.mkdir(exist_ok=True)
EXTRACT=ROOT/'results/combined-cb0-sdk-extracted-client-20261014-03';SDK=EXTRACT/'KeplerMetalSDK'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_verifier(name):
 p=SDK/'examples'/name;spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module.verify
delivery=json.loads((ROOT/'results/combined-cb0-sdk-build-20261014-03/delivery.json').read_text());archive=Path(delivery['path']);assert sha(archive)==delivery['SHA256']
build=json.loads((SDK/'BUILD_MANIFEST.json').read_text());assert sha(SDK/'lib/libKeplerMetal.a')==build['static_library_SHA256']==delivery['static_library_SHA256']
assert not (SDK/'src').exists()
for n,h in build['source_SHA256'].items():assert sha(ROOT/'src'/n)==sha(EXTRACT/'audit-source-not-in-client-SDK'/n)==h
with tarfile.open(archive) as t:
 manifest=json.loads(t.extractfile('KeplerMetalSDK/FILE_MANIFEST.json').read())
 for e in manifest['files']:
  raw=t.extractfile('KeplerMetalSDK/'+e['path']).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
groups={'literal':['combined-cb0-sdk-literal-prepared-20261014-03','combined-cb0-sdk-literal-gpu-20261014-03','combined-cb0-sdk-literal-native-20261014-03'],
 'cas':['combined-cb0-sdk-cas-prepared-20261014-03','combined-cb0-sdk-cas-gpu-20261014-03','combined-cb0-sdk-cas-native-20261014-03']}
verified={};processes={}
for kind,names in groups.items():
 verifier=load_verifier('verify_literal_client.py' if kind=='literal' else 'verify_example.py')
 for name in names:
  folder=ROOT/'results'/name;v=verifier(folder);assert v['status']=='PASS';verified[name]=v
  m=json.loads((folder/'execution/manifest.json').read_text());assert m['GPU_reservation']['state']=='terminal' and not m['SIGKILL_requested'] and m['reservation_module_SHA256']==sha(ROOT/'tools/lab_gpu_reservation.py')
  current=subprocess.run(['ps','-o','pid=,lstart=,command=','-p',str(m['pid'])],capture_output=True,text=True).stdout.strip();assert not current
  assert json.loads((folder/'inputs.json').read_text())['static_library_SHA256']==delivery['static_library_SHA256']
  processes[name]={'PID':m['pid'],'exit_code':m['exit_code'],'SIGKILL_requested':False,'actual_ps_status':current,'manifest_SHA256':sha(folder/'execution/manifest.json')}
for app in ['literal-application','cas-application']:
 d=json.loads((EXTRACT/app/'inputs.json').read_text());assert d['core_source_compilations']==0
 argv=json.loads((EXTRACT/app/'commands.json').read_text())[0]['argv'];assert '-lKeplerMetal' in argv and '-Wl,-ObjC' in argv and not any('/src/' in p for p in argv)
assert 'mach_vm_' not in (SDK/'examples/literal_client.mm').read_text()
gpu=ROOT/'results/combined-cb0-sdk-literal-gpu-20261014-03';native=ROOT/'results/combined-cb0-sdk-literal-native-20261014-03';count=0
for r in json.loads((gpu/'results.json').read_text())['runs']:
 for file in r['outputs']+[r['counter_file'],r['input_file']]:assert (gpu/'outputs'/file).read_bytes()==(native/'outputs'/file).read_bytes();count+=1
assert count==42
old=json.loads((ROOT/'results/literal-bank-progress/system-check.json').read_text())
for row in old['system_files']:assert sha(row['path'])==row['sha256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==old['rootpatch_SHA256']
system={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_files':old['system_files'],'system_files_unchanged':83,'rootpatch_unchanged':True,'rootpatch_SHA256':old['rootpatch_SHA256'],'macOS':subprocess.check_output(['sw_vers'],text=True)}
lut=verified['combined-cb0-sdk-literal-gpu-20261014-03'];cas=verified['combined-cb0-sdk-cas-gpu-20261014-03'];control=verified['combined-cb0-sdk-cas-native-20261014-03']
summary={k:v for k,v in lut.items() if k!='raw_SHA256'};summary.update(at=system['observed_at'],goal_turn='PROGRESS',goal_complete=False,archive_SHA256=delivery['SHA256'],static_library_SHA256=delivery['static_library_SHA256'],native_ICB_byte_identical_files=42,CAS_correct_operations=cas['correct_CAS_operations'],CAS_repaired_operations=25088,CAS_native_valid_control_operations=4352,CAS_exact_uint32_words=cas['exact_uint32_words'],CAS_native_uncorrected_wrong_words=control['expected_native_wrong_words'],positive_processes_terminal=6,system_files_unchanged=83,rootpatch_unchanged=True,Git_branch='main',Git_commit=None,Qwen_job_ids=[])
assert summary['CAS_native_uncorrected_wrong_words']==25066 and summary['exact_uint32_words']==525916 and summary['GPU_invocations_counted']==131479
receipt={'summary':summary,'SDK_delivery':delivery,'SDK_build':build,'extraction':json.loads((EXTRACT/'extraction-verification.json').read_text()),'processes':processes,'client_build_commands':{n:json.loads((EXTRACT/n/'commands.json').read_text()) for n in ['literal-application','cas-application']},'client_inputs':{n:json.loads((EXTRACT/n/'inputs.json').read_text()) for n in ['literal-application','cas-application']},'runtime_manifests':{n:json.loads((ROOT/'results'/n/'execution/manifest.json').read_text()) for names in groups.values() for n in names},'creation_pending_flag':'Frozen qualification.json records creation-time pending=true. This external receipt qualifies the same archive bytes on GPU.','first_deliveries':'Build01 documentation incomplete; build02 literal client API type error; neither executed on GPU. Both immutable archives and error log preserved.'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'qualification-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(OUT/'verification-history.json').write_text(json.dumps(verified,indent=2)+'\n');(OUT/'system-check.json').write_text(json.dumps(system,indent=2)+'\n')
note=' Combined SDK now includes current CB0 256/512/1024B transport and shared cooperative reservation. Extracted40-file static package checked, ten implementation sources moved out before two independent public-client builds. Literal adapted client uses new counts65/4113/16321,locals64/256/128/512 then1024, offsets128/256/1024,caller library/manifest wiped.7CB/ 23 records:525916uint32 exact,131479GPUatomic-counted invocations,42raw captures byte-identical to ordinary unswizzled Metal reference;slot reset/copy/empty/precommit restoration qualified. Same delivered library CASclient:25088repaired+4352valid native control operations,117 760 uint32 exact;nativeuncorrected25066wrongwords.6processes exit0withoutSIGKILL/terminal,83system/rootpatch unchanged. Zero core source compilation by clients. L2explicit adaptation,bounded profiles,not all functions or ordinary-app transparent integration;no performance claim.'
for p in [ROOT/'results/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']:
 d=json.loads(p.read_text());assert len(d['coverage'])==30 and not d['complete']
 for row in d['coverage']:
  if row['category'] in ['CPU-recorded compute ICB selectors and bounded resource lifetime','Compiled-library native CAS repair with original metadata']:
   if note not in row['tested_scope']:row['tested_scope']+=note
   for ref in ['SDK_CB0_APPLICATION_ADAPTEE.txt','results/combined-cb0-sdk-progress/qualification-receipt.json']:
    if ref not in row['evidence']:row['evidence'].append(ref)
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
report=f'''KEPLERMETAL — SDK COMBINÉ CB0, APPLICATION ADAPTÉE
14 octobre 2026

La nouvelle bibliothèque statique contient la correction CAS native, les
transports calcul/rendu et les profils CB0 de 256 / 512 / 1024 octets. Deux applications
utilisant le header public sont compilées depuis son archive après retrait des
dix sources d'implémentation. Aucun fichier du cœur n'est recompilé par les clients.
Le lien conserve -Wl,-ObjC pour les classes optionnelles. Niveau L2 pour ces cas.

CLIENT CB0 ET RÉFÉRENCE INDÉPENDANTE
Quatre tables 16 / 64 / 128 / 256 uint32, indices dynamiques, rotations et arithmétique.
Nouveaux comptes 65 / 4 113 / 16 321, groupes locaux 64 / 256 / 128 / 512 puis 1024 ; offsets de sortie 128,
entrée 256, paramètres 1024, compteur 128. Données appelantes effacées après chargement.
Reset d'un slot, copie/reset, plage vide, réemploi et fermeture avant commit testés.
7 command buffers / 23 records :525 916 mots uint32 exacts,131 479 invocations GPU comptées,
5 909 264 octets de garde. 42 captures identiques à une référence qui utilise uniquement
Metal natif, sans installer le scope ni les objets ICB expérimentaux.
La préparation conserve NOP/blits auxiliaires mais ne soumet aucun CB utilisateur.

NON-RÉGRESSION CAS DANS LE MÊME SDK
25 088 opérations CAS réparées +4 352 opérations témoins natives correctes ;
29 440 opérations /117 760 uint32 exacts. Contrôle natif non corrigé :25 066 mots erronés
attendus, conformément à l'oracle. Six CB/ 23 records ; gardes et restauration PASS.
Les 6 processus de préparation/GPU/référence terminent exit 0 sans SIGKILL, vérifiés par ps.
Les deux lanceurs SDK partagent la même réservation que le laboratoire via
--reservation-root. Ils n'excluent pas WindowServer ni les applications non coopérantes.

ARCHIVE EXACTE ET QUALIFICATION
{archive.name}
Archive SHA256 :{delivery['SHA256']}
Bibliothèque SHA256 :{delivery['static_library_SHA256']}
40 fichiers livrés vérifiés ; clang 17 / SDK 26.2, hôte x86_64.
Le drapeau pending du paquet conserve son état de création. Le reçu externe
results/combined-cb0-sdk-progress/qualification-receipt.json atteste les mêmes bytes
après exécution GPU réelle. Archives01/02 non utilisées sur GPU conservées ;02 a
révélé une erreur NSData/dispatch_data_t dans le client, corrigée avec l'API URL.
Le contrôle système après essais constate 83 fichiers et rootpatch OCLP inchangés.
Aucun pilote, framework, kext, firmware ou réglage matériel modifié.

REPRODUCTION — EXTRAIRE LE TAR DANS UN DOSSIER NEUF
Depuis KeplerMetalSDK, avec /chemin/bridge la racine de réservation commune :
python3 examples/build_literal_client.py --out /chemin/neuf/client
python3 examples/run_literal_client.py --build /chemin/neuf/client --out /chemin/neuf/prep --reservation-root /chemin/bridge --mode prepare
python3 examples/verify_literal_client.py /chemin/neuf/prep
python3 examples/run_literal_client.py --build /chemin/neuf/client --out /chemin/neuf/gpu --reservation-root /chemin/bridge --mode execute
python3 examples/verify_literal_client.py /chemin/neuf/gpu
Le mode native requiert un autre dossier. Valider la préparation avant execute.
Le client CAS utilise build_example.py/run_example.py/verify_example.py avec le
même --reservation-root. Le reçu conserve les argv exacts et empreintes.

TRANSMISSION
Objectif global : fonctions matérielles réalisables de la GTX 880M sous macOS.
Git main sans commit ; sources locales non suivies ; références par archives/SHA.
Actions : intégration SDK, extraction isolée, builds clients, préparations,
GPU/références/oracles et rehash système. Qwen job_ids=[] / solo.
PASS : 6 oracles, clients publics liés au SDK sans sources, compteurs/guards/références.
FAIL conservé : compilation du client du paquet 02, aucun GPU exécuté par cet essai.
BLOCKED : aucun nouveau blocage ; limites vidéo et autres catégories restent ouvertes.
NOT RUN : SDK général tous programmes, autres CB0, concurrence et pression mémoire, benchmark,
Metal 3/4 complet, intégration transparente, port Linux et fonctions restantes.
Le pilote natif pouvait déjà exécuter les LUT ; l'extension rend ce chemin utilisable
par les objets ICB du SDK. Aucun gain général ni prise en charge complète annoncés.
Couverture : 30 catégories, complete=false ; objectif global actif. Suite : opérations FP64
manquantes et fonctions matérielles non couvertes, puis qualification élargie.
'''
(ROOT/'SDK_CB0_APPLICATION_ADAPTEE.txt').write_text(report);print(json.dumps(summary,indent=2))

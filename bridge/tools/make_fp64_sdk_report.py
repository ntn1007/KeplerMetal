#!/usr/bin/env python3
"""Attest the frozen combined SDK through three independent public clients."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/combined-fp64-sdk-progress-20261014';assert OUT.is_dir() and not (OUT/'summary.json').exists()
EXTRACT=ROOT/'results/combined-fp64-sdk-extracted-client-20261014-02';SDK=EXTRACT/'KeplerMetalSDK'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def dump(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
delivery=read(ROOT/'results/combined-fp64-sdk-build-20261014-02/delivery.json');archive=Path(delivery['path']);assert sha(archive)==delivery['SHA256']
build=read(SDK/'BUILD_MANIFEST.json');assert sha(SDK/'lib/libKeplerMetal.a')==build['static_library_SHA256']==delivery['static_library_SHA256'];assert not (SDK/'src').exists()
for name,h in build['source_SHA256'].items():
 assert sha(EXTRACT/'audit-source-not-in-client-SDK'/name)==h
 if name!='KeplerFP64Programs.inc':assert sha(ROOT/'src'/name)==h
with tarfile.open(archive) as t:
 manifest=json.loads(t.extractfile('KeplerMetalSDK/FILE_MANIFEST.json').read())
 for e in manifest['files']:
  raw=t.extractfile('KeplerMetalSDK/'+e['path']).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
groups={'fp64':(['combined-fp64-sdk-small-prepared-20261014-02','combined-fp64-sdk-small-gpu-20261014-02','combined-fp64-sdk-prepared-20261014-02','combined-fp64-sdk-gpu-20261014-02','combined-fp64-sdk-no-producer-20261014-02'],'verify_fp64_client.py'),
        'cas':([f'combined-fp64-sdk-cas-{mode}-20261014-02' for mode in ['prepared','gpu','native']],'verify_example.py'),
        'literal':([f'combined-fp64-sdk-literal-{mode}-20261014-02' for mode in ['prepared','gpu','native']],'verify_literal_client.py')}
ps=subprocess.check_output(['ps','-axo','pid,ppid,lstart,command'],text=True);verified={};processes={}
for kind,(names,modulefile) in groups.items():
 spec=importlib.util.spec_from_file_location(kind,SDK/'examples'/modulefile);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for name in names:
  folder=ROOT/'results'/name;v=module.verify(folder);assert v['status'].startswith('PASS');verified[name]=v;m=read(folder/'execution/manifest.json')
  assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
  assert m['reservation_module_SHA256']==sha(ROOT/'tools/lab_gpu_reservation.py')
  assert not [line for line in ps.splitlines() if m['signed_executable'] in line]
  assert read(folder/'inputs.json')['static_library_SHA256']==delivery['static_library_SHA256']
  processes[name]={'PID':m['pid'],'exit_code':0,'SIGKILL_requested':False,'current_signed_path_matches':[],'manifest_SHA256':sha(folder/'execution/manifest.json')}
for app in ['fp64-application','cas-application','literal-application']:
 d=read(EXTRACT/app/'inputs.json');assert d['core_source_compilations']==0 and d['static_library_SHA256']==delivery['static_library_SHA256']
 argv=read(EXTRACT/app/'commands.json')[0]['argv'];assert '-lKeplerMetal' in argv and '-Wl,-ObjC' in argv and not any('/src/' in item for item in argv)
system=read(OUT/'system-check.json');assert len(system['system_files'])==83
for row in system['system_files']:assert sha(row['path'])==row['sha256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==system['rootpatch_SHA256']
fp=verified['combined-fp64-sdk-gpu-20261014-02'];negative=verified['combined-fp64-sdk-no-producer-20261014-02'];cas=verified['combined-fp64-sdk-cas-gpu-20261014-02'];lut=verified['combined-fp64-sdk-literal-gpu-20261014-02']
assert fp['exact_results_for_executed_programs']==1167291 and fp['GPU_invocations_with_correct_tags']==1167291 and fp['user_dispatches']==243
assert negative['negative_differences_from_full_chain']==172626 and cas['exact_uint32_words']==117760 and lut['exact_uint32_words']==525916
identical=0
gpu=ROOT/'results/combined-fp64-sdk-literal-gpu-20261014-02';native=ROOT/'results/combined-fp64-sdk-literal-native-20261014-02'
for r in read(gpu/'results.json')['runs']:
 for n in r['outputs']+[r['counter_file'],r['input_file']]:assert (gpu/'outputs'/n).read_bytes()==(native/'outputs'/n).read_bytes();identical+=1
assert identical==42
summary={k:x for k,x in fp.items() if k!='raw_SHA256'}
summary.update(goal_turn='PROGRESS',goal_complete=False,FP64_direct_results=951126,FP64_chained_results=216165,FP64_program_count=15,negative_control_differences=172626,CAS_correct_operations=cas['correct_CAS_operations'],CAS_repaired_operations=25088,CAS_valid_native_operations=4352,CAS_exact_uint32_words=117760,CAS_native_wrong_words=verified['combined-fp64-sdk-cas-native-20261014-02']['expected_native_wrong_words'],CB0_exact_uint32_words=525916,CB0_GPU_invocations_counted=131479,CB0_native_identical_files=42,terminal_processes=len(processes),system_files_unchanged=83,rootpatch_unchanged=True,SDK_archive_SHA256=delivery['SHA256'],static_library_SHA256=delivery['static_library_SHA256'],Git_branch='main',Git_commit=None,Qwen_job_ids=[])
assert summary['CAS_native_wrong_words']==25066
dump(OUT/'summary.json',summary);dump(OUT/'processes.json',processes);dump(OUT/'verification-history.json',verified)
receipt={'summary':summary,'delivery':delivery,'build':build,'extraction':read(EXTRACT/'extraction-verification.json'),'client_builds':{n:read(EXTRACT/n/'commands.json') for n in ['fp64-application','cas-application','literal-application']},'client_inputs':{n:read(EXTRACT/n/'inputs.json') for n in ['fp64-application','cas-application','literal-application']},'runtime_manifests':{n:read(ROOT/'results'/n/'execution/manifest.json') for n in processes},'scope':'Same frozen66-file SDK qualified by public clients after removing implementation sources. Creating/encoding is not GPU execution; markers, raw results and controls qualify execution separately.','creation_pending_flag':'The immutable tar retains creation-time pending=true; this external receipt attests its exact bytes.','prototype01':'Built and client-compiled only; not executed on GPU. Version02 adds tracking exclusions and current documentation, then is qualified here.'}
dump(OUT/'qualification-receipt.json',receipt)
note=(' Combined static SDK now includes FP64 via the existing NativeCAS importer/mutex and immutable in-memory carrier, '
      'with build-pinned15strided SM30 programs. Header-only client compiled without13implementation files: '
      'all22input stride8/16 combinations, counts65/2057/12289, local32/128/1024, nine trials. '
      '1167291 exact binary64 results with index/stamp, including216165 in dependent DIV/SQRT/FMA/ADD/MUL chain '
      'with Private intermediates and no CPU interstage readback. Caller program data wiped; library released '
      'before last commit; bad code and seven encoding cases refused. Missing producer:172626differences, '
      'all actually executed consumer results match the missing-input CPU reference. '
      'Same SDK regresses native CAS117760uint32 and CB0525916uint32/131479countedGPUinvocations, '
      '42files match ordinary native Metal.11processes terminal,83system/OCLP unchanged. '
      'L2explicit adaptation,not MSLdouble or transparent Metal support,no performance benchmark.')
for p in [ROOT/'results/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/hardware-coverage.json',ROOT.parent/'driver-research-2026-10-13/inventory/evidence-summaries/hardware-coverage.json']:
 d=read(p);assert len(d['coverage'])==30 and not d['complete'];row=next(r for r in d['coverage'] if r['category']=='FP64 hardware arithmetic')
 row['status']='sample_qualified_five_operations_L2'
 if note not in row['tested_scope']:row['tested_scope']+=note
 row['remaining_requirements']='Further IEEE cases and rounding modes/conversions, pressure/concurrency/performance; ordinary-app integration and MSL double frontend remain open. API count ceiling is not qualification of all lengths.'
 for e in ['SDK_FP64_APPLICATION_ADAPTEE_2026-10-14.txt','results/combined-fp64-sdk-progress-20261014/qualification-receipt.json']:
  if e not in row['evidence']:row['evidence'].append(e)
 dump(p,d)
report=f'''KEPLERMETAL — SDK COMBINÉ AVEC FP64, CLIENT INDÉPENDANT
14 octobre 2026 ; objectif global actif et incomplet

RÉSULTAT ET INTÉGRATION
Les cinq opérations FP64 sont maintenant utilisables par une application
adaptée via KeplerFP64.h / KPBinary64Library. Le même paquet conserve CAS
natif et CPU ICB calcul/rendu/CB0. Niveau L2 pour les scénarios testés.
Le client FP64 lie la bibliothèque statique extraite du tar, après retrait
des13fichiers d'implémentation. Il ne compile que son propre .mm et utilise
le header public. Aucun code du cœur n'est recompilé par les trois clients.

QUALIFICATION FP64 SUR LA GTX880M
15programmes SM30 contrôlés et décodés, locaux32/128/1024, GPR24 ;
pas de scratch, CRS ou shared pour ces cas. Codes au local32 :576BADD/MUL,
704BFMA,2432BDIV,1216BSQRT. Entrées pas8 ou16, sortie KPBinary64Record16B.
22combinaisons d'entrées couvrent chaque masque de pas valide des cinq
opérations ; neuf essais, tailles65/2057/12289, trois par taille/groupe.
9CBprincipaux/243dispatchs :1167291résultats et autant de marqueurs exacts.
951126résultats directs,216165dans DIV→SQRT→FMA→ADD→MUL. Les intermédiaires
Private sont consommés directement, sans CPU entre les étapes. Les valeurs
finies/zéros signés sont comparés bit à bit ; NaN silencieux requis, payload
et signe NaN non normalisés. Aucun assouplissement ULP. Oracle FMA rationnel.
Entrées reconstruites indépendamment à partir de la recette, pas seulement
acceptées parce que le host les déclare inchangées. Les records d'entrée16B
sont de simples copies des bits bruts8B, jamais des réponses calculées CPU.
1151640octets de garde vérifiés, entrées intactes. Le client efface les bytes
appelants après chargement et libère la bibliothèque avant le dernier commit.

CONTRÔLES ET LIMITES D'ATTRIBUTION
Préparation : aucun CBde kernels utilisateur commité ; sorties intactes.
Les blits préparatoires et imports existent, donc ce n'est pas CPU seule.
Empreinte de programme altérée refusée avant import de tout programme.
Sept encodages refusés : stride24, sortie désalignée, chevauchement, arité,
groupe64, sortie trop courte, dépassement de la borne count ; aucun commit.
Contrôle no_producer :DIVinitiale omise, sortie laissée0xc7 ; les quatre
consommateurs s'exécutent et leurs résultats correspondent exactement à la
référence CPU avec ce producteur absent.172626différences sont constatées
avec la chaîne complète, sur ces quatre étapes, gardes intactes.
L'import atteste les bytes transmis au constructeur et les métadonnées
décodées. Il ne lit pas les instructions résidentes. Marqueurs, résultats
et contre-épreuves constituent une preuve d'exécution distincte.

ARCHITECTURE ET NON-RÉGRESSION
L'import FP64 réutilise le mutex et le chemin du module NativeCAS existant,
avec une entrée interne recevant un carrier NSData copié. Aucun second moteur
de soumission ni nouvel importeur dupliqué. Les empreintes et métadonnées
autorisées sont générées à la compilation du SDK ; la factory n'accepte pas
des déclarations de code/ABI arbitraires du client. La méthode NVIDIA est
restaurée après chaque création. Buffers Shared/Private avec tracking ; pas
de Managed/memoryless/Untracked dans ce contrat. Commit/wait restent au client.
La borne count1048576ne signifie pas que chaque taille/pression est qualifiée.
Dans le même SDK, clientCAS :25088opérations réparées+4352témoins natifs,
117760uint32exacts ; natif non corrigé :25066mots incorrects attendus.
ClientCB0 :525916uint32exacts,131479invocations GPU comptées,42fichiers
identiques à une référence Metal native ordinaire, profils256/512/1024B.
11processus observés terminaux, exit0sans SIGKILL. Aucun pilote/framework/
kext/firmware/clock/OCLPmodifié :83fichiers système et plistrootpatch inchangés.

PAQUET ET VERSIONS
{archive.name}
Tar SHA256 :{delivery['SHA256']}
Bibliothèque SHA256 :{delivery['static_library_SHA256']}
66fichiers vérifiés par manifeste, extraction indépendante. Le drapeau
pending du tar conserve son état de création ; qualification-receipt.json
atteste ses mêmes bytes après essais GPU. Prototype01 jamais exécuté GPU.
macOS26.7.1/25G241, GTX880MGK104SM30, registry4294968458 ; clang17,
SDK26.2, x86_64. Mesa26.2.4/96cb43121031992b85767f9c1be8f3f48e22b1d2 ;
archives effectivement liées/code et sources SHA dans le buildoffline.
GeForceMTLDriver16.0.12/16.0.0 SHA :
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.

COMMANDES REPRODUCTIBLES — BRIDGE, DOSSIERS NEUFS
python3 tools/build_fp64_math.py --out results/NEW-FP64-OFFLINE --strided-inputs
python3 tools/build_combined_keplermetal_sdk.py --fp64-programs results/NEW-FP64-OFFLINE --out results/NEW-SDK
Extraire le tar dans un autre dossier ; depuis KeplerMetalSDK :
python3 examples/build_fp64_client.py --out /chemin/neuf/client
python3 examples/run_fp64_client.py --build /chemin/neuf/client --out /chemin/neuf/prep --reservation-root /chemin/bridge --mode prepare --trials9
python3 examples/verify_fp64_client.py /chemin/neuf/prep
python3 examples/run_fp64_client.py --build /chemin/neuf/client --out /chemin/neuf/gpu --reservation-root /chemin/bridge --mode execute --trials9
python3 examples/verify_fp64_client.py /chemin/neuf/gpu
Le contrôle no_producer utilise un autre dossier. --trials1permet le premier
essai discriminant ; une suite courte ne constitue pas la campagne complète.
Les lanceurs coopérants partagent reservation-root ; pas WindowServer.
Une observation ambiguë reste bloquée. Les commandes exactes des compilations
et les manifests de chaque processus sont dans les dossiers livrés.

TRANSMISSION ET SUITE
Gitmain sans premier commit ; sources locales non suivies, source/objet/lib/
programmes épinglés par SHA dans le paquet. job_ids=[] ; travail solo sur iMac.
Les deux MCP ont répondu lors de cette reprise, sans nouveau job ni transfert
central exact attesté. Les observations matérielles ne proviennent pas du MacBook.
PASS : FP64L2borné, contrôle producteur attendu, CAS/CB0non-régression,
gardes/données/propriétaires testés, restauration et système inchangé.
FAIL : aucun nouvel échec numérique ; anciens défauts FP64 restent archivés.
NOT RUN : benchmark, autres modes d'arrondi/conversions, concurrence/pression,
référenceM1, MSLdouble, intégration transparente et portage Linux/FreeBSD.
Objectif complet non atteint. Aucun support Metal3/4global ou gain revendiqué.
Prochaine action : conversions/arrondis FP64 et charge de réception mesurée,
puis intégration aux applications ordinaires ; chantier NVIDIA/Linux distinct.
'''
report=report.replace('--trials9','--trials 9').replace('--trials1','--trials 1')
(ROOT/'SDK_FP64_APPLICATION_ADAPTEE_2026-10-14.txt').write_text(report);(OUT/'RAPPORT.txt').write_text(report)
print(json.dumps({k:v for k,v in summary.items() if k!='raw_SHA256'},indent=2))

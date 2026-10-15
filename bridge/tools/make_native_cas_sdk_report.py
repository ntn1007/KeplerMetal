#!/usr/bin/env python3
"""Freeze an evidence-calibrated report for the native CAS application API."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/native-cas-sdk-progress';SDK=ROOT/'results/native-cas-sdk-build-20261014-02/KeplerNativeCAS'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('oracle',ROOT/'tools/verify_native_cas_sdk.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
history={};processes={}
for name in ['native-cas-sdk-negative-02','native-cas-sdk-prepared-02','native-cas-sdk-gpu-qualified-02','native-cas-sdk-native-control-02']:
 root=ROOT/'results'/name;history[name]=oracle.verify(root);m=read(root/'execution/manifest.json');s=subprocess.run(['ps','-o','stat=,command=','-p',str(m['pid'])],capture_output=True,text=True).stdout.strip();assert m['signed_executable'] not in s;processes[name]=m
gpu=history['native-cas-sdk-gpu-qualified-02'];native=history['native-cas-sdk-native-control-02'];assert gpu['correct_CAS_operations']==106650 and native['expected_native_defect_words']==85212
build=read(SDK/'BUILD_MANIFEST.json')
for rel,want in build['source_SHA256'].items():assert sha(ROOT/rel)==want
old=read(ROOT/'results/native-cas-sdk-client-20261014-02/inputs.json');extracted=read(ROOT/'results/native-cas-sdk-extracted-client-02/application/inputs.json');assert old==extracted and extracted['core_source_compilations']==0
assert not (ROOT/'results/native-cas-sdk-extracted-client-02/KeplerNativeCAS/src').exists()
profiles=[];manifest=read(SDK/'assets/client-manifest.json')
for p in manifest['profiles']:
 cert=read(SDK/'assets'/p['certificate']);assert sha(SDK/'assets'/p['certificate'])==p['certificate_SHA256']
 if p['candidate']:
  import base64
  code=base64.b64decode(cert['original_code_base64']);metadata=base64.b64decode(cert['native_metadata_base64']);s=cert['SASS']
  profiles.append({'function':p['function'],'old_register':s['old_register'],'expected_register':s['expected_register'],'redirect':s['redirect_offset'],'original_code_bytes':len(code),'repaired_code_bytes':len(code)+64,'native_GPR':struct.unpack_from('<I',metadata,28)[0],'shared_address':s['shared_address'],'certificate_SHA256':p['certificate_SHA256']})
summary={k:v for k,v in gpu.items() if k!='records'};summary.update({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'branch':'A — native NVIDIA shader correction','repaired_CAS_operations':85320,'valid_native_control_operations':21330,'native_defect_wrong_words':85212,'negative_refusals':8,'pre_constructor_refusals':6,'constructor_pin_refusals':2,'SDK':read(OUT/'SDK-delivery.json'),'Git_branch':'main','Git_commit':None,'ordinary_applications_transparent':False,'installed_compiler_modified':False,'NVIDIA_Linux_correction_ported':False,'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current exact Windows sources unverified','system_files_unchanged':83,'rootpatch_unchanged':True,'ICB_core_unchanged':True,'extracted_client_byte_identical_to_GPU_tested_client':True})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'qualification-receipt.json',{'summary':summary,'module_build':build,'client_inputs':old,'independently_extracted_client_inputs':extracted,'profiles':profiles,'processes':processes,'portable_verification_scope':'Raw CPU oracle and input fingerprints; omitted executables are not re-attested and no new GPU run is implied','metadata_only_reporting_corrections':['prepare verification originally displayed integration_level2; corrected to1 before GPU qualification, raw output unchanged','native control did not interpose a constructor; metadata/restore fields changed from false to not-applicable null, raw output unchanged'],'REA_Ghidra_analysis':'NOT RUN; existing AIR/SASS tools and own-process constructor observer used, no new decompilation of installed driver'})
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete']
addition=' Optional native CAS application API now qualified separately: immutable library/certificate NSData, indexed AIR name/range/HASH binding, original code and complete incoming metadata pinned, MOV/trampoline structure checked, native GPR/launch/shared preserved except normalized instruction count. Four client functions,33/128/1024threads,3groups,2variants,3seeds;85320 repairedCAS+21330 valid native-controlCAS,426600uint32 words exact;8refusals before dispatch. Native uncorrected candidates retain85212wrongwords. Caller library/certificate bytes wiped precommit. Independent extracted SDK client has no implementation sources and reproduces identical executable. Level2 only for this adapted client; general compiler/L3/otherInvalidResource/performance remain open.'
for row in coverage['coverage']:
 if row['category'] in ['Pinned native shared-CAS shader correction','Compiled-library native CAS repair with original metadata','Native repair instruction-count metadata']:
  if addition not in row['tested_scope']:row['tested_scope']+=addition
  row['adapted_client_integration']={'level':2,'scope':'Four approved local uint32 weak CAS shapes in explicitly adapted client','evidence':'bridge/results/native-cas-sdk-progress/qualification-receipt.json','full_category_qualified':False}
research=ROOT.parent/'driver-research-2026-10-13'
for p in [ROOT/'results/hardware-coverage.json',research/'inventory/hardware-coverage.json',research/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
rows='\n'.join(f"{p['function']}: r{p['old_register']}→r{p['expected_register']}, redirect {p['redirect']:#x}, {p['original_code_bytes']}→{p['repaired_code_bytes']}B, GPR{p['native_GPR']}, shared{p['shared_address']}" for p in profiles)
report=f'''KEPLERMETAL — CAS NATIVE ACCESSIBLE À UN CLIENT ADAPTÉ
14 octobre 2026 — branche A, résultat borné de niveau2

L'API KPCreateCertifiedNativeCASPipeline accepte NSData bibliothèque/certificat
avec SHA attendus. Elle préserve le programme NVIDIA hors trampoline, conserve
les GPR/launch/shared natifs et normalise uniquement metadata.word0 (code_words-1).
Elle vérifie l'entrée AIR indexée, son HASH, l'intention analysée hors ligne,
la structure du MOV ajouté, puis le code et les232octets de métadonnées réellement
reçus au constructeur. Celui-ci est interposé dans le processus pendant la
création seulement, puis restauré. La bibliothèque est chargée depuis une copie
immuable, sans chemin extérieur fourni à l'API. Les certificats sont des
diagnostics approuvés par le développeur, pas une signature d'une autorité.

QUALIFICATION NOUVELLE
Quatre fonctions client compilées avec MSL2.4 puis analysées AIR/SASS :
{rows}
33/128/1024threads par groupe, trois groupes, deux variantes et trois graines.
72 captures sur les fonctions réparées :85 320 CAS et341 280 mots uint32 corrects.
18captures sur le témoin natif volontairement non réparé :21 330 CAS correctes.
Total positif90CB,106 650 CAS,426 600 mots exacts,11 520octets de garde intacts.
Les octets bibliothèque/certificats appartenant à l'appelant sont effacés avant
tout commit. Les pipelines restent fonctionnels grâce aux copies conservées.

Comparaison avec le même client et mêmes paramètres en Metal natif :
90CB, le témoin21 330CAS reste correct ; les quatre candidats produisent
85 212 mots incorrects, uniquement le composant expected. Les valeurs finales,
indices et nombres de gagnants restent corrects. Ce sont des défauts numériques
attendus, pas une réussite de justesse native. Les sorties brutes sont conservées.
Un gagnant par groupe vérifie la boucle lock/unlock NVIDIA qualifiée, pas une
garantie générale de weak-CAS pour toutes les implémentations du langage.

Huit refus : bibliothèque/certificat altéré, intention non applicable, entrée
AIR renommée vers un autre kernel, composante discordante, NOP à la place du MOV,
programme original ou métadonnées arrivant au constructeur non concordants.
Six refus avant constructeur, deux au constructeur, tous avant dispatch.
Préparation90CB non committés : gardes intactes. PID42550/42589/42705/42837,
exit0, aucun SIGKILL, tous réellement terminaux. Les compteurs incluent les
captures de validation, aucun échauffement ni mesure de débit n'a été réalisé.

LIVRAISON ET PROVENANCE
Header public, lib statique x86_64, sources exactes, cinq certificats, metallib,
client et README. Tar19fichiers SHA{summary['SDK']['SHA256']}.
LibSHA{build['static_archive_SHA256']}.
ExécutableSHA{old['executable_SHA256']}.
Le client recompilé depuis le tar extrait, après retrait des sources
d'implémentation, est byte-identique au client GPU testé.0compilation du module.
Les certificats conservent leur drapeau pending de création ; ce reçu externe
atteste les quatre formes de ces mêmes octets. Ils ne qualifient pas tout shader.
Git main sans premier commit. SHA et commandes complètes dans BUILD_MANIFEST,
qualification-receipt et chaque dossier execution. GeForceMTLDriver16.0.12/16.0.0
SHA2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054 ;
macOS26.7.1/25G241,SDK26.2,clang17(1700.6.4.2),GTX880M registry4294968458.
83fichiers système/rootpatch OCLP et les six sources ICB rehashés inchangés.
La branche B et son SDK ICB existant ne sont pas remplacés par ce module.

REPRODUCTION DANS LE WORKSPACE (répertoires neufs)
SDK=results/native-cas-sdk-build-20261014-02/KeplerNativeCAS
python3 "$SDK/examples/build_example.py" --out results/CAS-client-NEW
python3 tools/run_native_cas_sdk.py --sdk "$SDK" --build results/CAS-client-NEW --out results/CAS-negative-NEW --mode negative
python3 tools/verify_native_cas_sdk.py results/CAS-negative-NEW
python3 tools/run_native_cas_sdk.py --sdk "$SDK" --build results/CAS-client-NEW --out results/CAS-prepare-NEW --mode prepare
python3 tools/verify_native_cas_sdk.py results/CAS-prepare-NEW
python3 tools/run_native_cas_sdk.py --sdk "$SDK" --build results/CAS-client-NEW --out results/CAS-GPU-NEW --mode execute
python3 tools/verify_native_cas_sdk.py results/CAS-GPU-NEW
Même commande --mode native pour la référence non corrigée, dans un autre dossier.
Le lanceur signe uniquement une copie de l'application et suit son PID réel.

LIMITES ET SUITE
Reconnaissance locale weak uint32/post-CAS uint4 dans les formes acceptées ;
pas de preuve générale CFG/alias/orders/types/progression. Aucun compilateur
installé réparé, aucun correctif Linux transposé, aucune intégration transparente
aux applications ordinaires. Les autres Invalid Resource restent distincts.
Pas de benchmark ni de réduction CPU déduite. REA/Ghidra NOT RUN ; les preuves
proviennent des outils AIR/SASS existants et d'observations de notre processus.
Qwenjob_ids=[] ; MCP accessibles/authentifiés, sources centrales exactes non
confirmées, contre-lecture NOT RUN. Travail solo conformément au repli autorisé.
La couverture30catégories reste complete=false ; objectif matériel global ouvert.
Prochaine action : étendre la reconnaissance conservatrice et relier ces
pipelines corrigés au contrat compute ICB, puis qualifier des clients plus larges.
'''
(ROOT/'CAS_API_APPLICATION_ADAPTEE.txt').write_text(report);print(json.dumps(summary,ensure_ascii=False,indent=2))

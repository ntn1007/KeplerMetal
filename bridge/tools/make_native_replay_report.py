#!/usr/bin/env python3
"""Reconcile real native packet replay without relabelling it as Metal ICB."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/native-replay-progress';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
cohorts=['native-replay-prepared','native-replay-gpu-l32-g1','native-replay-gpu-l33-g3','native-replay-gpu-l128-g5','native-replay-sequence-module-control','native-replay-mixed-prepared','native-replay-mixed-gpu']
verified={name:read(ROOT/'results'/name/'independent-verification.json') for name in cohorts};assert all(r['status']=='PASS' for r in verified.values())
single=[verified[x] for x in cohorts[1:4]];mixed=verified['native-replay-mixed-gpu'];control=verified['native-replay-sequence-module-control'];assert sum(x['replayed_consumer_invocations'] for x in single)==32382 and mixed['replayed_consumer_invocations']==9054
baseline=read(LAB/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json');system=[]
for r in baseline['system_files']:
 p=Path(r['path']);h=sha(p);assert h==r['sha256'];system.append({'path':str(p),'sha256':h})
assert len(system)==len({r['path'] for r in system})==83
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert sha(rootpatch)==baseline['rootpatch_sha256']
inputs=[];children=[]
for name in cohorts:
 directory=ROOT/'results'/name
 for p in directory.rglob('*.json'):
  inputs.append({'path':str(p),'sha256':sha(p)});o=read(p)
  if isinstance(o,dict) and 'signed_executable' in o:
   assert o['exit_code']==0 and not o['SIGKILL_requested'] and not o['authoritative_ps_status'];state=subprocess.run(['ps','-o','stat=,command=','-p',str(o['pid'])],capture_output=True,text=True).stdout.strip();assert o['signed_executable'] not in state;children.append({'pid':o['pid'],'terminal':True,'signed_executable':o['signed_executable']})
source_paths=[ROOT/'src/KeplerNativeCommands.h',ROOT/'src/KeplerNativeCommands.mm',ROOT/'tools/native_replay_probe.mm',ROOT/'tools/reproduce_native_replay.py',ROOT/'tools/verify_native_replay.py',ROOT/'tools/reproduce_mixed_native_replay.py',ROOT/'tools/verify_mixed_native_replay.py']
head=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=LAB.parent,capture_output=True,text=True)
provenance={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Git':{'repository':str(LAB.parent),'branch':subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=LAB.parent,text=True).strip(),'commit':head.stdout.strip() if head.returncode==0 else None,'local_changes':subprocess.check_output(['git','status','--short'],cwd=LAB.parent,text=True)},'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),'compiler':subprocess.check_output(['xcrun','clang','--version'],text=True).strip(),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'system_files':system,'system_files_unchanged':83,'rootpatch_sha256':sha(rootpatch),'source_files':[{'path':str(p),'sha256':sha(p)} for p in source_paths],'inputs':inputs,'children':children,'Qwen_job_ids':[],'system_modifications':False};dump(OUT/'provenance.json',provenance)
summary={'single_record':{'geometries':[[x['geometry'][0],x['geometry'][1]] for x in single],'positive_trials':sum(x['positive_replay_trials'] for x in single),'no_launch_controls':sum(x['launch_suppression_controls'] for x in single),'replayed_consumer_invocations':sum(x['replayed_consumer_invocations'] for x in single),'correct_uint32_words_including_references':sum(x['correct_uint32_words_including_reference'] for x in single)},'sequence_module_regression':{k:v for k,v in control.items() if k!='records'},'mixed_sequence':{k:v for k,v in mixed.items() if k!='sequences'},'new_module_SHA256':sha(ROOT/'src/KeplerNativeCommands.mm'),'source_library_SHA256':'b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d','system_files_unchanged':83,'all_hardware_functions_supported':False,'ICB_implemented':False,'integration_level':1,'system_modifications':False,'Qwen_job_ids':[]};dump(OUT/'summary.json',summary)
dump(OUT/'verification-history.json',{'initial_mixed_verifier_failure':'Independent verifier used offset180 (packet header) instead of184 (QMD payload), producing AssertionError. Corrected to derive payload offset from decoded packets; all raw captures subsequently verified without GPU rerun.','preparation_gate':'Native builder invariants and own-process uncommitted preparation passed before mixed GPU attempt. Initial independent mixed verifier failed; the shell continued to the GPU runner. This ordering was not a passing independent preflight; corrected verifier results are post-execution validation.','native_module_failure':False,'new_GPU_execution_for_verifier_repair':False})
report='''KEPLERMETAL — REJEU NATIF PERSISTANT, JALON EXPÉRIMENTAL
13 octobre 2026; objectif global ACTIVE, PROGRESS, non terminé.
Solo; Git main sans commit, instantanés/SHA256; aucun job Qwen.

Résultat concret

Nouveau module src/KeplerNativeCommands.h/.mm: KPRecordedNativeCompute.
Il conserve des paquets émis par le vrai pilote NVIDIA et des références fortes
à une file, un pipeline natif, les buffers applicatifs, les constantes et QMD.
Les backings constantes65536B et descripteur4096B sont dédiés à chaque record.
Ils restent vivants entre soumissions. Les bindings et dimensions d'un record
sont fixes; ses uniforms de graines peuvent changer entre exécutions.

Il ne fait pas une suite de dispatch API par commande rejouée: une préparation
native initialise le contexte et enregistre les ressources pour l'ensemble
du CB. Ses octets de dispatch sont remplacés avant commit. Les paquets retenus
sont ensuite recopiés dans le PushBuffer de NOTRE encoder, dans une région
validée writable et suffisamment grande; seul ce cursor/processus est modifié.
Le GPU exécute ces vrais paquets. L'émission reste une copie CPU de command words
vers le CB vivant: aucune indirection vers un ICB GPU-résident n'est démontrée.

Les constantes sont copiées par blit public depuis l'état natif qualifié;
les adresses upload/CB1/QMD/LAUNCH_DESC sont relocalisées. Les autres octets
des paquets restent exacts. CB2 pointe toujours vers le buffer d'uniforms retenu.
Pipeline/library/profil shader consume_grid natifs épinglés; aucun code NAK,
aucun nouveau shader GPU, aucun patch du compilateur ou du pilote installé.

Tests GPU et oracles

Mono-record: local32/groupes1,local33/groupes3,local128/groupes5; deux graines,
1/4/16copies et contrôle8copies sans LAUNCH par remplacement en PGRAPH NOP.
18essais positifs,6témoins NOP,32382invocations consumer exactement comptées.
21588uint32 corrects incluant les trois références natives; gardes intactes.
Préparation initiale supplémentaire non soumise et trois templates incohérents
(packet/binding/geometry) refusés. Compatibilité du module séquence réévaluée
surlocal33/groupes3:8essais,4158invocations positives; cohorte distincte.

Séquence mixte: trois records avec OUT/COUNT/PARAMS/CB/QMD distincts,
géométries32x1,33x3,128x5, une seule préparation native pour la séquence.
Deux graines par élément; répétition1 ou4, puis suppression du deuxième record
seulement, puis suppression des trois. Huit séquences soumises,24résultats
d'éléments (16positifs,8supprimés),9054invocations consumer comptées;
20796uint32 corrects incluant références, gardes intactes.
Neutraliser le deuxième record laisse ses sorties intactes tout en conservant
les sorties correctes des deux autres; suppression totale donne zéro invocation.
Cela vérifie l'absence d'un dispatch de préparation exécuté résiduellement.
File incompatible refusée avant emission/submission;8command buffers nouveaux.
Chaque état CB65536B reste exactement celui enregistré, et le QMD relocalisé
relu sur GPU concorde avec les paquets. Pas de remapping deviné du buffer.

Le programme library est exactement SHA256:
b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d.
Les hashes des modules/probes effectivement exécutés diffèrent selon la révision
et sont conservés dans inputs.json, sans écrasement d'une cohorte antérieure.

Erreur de vérification corrigée: le premier vérificateur mixte utilisait
180 (header) plutôt que184 (payload QMD), refusant des relocalisations valides.
Les offsets sont maintenant issus du parsing des paquets. Tous les bruts passent
la vérification corrigée, sans réexécuter les GPU pour cette réparation.
L'essai GPU mixte avait démarré malgré cet échec du vérificateur initial: sa
préparation native bornée avait passé, mais ce n'était pas un PASS indépendant
préalable. Cette chronologie est conservée dans verification-history.json.

Limites obligatoires

Prototype L1 appelé explicitement par notre application, un seul pipeline
consume_grid/profil exact. Pas d'identification sûre d'un pipeline arbitraire,
de multi-shaders, textures/samplers, render, changement de binding après record,
reset/copie/ranges d'ICB publics, ni commandes produites sur GPU.
Les ressources persistantes sont propres à notre processus/file; aucun rejeu
cross-queue, reprise après eviction, mémoire sous pression/concurrence longue
ou sérialisation d'adresses entre processus n'est qualifié.

Le contrat Metal MTLIndirectCommandBuffer n'est PAS implémenté. Les factories
absentes, compute/blit no-op, render refusé et air.command_buffer restent les
obstacles de la pile installée. Pas de capacité/famille GPU falsifiée.
Ce résultat fournit une primitive native pour poursuivre ce contrat, pas
une intégration transparente L2/L3 ni un pilote global modernisé.
Pas de benchmark: aucune baisse de CPU ou hausse de débit déduite du rejeu.
La branche A CAS et la recherche/transposition Linux restent séparées.
Vidéo, énergie, affichage, conformité générale et limites physiques restent
des chantiers du même objectif; ils ne sont pas retirés du périmètre.

Prochaine étape

Raccorder cette représentation aux contrats CPU ICB: objets réels, commande
compute, states hérités/locaux, mutation/reset/copie/ranges et ownership corrects,
avec client de test explicite. Étudier l'indirection de commandes GPU-résidentes,
puis génération GPU/compiler séparément. Qualifier d'autres pipelines/bindings
et leurs métadonnées avant d'étendre le profil, et mesurer CPU/coût de copies.
Ne pas déclarer l'API disponible tant que création ET exécution restent absentes.

Reproduction, depuis bridge, dossiers nouveaux, aucune installation système:
python3 tools/reproduce_native_replay.py --out results/replay-PREP-NEW
python3 tools/verify_native_replay.py --input results/replay-PREP-NEW
python3 tools/reproduce_native_replay.py --out results/replay-GPU-NEW --execute
python3 tools/verify_native_replay.py --input results/replay-GPU-NEW
python3 tools/reproduce_mixed_native_replay.py --out results/mixed-PREP-NEW
python3 tools/verify_mixed_native_replay.py --input results/mixed-PREP-NEW
Après PASS de cette préparation et vérification (pas de chaîne shell sans garde):
python3 tools/reproduce_mixed_native_replay.py --out results/mixed-GPU-NEW --execute
python3 tools/verify_mixed_native_replay.py --input results/mixed-GPU-NEW
Les vérificateurs bruts sont portables après extraction; le lancement GPU requiert
l'iMac, ses versions exactes et le workspace/toolchain épinglé.

Provenance: macOS26.7.1/25G241, clang17.0.0(1700.6.4.2),SDK26.2,
GTX880M registry4294968458,GeForceMTLDriver16.0.12 SHA
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054.
Envytools format f102b82381f3f11cee113d16374c87091db039d9,
demmt/pushbuf.c,rnndb/graph/gk104_compute.xml,rnndb/fifo/nv_object.xml.
PGRAPH0x100 NOP,0x110 SERIALIZE d'après les définitions épinglées.
https://github.com/envytools/envytools/blob/f102b82381f3f11cee113d16374c87091db039d9/rnndb/fifo/nv_object.xml
83empreintes système et le plist rootpatch OCLP inchangés après ces essais;
sept nouveaux enfants signés réellement terminés. Aucune modification système.
PASS: actual native packet relocation/reuse and mixed controls.
BLOCKED actuel: API ICB de la pile installée; vidéo non raccordée.
NOT RUN: ICB complet CPU/GPU, arbitrary pipelines, L2/L3, stress/performance.
'''
(ROOT/'REJEU_NATIF_PERSISTANT.txt').write_text(report);(OUT/'RAPPORT.txt').write_text(report);(OUT/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
coverage=ROOT/'results/hardware-coverage.json';cov=read(coverage);title='Persistent recorded native compute packets and mixed resources'
if not any(r['category']==title for r in cov['coverage']):cov['coverage'].append({'category':title,'status':'sample_qualified_application_local','tested_scope':'Dedicated CB/QMD per record, real native packet relocation/copy/reuse; three geometries and mixed independent bindings, one native preparation per sequence removed before commit; partial/full launch suppression, exact outputs and guards.','remaining_requirements':'Actual Metal ICB object/API/runtime, GPU-resident command indirection and GPU generation/compiler; other shaders/stages/resources, lifecycle/residency/stress and CPU/performance benchmarks; L2/L3 integration.','evidence':['src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','results/native-replay-mixed-gpu/independent-verification.json','results/native-replay-progress/summary.json']})
cov['complete']=False;dump(coverage,cov)
files=[ROOT/'REJEU_NATIF_PERSISTANT.txt',OUT/'RAPPORT.txt',OUT/'summary.json',OUT/'provenance.json',coverage];dump(OUT/'delivery.json',{'files':[{'path':str(p),'SHA256':sha(p),'bytes':p.stat().st_size} for p in files],'global_complete':False,'system_files_unchanged':83})
print(json.dumps({'single_replay_invocations':32382,'mixed_replay_invocations':9054,'new_signed_children_terminal':len(children),'system_files_unchanged':83,'ICB_implemented':False,'global_complete':False},indent=2))

#!/usr/bin/env python3
"""Record verified execution in signed copies without asserting a root cause."""
from pathlib import Path
import datetime,hashlib,json,struct,subprocess

root=Path(__file__).resolve().parents[1];folder=root/'results/native-execution-signed'
d=json.loads((folder/'gpu-correct.stdout').read_text());m=json.loads((folder/'gpu-correct-manifest.json').read_text())
assert m['exit_code']==0 and m['driver_unchanged'] and d['mismatches']==d['changed_guard_elements']==0
payload=(folder/'gpu-add-1041-correct/imported.compiler-output.bin').read_bytes();offset=d['events'][0]['code_payload_offset']
code=(root/'build/add_buffers-air-cb2.sass').read_bytes();assert payload[offset:offset+len(code)]==code
assert hashlib.sha256(code).hexdigest()==m['shader_sha256']
values=struct.unpack('<1088f',(folder/'gpu-add-1041-correct/output.f32').read_bytes())
assert all(values[i]==((i%127)-63)*.25+((i%31)-15)*.5 for i in range(1041))
assert all(v==-123456 for v in values[1041:])
video=json.loads((root/'results/video-signed-control/execution.stdout').read_text());vm=json.loads((root/'results/video-signed-control/manifest.json').read_text())
assert vm['exit_code']==0 and video['CPU_control_valid']
assert video['encode_hardware']['create_status']==video['encode_hardware_gpu']['create_status']==-12908 and video['decode_hardware']['create_status']==-12906
cp=json.loads((folder/'manifest.json').read_text());assert cp['exit_code']==0
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
assert hashlib.sha256(driver.read_bytes()).hexdigest()==m['driver_sha256']
# Preserve the exact carrier/ISA pair rather than a mutable build path.
for source,name in ((root/'build/kepler_carrier.metallib','qualified-carrier.metallib'),(root/'build/add_buffers-air-cb2.sass','qualified-code.sass')):
    target=folder/name
    if target.exists():assert target.read_bytes()==source.read_bytes()
    else:target.write_bytes(source.read_bytes())
states=[]
for pid in (20575,20903,21115):
    s=subprocess.run(['ps','-o','pid=,ppid=,stat=,etime=,command=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
    states.append({'pid':pid,'present':bool(s),'status':s,'SIGKILL_requested':True})
lifecycle=json.loads((root/'results/video-probe-lifecycle.json').read_text());lifecycle.update({'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'probes':states,'signed_CPU_execution_succeeded':True,'signed_NAK_compute_execution_succeeded':True,'global_native_execution_block_not_proved':True})
(root/'results/video-probe-lifecycle.json').write_text(json.dumps(lifecycle,indent=2)+'\n')
summary={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'signed_CPU_sum':40,'signed_CPU_passed':True,'GPU_compute_currently_usable':True,'NAK_values_checked':1041,'NAK_mismatches':0,'changed_guards':0,'guard_elements':47,'imported_code_identical':True,'NAK_code_sha256':hashlib.sha256(code).hexdigest(),'driver_sha256':m['driver_sha256'],'driver_unchanged':True,'signed_video_control_passed':True,'signed_video_hardware_available':False,'old_process_states':states,'hang_cause':'unproven','signature_is_cause':'unproven','performance_benchmark':False,'global_hardware_goal_complete':False}
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text());category='Native lab execution under current OS'
row={'category':category,'status':'partially_available','tested_scope':'Immutable ad hoc signed CPU executable returns40; signed copy of previously qualified NAK helper executes1041 additions exactly onGTX with47guards; signed VT control finishes but hardware H264 sessions fail-12908/-12906; previous unsigned GPU/CPU processes remainU','remaining_requirements':'Resolve previous uninterruptible processes and debugger authorization; signing/path relocation are not established as the cause; qualify further tool dependencies/lifecycle while preserving OS settings','evidence':['results/native-execution-summary.json','results/native-execution-signed/gpu-correct-manifest.json','results/video-signed-control/manifest.json','results/video-probe-lifecycle.json','tools/run_signed_probe.py']}
existing=next((i for i,r in enumerate(ledger['coverage']) if r['category']==category),None)
if existing is None:ledger['coverage'].append(row)
else:ledger['coverage'][existing]=row
ledger['complete']=False;ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n');summary['coverage_updates']=[row]
summary['GPU_execution_verified_at']=m['collected_at']
reproPath=root/'results/signed-add-reproduction/manifest.json'
if reproPath.exists():
    repro=json.loads(reproPath.read_text());data=json.loads((reproPath.parent/'execution.stdout').read_text())
    assert repro['exit_code']==0 and data['mismatches']==data['changed_guard_elements']==0 and data['import_contract_verified']
    summary['delivered_reproduction_command_verified']=True
    summary['reproduction_manifest']=str(reproPath.relative_to(root))
(root/'results/native-execution-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
vpath=root/'results/video-summary.json';v=json.loads(vpath.read_text());v['signed_control']={'manifest':'results/video-signed-control/manifest.json','result':'results/video-signed-control/execution.stdout','CPU_control_valid':True,'hardware_encode_status':-12908,'hardware_decode_status':-12906};v['later_probe_lifecycle']=lifecycle;vpath.write_text(json.dumps(v,indent=2)+'\n')
text=f'''KEPLERMETAL — exécution actuelle dans des copies signées

Le calcul GPU reste utilisable, malgré trois anciens processus en état noyauU.
Un programme CPU signé ad hoc calcule17+23=40 et termine avec0.
Une copie signée de la sonde NAK déjà validée exécute1041 additions a+b :
aucune différence CPU,47 gardes intactes. Le CPU vérifie aussi le fichier output.f32.
Le code SASS importé est identique octet par octet au programme compilé :
384B,24GPR, métadonnées de lancement576/576, stagecompute5.
Le shader natif porte23588 ; la sortie NAK commence à-23.25, comme le CPU.
La preuve repose sur le programme importé et la sortie numérique ; la détection
ou l’allocation de mémoire ne seraient pas des preuves suffisantes.
SHA256 SASS : {m['shader_sha256']}
SHA256 copie signée : {m['signed_binary_sha256']}
Carrier exact : kepler_carrier.metallib, SHA256 {m['carrier_sha256']}
Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2.
Le relevé gpu_seconds est conservé mais n’est pas qualifié pour un benchmark.
Aucune accélération de performance ni nouvelle famille Metal n’est annoncée.

L’essai initial a repris par erreur add_buffers.metallib, dont le contrat est
différent : toutes les sorties sont restées à la sentinelle, retour10.
Cet échec est conservé dans gpu-manifest.json et gpu-execution.stdout.
Le test corrigé reprend la commande du cas antérieur air-correct-1041.
Une création de pipeline et un statutCompleted n’ont pas été assimilés à du calcul.

La sonde VideoToolbox signée termine également : témoin CPU valide,691200 octets
NV12 auto/CPU identiques. Les modes H264 matériels restent refusés :
encodeur-12908, décodeur-12906. Les moteurs vidéo ne sont toujours pas qualifiés.

LIMITES DE LA REPRISE
Les PID20575/20903/21115 restent présents au dernier contrôle. SIGKILL a été
demandé ; leur sortie n’est pas affirmée. La cause est inconnue. Les nouveaux
tests ne réécrivent pas leurs fichiers exécutables et ne relancent pas ces jobs.
Developer mode est désactivé ; restrictions de debug SIP actives. Aucune
de ces protections n’a été modifiée. La requêteLLDB s’est bloquée dans task_for_pid.
spctl rejette le binaire non signé lors de son évaluation explicite, mais cela
ne prouve pas la cause des processusU : des outils non signés avaient fonctionné.
Le changement de signature et de chemin n’est pas une expérience causale complète.
La réussite actuelle est une voie de travail qualifiée pour ces échantillons.
Une signature ad hoc d’un fichier local ne lui attribue pas une confiance Apple.

COMMANDES ET ARTEFACTS
Depuis bridge, reproduction de l’addition dans une nouvelle copie :
python3 tools/run_signed_probe.py --exe results/native-execution-signed/gpu-add-probe --out results/signed-add-reproduction --timeout 15 -- results/native-execution-signed/qualified-carrier.metallib results/native-execution-signed/qualified-code.sass results/signed-add-output stack_execute 1041
Commande originale exacte : results/native-execution-signed/gpu-correct-manifest.json.
Le lanceur copie le programme dans un dossier neuf, signe seulement cette copie,
journalise le PID, refuse de dupliquer un job signé encore présent, et ne
confond jamais une demandeSIGKILL avec un processus effectivement terminé.
Les dépendances relatives @loader_path/@executable_path sont refusées : leur
relocation n’a pas été qualifiée par cette voie.
Sources, commandes et hashes : results/native-execution-signed/ et
results/video-signed-control/manifest.json ; résultats historiques préservés.
Outils : clang17/Xcode26.3/SDK26.2, versions relevées précédemment ; leurs probes
ne sont pas relancées, les fichiers sont rafraîchis via provenance.py --hash-only.
Pilote GeForceMTLDriver inchangé : {m['driver_sha256']}
macOS/OCLP, protections, VBIOS, fréquences et registres matériels inchangés.
Objectif complet toujours ouvert : results/hardware-coverage.json.
'''
if summary.get('delivered_reproduction_command_verified'):
    text+='\nLa commande livrée a aussi été exécutée via run_signed_probe.py : retour0,\n1041 résultats exacts,47 gardes intactes. Manifest :\nresults/signed-add-reproduction/manifest.json.\n'
(root/'EXECUTION_NATIVE.txt').write_text(text)
print('Current GPU compute verified; signed video hardware blocker remains; cause of old hangs unproven')

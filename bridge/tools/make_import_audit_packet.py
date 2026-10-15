#!/usr/bin/env python3
"""Create a portable audit packet: own sources, raw proofs and measurements."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess,zipfile
root=Path(__file__).resolve().parents[1];out=root/'results/keplermetal-audit-packet';assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');driverHash=sha(driver)
cpu=json.loads((root/'results/import-contract-tests/execution.stdout').read_text());guards=json.loads((root/'results/import-real-guards/execution.stdout').read_text());assert cpu['failures']==guards['failures']==0
audit=json.loads((root/'results/shared-units-audited/manifest.json').read_text());bench=json.loads((root/'results/shared-benchmark-summary.json').read_text());promotion=json.loads((root/'results/import-audit-promotion.json').read_text())
assert driverHash==audit['driver_sha256']==bench['driver_sha256'] and len(audit['cases'])==288 and bench['independent_counter_and_raw_oracles_passed']
assert sha(root/'build/libKeplerProgramImport.dylib')==promotion['new_sha256']==audit['library_sha256']
for case in audit['cases']:
 d=json.loads((root/case['result']).read_text());assert d['mismatches']==d['guard_mismatches']==0
 if d['mode']=='nak':
  p=d['import'];assert p['contract_verified'] and not p['rejected_import'] and p['target_imports']==p['verified_imports']==1
  for e in p['events']:assert e['metadata_bytes_preserved_except_import_fields'] and e['code_input_unchanged_after_constructor']
regress=[]
for name in ('constant-unorm','vertex-unorm','both-vertex-constant-unorm','tess-factor1'):
 p=root/'results/import-graphics-regression'/name/'execution.stdout';d=json.loads(p.read_text())
 tests=d.get('tests',[d]);assert all(t.get('mismatched_channels',t.get('mismatches',0))==0 and t['command_status']==4 and t['import']['contract_verified']for t in tests)
 regress.append({'label':name,'result':str(p.relative_to(root))})
summary={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'CPU_contract_cases':len(cpu['cases']),'real_rejection_and_restoration_cases':len(guards['cases']),'shared_GPU_reproduction_cases':288,'graphics_regressions':regress,'benchmark_cases':12,'benchmark_samples':216,'GPU_completed_groups_verified':bench['GPU_completed_groups_verified_in_measured_samples'],'driver_unchanged':True,'driver_sha256':driverHash,'old_library_sha256':promotion['old_sha256'],'new_library_sha256':promotion['new_sha256'],'full_hardware_goal_complete':False,'new_Metal_family_qualified':False,'driver_system_rewritten':False,'hardware_instruction_resident_readback':False}
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text());row=next(r for r in ledger['coverage']if r['category']=='Application-local native program import')
addition='Bridge audit: exact driver hash pinned internally; original IMP published atomically before hook; rejection persists across all matching imports; metadata offsets relocated when after code; immutable input snapshot and post-constructor code check;16 CPU contract tests,5 real rejection/restoration tests,288 fresh shared fixtures, vertex/fragment/paired/tessellation regression; constructor bytes are distinguished from resident GPU instructions'
if addition not in row['tested_scope']:row['tested_scope']+='; '+addition
for e in ('AUDIT_PONT_NAK.txt','results/import-audit-summary.json','results/shared-units-audited/manifest.json','results/import-graphics-regression/commands.json','results/import-real-guards/execution.stdout'):
 if e not in row['evidence']:row['evidence'].append(e)
summary['coverage_updates']=[row];ledger['complete']=False;ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n');(root/'results/import-audit-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['KEPLERMETAL — audit du pont NAK/macOS, 13 octobre2026','',
 'Résultat : le pont exécute les programmes testés sur la GTX880M, avec',
 'reproduction fraîche des288cas, validation des buffers bruts et contrôles.',
 'Le benchmark actuel ne démontre aucun gain général : sur64groupes et64',
 'dispatches par lot, ratio médian apparié NAK/Metal2.008 pour les échanges',
 'shared48Kio,3.143 pour ADD partagé128threads. Ces ratios incluent readback',
 'amorti et compteurs GPU identiques ; détails/IQR et autres tailles joints.', '',
 'MÉCANISME EXACT',
 'NAK génère du SASS SM30. Une bibliothèque Metal porteuse est compilée par',
 'la toolchain locale, avec les ressources, paramètres et mémoire partagée',
 'correspondants. Le client appelle explicitement KPCreatePipeline.',
 'Pendant cette création seulement, dans son propre processus, la bibliothèque',
 'remplace NVMTLFunctionVariant::initWithCompilerOutput:size:device:.',
 'Signature Objective-C observée : @40@0:8r^v16Q24@32.',
 'Le constructeur original est publié avant le hook. Un mutex sérialise les',
 'imports KP ; un contexte thread_local cible les appels de ce thread.',
 'Les autres threads sont transmis au constructeur original. Le host ne doit',
 'pas installer un autre interposeur concurrent sur cette méthode.',
 'Un @finally restaure le constructeur, même lors d’erreur/exception.', '',
 'CONTENEUR ET MÉTADONNÉES',
 'Versions7/8/9 ; total32bits à+4 ; sections liées àpartir de+8 :',
 'u64 next relatif, u32 type, u32 longueur, puis payload.32sections maximum.',
 'La première section type1 contient le stage : compute5,vertex0,fragment4,',
 'évaluation de tessellation2. Métadonnées type0x10004 de232octets ; code',
 'type0x10005. Compute : SASS seul ; graphique : préfixe natif80B conservé.',
 'Le SASS est remplacé par le code NAK. Le total, la longueur de code et son',
 'lien suivant sont ajustés. Dans les232B de métadonnées, seuls les mots7',
 '(+28,GPR),9(+36)et11(+44) changent. Les deux derniers acceptent0/576 selon',
 'le profil testé ; leur signification complète n’est pas prétendue décodée.',
 'Toutes les autres données, dont les conventions et allocations natives,',
 'restent identiques. Un contrôle compare explicitement les autres octets.',
 'La bibliothèque relit128B du _variant de l’objet dans son propre processus :',
 '_variant doit être un pointeur àoffset32 ; taille de code u64 à+24, GPR u32',
 'à+48. L’ensemble des imports ciblés doit être accepté avant tout dispatch.',
 'Les payloads sont retenus avec le pipeline pour leur durée de vie.', '',
 'RESSOURCES ET SOUMISSION',
 'Le pilote installé garde les allocations MTLBuffer/MTLTexture, adresses,',
 'blits, commandes, fences et programmation du matériel. Aucun QMD brut ou',
 'ioctl expérimental n’est soumis. Le contrat Linux CB0 de hw_runner.rs est',
 'une référence, pas le contrat macOS utilisé ici.',
 'Dans ces fixtures, CB1 porte les bindings : entrée32B, adresse64bits à+8.',
 'Les paramètres uniformes sont dans CB2. Le shader partagé reçoit output',
 'address àCB2+0,seed+8,active+12,variant+16,operand+20 ; le benchmark ajoute',
 'progress address64bits à+24. Workgroup size : CB1+0x6f0.',
 'Le carrier doit correspondre au code pour les bindings et la mémoire static.',
 'La bibliothèque ne déduit pas la sécurité mémoire d’un kernel arbitraire.',
 'Private est lu par blit vers Managed/NoCopy ; synchronisation Managed avant',
 'lectureCPU. Aucun contents de buffer Private n’est utilisé comme readback.', '',
 'CORRECTIONS APPORTÉES PAR CET AUDIT',
 '1. Une validation réussie ne masque plus un appel ciblé invalide ultérieur :',
 '   rejet persistant, compteurs imports ciblés/vérifiés, refus du cache sanscallback.',
 '2. Le chemin/empreinte du GeForceMTLDriver est contrôlé par la bibliothèque,',
 '   au-delà des contrôles précédemment faits par les scripts.',
 '3. Le pointeur du constructeur original est publié atomiquement avant hook,',
 '   pour éviter une fenêtre avec pointeur non initialisé sur un autre thread.',
 '4. Les offsets de metadata située après code sont ajustés quand le code',
 '   change de taille ; aucun accès àun ancien offset n’est effectué.',
 '5. Copie immutable du SASS fourni ; contrôle après constructeur ; restauration',
 '   du contexte parent lors d’exception dans le chemin vertex/fragment couplé.',
 'Tests :16cas CPU simulés,5refus/restaurations sur le vrai device sans dispatch,',
 '288cas GPU frais,3cas de rendu(stages0/4/couplés)et tessellationstage2facteur1.',
 'Les cas CPU avec metadata après code testent le repacker ; ils ne qualifient',
 'pas àeux seuls un nouveau format de conteneur réel du pilote.', '',
 'NIVEAU DE PREUVE ET LIMITES',
 'imported_code_identical compare les octets présentés au constructeur, avant',
 'et après celui-ci. decoded_* contrôle des métadonnées décodées. Aucun de ces',
 'champs seul ne prouve que les instructions ont été exécutées sur le GPU.',
 'La preuve d’exécution des cas repose aussi sur dispatch, résultat brut CPU,',
 'gardes et témoin natif porteur différent ; le benchmark ajoute compteurs de',
 'groupes terminés et checksums produits surGPU, pour chaque répétition.',
 'Aucun dump des instructions résidentesGPU n’a été réalisé. Aucun attestation',
 'matérielle distante : la vérification offline confirme fichiers/cohérence',
 'arithmétique ; la reproduction GPU nécessite cet iMac et le profil décrit.',
 'Le hash impose ce composant utilisateur précis ; il ne constitue pas une',
 'qualification de toutes versions de macOS/OCLP/HAL/IOAccelerator.',
 'AIR→NIR n’est validé que sur les programmes antérieurs testés ; ces kernels',
 'shared et benchmarks partent de NIR construit explicitement. Il n’existe',
 'pas encore de frontend MSL universel ou de Metal3/4 complet exposé aux apps.',
 'Pas de nouveau pilote système, d’accélération WindowServer, d’occupation GPU',
 'mesurée ou de fréquence imposée. Le compte24GPR demandé pour NAK possède',
 'un plancher hérité du profil ; aucune causalité de performance n’en est déduite.',
 'L’erreur native Metal weak-CAS InvalidResource reste distincte et non résolue.',
 'Les deux compteurs comparés sont uint32 en shared ; le code natif montre aussi',
 'des accès locaux de temporaires, absents du NAK testé. Leur rôle dans l’échec',
 'n’est pas démontré. Les échecs et sources originales sont conservés.', '',
 'PROFIL ET REPRODUCTION',
 'GPU : GTX880M GK104/SM30 ; macOS26.7.1 build25G241, iMacIntel.',
 'Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2.',
 'GeForceMTLDriver SHA256 : '+driverHash,
 'Ancienne bibliothèque utilisateur conservée ; nouvelle SHA256 : '+promotion['new_sha256'],
 'Header/API : src/KeplerProgramImport.h ; implémentation : .mm.',
 'clang++ -O3 -std=c++17 -fno-objc-arc -dynamiclib src/KeplerProgramImport.mm',
 '  -framework Metal -framework Foundation -install_name @rpath/libKeplerProgramImport.dylib',
 '  -o build/import-audit/libKeplerProgramImport.dylib',
 'python3 tools/reproduce_shared_units.py --import-library build/import-audit/libKeplerProgramImport.dylib --out results/shared-units-reproduction',
 'python3 tools/make_shared_units_report.py --input results/shared-units-reproduction',
 'python3 tools/reproduce_shared_benchmark.py --out results/shared-benchmark-reproduction',
 'python3 tools/make_shared_benchmark_report.py --input results/shared-benchmark-reproduction',
 'Chaque dossier de reproduction doit être nouveau. Les commandes complètes',
 'avec flags/archives/chemins et les sources figées sont dans les dossiers joints.',
 'L’archive exclut les exécutables du pilote système ; seules leurs empreintes',
 'sont partagées. verify_packet.py fonctionne sans Metal pour les fichiers bruts.',
 'La couverture complète du matériel reste ouverte : hardware-coverage.json.']
(root/'AUDIT_PONT_NAK.txt').write_text('\n'.join(lines)+'\n')
delta=subprocess.run(['diff','-u',str(root/'results/import-audit-before/KeplerProgramImport.mm'),str(root/'src/KeplerProgramImport.mm')],capture_output=True,text=True);assert delta.returncode in (0,1);(out/'bridge-import-audit.patch').write_text(delta.stdout)
files=[root/p for p in ('AUDIT_PONT_NAK.txt','MEMOIRE_PARTAGEE.txt','COMPARAISON_METAL_NAK.txt','src/KeplerProgramImport.mm','src/KeplerProgramImport.h','src/KeplerResourceABI.h','tools/import_contract_test.mm','tools/import_guard_probe.mm','tools/reproduce_shared_units.py','tools/make_shared_units_report.py','tools/reproduce_shared_benchmark.py','tools/make_shared_benchmark_report.py','tools/run_signed_probe.py','results/import-audit-summary.json','results/import-audit-promotion.json','results/shared-benchmark-summary.json','results/hardware-coverage.json','results/provenance.json')]
trees=('results/shared-units-audited','results/shared-benchmark-final','results/import-contract-tests','results/import-real-guards','results/import-graphics-regression','results/import-audit-before','results/shared-atomics-first-gpu','results/shared-atomics-serial-reference','results/shared-cas-reference-isolated')
for tree in trees:
 for f in (root/tree).rglob('*'):
  if f.is_file() and (f.suffix in ('.json','.txt','.c','.mm','.h','.py','.metal','.sass','.asm','.bin','.metallib')or f.name in ('execution.stdout','execution.stderr','launcher.stdout','launcher.stderr')):files.append(f)
for f in dict.fromkeys(files):
 dest=out/f.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
entries=[{'path':str(f.relative_to(out)),'bytes':f.stat().st_size,'sha256':sha(f)}for f in sorted(out.rglob('*'))if f.is_file()];(out/'packet-manifest.json').write_text(json.dumps({'generated_at':summary['collected_at'],'files':entries,'offline_scope':'Integrity and arithmetic checks only; no remote hardware execution attestation'},indent=2)+'\n')
print('Audit packet folder ready:',len(entries),'files. Add verifier before zipping.')

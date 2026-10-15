#!/usr/bin/env python3
"""Package lightweight source/evidence and verify the relocated raw outputs."""
from pathlib import Path
import datetime, hashlib, json, subprocess, tempfile, zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/air-cas-final'
packet=ROOT/'KEPLERMETAL_AIR_CAS_2026-10-13.zip'
assert not packet.exists(), 'Keep existing delivered snapshots; use another packet name.'
readme=OUT/'PAQUET.txt'
readme.write_text('''Ce paquet contient sources, AIR/NIR/SASS, captures natives, données GPU brutes,
oracles et échecs connus. Les executables de compilation/décodage/sondes et
objets .o sont exclus; les archives Mesa/OpenNVDA et la bibliothèque d’import
auditée restent dans le workspace existant. Ce n’est pas une distribution
de pilote macOS. Les commandes de RAPPORT.txt reproduisent le travail dans
ce workspace, avec dossiers de sortie inédits. Le contrôleur actuel inclut
les étapes de décodage auparavant enregistrées dans decode-commands.json.

Vérification CPU du paquet extrait (aucun accès GPU):
python3 tools/verify_air_cas.py --input results/air-cas-final --relocate-from "<LOCAL_LAB_ROOT>" --relocate-to .
Code de retour1 attendu pour les trois mots expected incorrects du chemin
natif partagé; les quatre configurations AIR/NAK doivent être correctes.
Les handles/PIDs historiques conservés ne signifient pas un processus actif.
''')
excluded={'air_cas_compile','envydis','air_cas_probe','air_contract_probe','compiler_output_trace'}
paths=[]
for name in ['cas-lowering-initial','cas-lowering-corrected','cas-lowering-final','air-cas-final']:
    for path in (ROOT/'results'/name).rglob('*'):
        if path.is_file() and not path.is_symlink() and path.suffix!='.o' and path.name not in excluded:
            if path.name not in ['delivery.json','packet-files.json']:paths.append(path)
paths += [ROOT/'tools'/name for name in ['air_cas_compile.c','prepare_cas_lowering.py','reproduce_air_cas.py',
          'air_cas_probe.mm','verify_air_cas.py','air_contract_probe.c','make_air_cas_report.py','package_air_cas.py']]
paths += [ROOT/'src'/name for name in ['air_cas_carrier.metal','opennvda-air-cas-result.patch','KeplerProgramImport.h']]
paths=sorted(set(paths))
entries=[]
with zipfile.ZipFile(packet,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for path in paths:
        name=str(path.relative_to(ROOT));data=path.read_bytes();archive.writestr(name,data)
        entries.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
with zipfile.ZipFile(packet) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist())=={entry['path'] for entry in entries}
    for entry in entries:assert hashlib.sha256(archive.read(entry['path'])).hexdigest()==entry['sha256']
    with tempfile.TemporaryDirectory(prefix='air-cas-packet-check-',dir=ROOT/'results') as temporary:
        destination=Path(temporary)
        archive.extractall(destination)
        result=subprocess.run(['python3',str(destination/'tools/verify_air_cas.py'),
            '--input',str(destination/'results/air-cas-final'),'--relocate-from',str(ROOT),
            '--relocate-to',str(destination)],capture_output=True,text=True,timeout=20)
        assert result.returncode==1,result.stderr
        verified=json.loads((destination/'results/air-cas-final/independent-verification.json').read_text())
        assert (verified['cases'],verified['passed'],verified['failed'],verified['bad_words'])==(9,8,1,3)
        assert not verified['guard_mismatches']
delivery={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'path':str(packet),
          'bytes':packet.stat().st_size,'sha256':hashlib.sha256(packet.read_bytes()).hexdigest(),
          'files':len(entries),'CRC_and_file_hashes_verified':True,
          'relocated_CPU_oracle':{'cases':9,'passed':8,'known_native_failures':1,'bad_words':3,'guard_mismatches':0},
          'executables_excluded':True,'full_hardware_goal_complete':False}
(OUT/'packet-files.json').write_text(json.dumps(entries,indent=2)+'\n')
(OUT/'delivery.json').write_text(json.dumps(delivery,indent=2)+'\n')
print(json.dumps(delivery,indent=2))

#!/usr/bin/env python3
"""Create a small source-only bundle for the M1 reference, without credentials."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,tarfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();tree=out/'KeplerMetalReference';tree.mkdir();(tree/'results').mkdir()
names=['tools/metal_reference_client.mm','tools/build_metal_reference.py','tools/run_metal_reference.py','tools/verify_metal_reference.py','tools/lab_gpu_reservation.py','sdk-combined/runtime/run_sdk_host.py','src/KeplerCPUICB.h','src/cpu_icb_literal_lut.metal','src/cpu_icb_literal_lut_values.json','src/cpu_icb_literal_lut_manifest.json']
for n in names:
 dst=tree/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,dst)
readme='''KeplerMetal — référence comportementale Metal native, source seulement

Ce dossier ne contient ni binaire x86_64, ni bibliothèque KeplerMetal, ni
pilote, ni secret. Le header public est fourni pour compiler le même client ;
les références à l'adaptateur sont éliminées du build natif. Compiler sur le M1
avec Xcode/SDK26 ou plus récent. Inspecter sw_vers, uname-m et SDK avant usage.
Ne pas modifier xcode-select ou le système : utiliser une toolchain déjà présente.
Si le SDK/compiler Metal n'est pas disponible, conserver le diagnostic et arrêter.

Depuis ce dossier, avec des noms de résultats neufs :
python3 tools/build_metal_reference.py --out results/M1-native-build
python3 tools/run_metal_reference.py --build results/M1-native-build --out results/M1-caps --reservation-root . --mode caps
python3 tools/verify_metal_reference.py results/M1-caps --out results/M1-caps/independent-verification.json
python3 tools/run_metal_reference.py --build results/M1-native-build --out results/M1-direct --reservation-root . --mode native
python3 tools/verify_metal_reference.py results/M1-direct --out results/M1-direct/independent-verification.json
python3 tools/run_metal_reference.py --build results/M1-native-build --out results/M1-ICB --reservation-root . --mode native_icb
python3 tools/verify_metal_reference.py results/M1-ICB --out results/M1-ICB/independent-verification.json

Les runs de calcul utilisent7scénarios LUT, groupes jusqu'à1024, sortie et
entrée Private, compteurs GPU. Les sources MSL sont compilées sur le M1 ;
ne pas réutiliser le metallib NVIDIA comme programme AppleGPU.
La voie native ICB crée un pipeline avec supportIndirectCommandBuffers=YES
et annonce les ressources nécessaires par useResource. La copie d'ICB du
scénario3 est une copie GPU avec commit/wait, puis reset de la source.
La copie KeplerMetal est un snapshot CPU : mécanismes distincts à comparer
comme tels. Comparer résultats, gardes, états et appels, sans attribuer une
différence de vitesse au pilote entre architectures.

Les Metal4flags et la création d'une queue sont observés ; ce n'est pas un
test d'exécution Metal4complet. Aucun shader SM30, FP64Kepler ou importeur
NVIDIA n'est validé par cette référence AppleGPU.
Une absence de factory est OBSERVED_UNAVAILABLE, sans dispatch, pas un PASS
d'ICB. Toute erreur numérique/guard reste un échec. Ne pas relancer après
timeout sans vérifier le processus exact ; le verrou reste prudent.
Le runner coordonne ces essais, pas le moteur MLX ou les autres applications.
Conserver leurs services et réglages ; aucun moteur partagé n'est arrêté.

Le paquet est préparé depuis l'iMac. Son transfert et ses empreintes sur M1
doivent être attestés avant l'exécution. La compilation/exécution M1 n'a pas
été effectuée au moment de sa création. Gitmain sans premier commit ;
les empreintes du FILE_MANIFEST.json définissent cet instantané source.
'''
(tree/'README.txt').write_text(readme)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entries=[{'path':str(x.relative_to(tree)),'bytes':x.stat().st_size,'SHA256':sha(x)} for x in sorted(tree.rglob('*')) if x.is_file()]
(tree/'FILE_MANIFEST.json').write_text(json.dumps({'files':entries,'Git_branch':'main','Git_commit':None,'M1_execution':False,'source_only':True,'Qwen_job_ids':[]},indent=2)+'\n')
archive=out/'KeplerMetalReference-M1-source-2026-10-14.tar.gz'
with tarfile.open(archive,'x:gz') as t:
 for f in sorted(tree.rglob('*')):
  if not f.is_file():continue
  raw=f.read_bytes();i=tarfile.TarInfo('KeplerMetalReference/'+str(f.relative_to(tree)));i.mode=0o644;i.size=len(raw);i.mtime=0;t.addfile(i,io.BytesIO(raw))
with tarfile.open(archive) as t:
 for e in entries:
  raw=t.extractfile('KeplerMetalReference/'+e['path']).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
delivery={'path':str(archive),'SHA256':sha(archive),'files':len(entries)+1,'all_source_SHA_verified':True,'M1_transfer':False,'M1_execution':False,'Qwen_job_ids':[]};(out/'delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))

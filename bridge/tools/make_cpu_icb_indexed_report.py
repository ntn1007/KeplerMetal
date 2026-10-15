#!/usr/bin/env python3
"""Reconcile indexed rendering evidence and preserve the full goal's open scope."""
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];R=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-indexed-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
names=['cpu-icb-indexed-prepared','cpu-icb-indexed-gpu-qualified','cpu-icb-indexed-direct-regression-prepared','cpu-icb-indexed-direct-regression-gpu-qualified','cpu-icb-indexed-mixed-regression-prepared','cpu-icb-indexed-mixed-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for n in names:
    p=ROOT/'results'/n;process=read(p/'execution/manifest.json');assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'] and not any(process['signed_executable'] in x for x in ps.splitlines())
    for f,h in read(p/'inputs.json')['source_hashes'].items():
        assert sha(p/f)==h;folder='src' if f.startswith('Kepler') or f.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/f)==h
    v=read(p/('independent-verification.json' if 'mixed-' in n else 'verification.json'));assert v['status']=='PASS';history.append({'cohort':n,'pid':process['pid'],'exit_code':0,'terminal':True,'verifier_status':v['status']})
gpu=read(ROOT/'results/cpu-icb-indexed-gpu-qualified/verification.json');direct=read(ROOT/'results/cpu-icb-indexed-direct-regression-gpu-qualified/verification.json');mixed=read(ROOT/'results/cpu-icb-indexed-mixed-regression-gpu-qualified/independent-verification.json');assert gpu['correct_float32_channels']==147456 and gpu['GPU_compute_invocations_counted']==128
system=read(OUT/'system-check.json');assert system['system_files_unchanged']==83 and system['rootpatch_unchanged']
for row in system['system_files']:assert sha(Path(row['path']))==row['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256']
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'indexed_domain_contract':'Caller supplies post-baseVertex fetch indices inside declared domain; Private contents not checked before submission. All actual fixture indices checked after GPU completion.','tested_base_vertex':[5,-2],'tested_base_instance':[3,5],'tested_instances':[2,17,64],'GPU_generated_indices_format':'UInt32; UInt16 path qualified with uploaded private indices','full_ICB_contract':False,'GPU_generated_ICB':False,'fragment_resources_qualified':False,'pressure_concurrency_conformance':False,'ordinary_application_integration_complete':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'direct_regression_float32_channels':direct['correct_float32_channels'],'mixed_regression_invocations':mixed['GPU_compute_invocations_counted'],'mixed_regression_float32_channels':mixed['correct_float32_channels'],'vertex_library_SHA256':sha(ROOT/'results/cpu-icb-indexed-gpu-qualified/vertex_io_carrier.metallib'),'indexed_manifest_SHA256':sha(ROOT/'src/cpu_icb_indexed_profiles.json'),'compute_library_SHA256':sha(ROOT/'results/cpu-icb-indexed-gpu-qualified/cpu_icb_gpu_indices.metallib'),'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current source copy on MrWhite not verified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'machine':system,'current_source_hashes':gpu['source_sha256'],'verifier_SHA256':sha(ROOT/'tools/verify_cpu_icb_indexed.py'),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[]})
coverage=read(ROOT/'results/hardware-coverage.json');assert not coverage['complete'] and len(coverage['coverage'])==30
text=' Indexed native stage-in CPU ICB rendering qualified on UInt16/UInt32, signed baseVertex5/-2 and instances2/17/64:12CB,15 copied records,147456 float32 components. Native one-index primers cannot form triangles and are replaced by cached60-byte records. Native compute emits UInt32 indices into the same Private buffer consumed by stage-in render in one CB,128 counted invocations, no intermediate CPU read. Degenerate/missing producer/consumer, copies/reset, caller state and pre-commit scope release qualified. Explicit index domain is a valid-input contract, not an untrusted Private-data validator. No GPU-resident/generated ICB or benchmark.'
for row in coverage['coverage']:
    if row['category'] in ('Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
        if text not in row['tested_scope']:row['tested_scope']+=text
        for e in ['CPU_ICB_RENDU_INDEXE.txt','results/cpu-icb-indexed-progress/summary.json','results/cpu-icb-indexed-gpu-qualified/verification.json']:
            if e not in row['evidence']:row['evidence'].append(e)
for p in [ROOT/'results/hardware-coverage.json',R/'inventory/hardware-coverage.json',R/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(R/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
    if row['id'] in ('B10','B10C'):
        row['pipeline_execution_justesse']+=' Nouveau stage-in indexé16/32:12CB/15records/147456float32; baseVertex5/-2, baseInstance3/5, instances2/17/64. UInt32 produits par kernel natif puis consommés sans lectureCPU intermédiaire,128invocations comptées; contrôles/reset/copies/lifetime/caller PASS.'
        row['modification_necessaire']='Ressources fragment/textures/samplers, états/cibles supplémentaires, mélange legacy/stage-in, ranges/timeline et format ICB GPU-résident/génération, pression/concurrence, benchmark et L2/L3 restent ouverts. Le domaine des indices privés est une précondition de validité, pas une validation GPU de données arbitraires.'
        row['preuve']+='; ../bridge/CPU_ICB_RENDU_INDEXE.txt; ../bridge/results/cpu-icb-indexed-gpu-qualified/verification.json'
dump(R/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (R/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
plans=read(R/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in plans:
    if row['id']=='B2':row['etat']='Stage-in direct puis indexé16/32 qualifiés L1; indicesUInt32 GPU→Private→render dans le mêmeCB,128invocations/147456float32; contrôles et régressions PASS.';row['travail']='Raccorder les ressources fragment natives au même contrat réfléchi, puis états/cibles/pression/concurrence. Préserver le contrat de validité des indices; format GPU-résident/génération et intégration L2/L3 restent distincts.'
dump(R/'reports/EXPERIMENTATIONS_PRIORISEES.json',plans)
report=f'''KEPLERMETAL — RENDU INDEXÉ NATIF DANS LE PROTOTYPE ICB

PROGRESS, objectif global encore incomplet. Branche B : extension applicative
du contrat CPU ICB. Aucune nouvelle modernisation Linux/pilote installée.

Résultat GTX 880M :12CB,15 records indexés copiés,147456 float32 corrects,
23040 pixels colorés. Erreur max {gpu['maximum_float_error']:.12g}, tolérance2e-6.
Indices16/32, baseVertex5 et-2, baseInstance3/5, instances2/17/64;
smooth/linear/flat, buffers vertex/instance/index Private et gardes intacts.
Trois pipelines natifs créés et possédés depuis la même bibliothèque vérifiée.

Preuve : huit captures passives non soumises montrent la macro0x3aa8 et les
méthodes restart0x1644/index-address0x17c8. Les records60octets conservent
leur adresse/type et les arguments natifs, dont le décalage signé. Ce ne sont
pas des équivalences avec les numéros des slots MME Nouveau.
Une amorce native indexCount1 produit l'état; elle ne forme pas de triangle.
Seuls ses60octets index+draw sont remplacés par le record count3/6. Les autres
prefixes natifs sont conservés. Un lecteur Mach distinct recapture les bytes.
L'oracle confronte chaque paquet réel et chaque image à la référence CPU.

Chaîne GPU : kernel NVIDIA gpu_indices→uint4 Private→shader vertex stage-in
NVIDIA natif dans un même CB.128 invocations comptées (4×32); aucun accès CPU
aux indices produits entre compute et render. Les UInt32 réels, leur stamp et
le compteur sont lus seulement après completion et comparés à la source du
kernel. Le format16 est qualifié avec des données uploadées, pas un producteur16.
Retirer le producteur ou le consommateur et générer des indices dégénérés
conserve les sorties attendues. Copies/reset du source, réutilisation et mise
à jour de données privées passent. DernierCB : classes/scope/ICB et refs locales
fermés avant commit, image correcte. Le rendu caller après ICB passe aussi.

Cinq refus : alignement/extent/count d'indices, baseVertex hors limite et
copie vers descriptor de capacité vertex insuffisante. La capacité de copie
est maintenant vérifiée; les anciens profils de calcul/rendu restent conservés.
Régressions aux mêmes bytes courants : direct110592float32; ancien scope
calcul→indices→rendu192invocations/110592float32 PASS. Six processus de ces
cohortes terminés exit0, aucun SIGKILL.83fichiers système/rootpatch inchangés.

Contrat important : le manifeste déclare un domaine de sommets APRÈS ajout de
baseVertex (5..10 ici). Les buffers sont dimensionnés pour tout ce domaine.
L'application doit fournir des indices valides. Les contenus Private ne sont
pas inspectés par le CPU avant la soumission. La qualification vérifie après
exécution que tous les indices réels sont dans le domaine; elle ne prouve pas
une protection générale contre des indices arbitraires ou malveillants.

Bibliothèque vertex :{summary['vertex_library_SHA256']}
Manifeste indexé :{summary['indexed_manifest_SHA256']}
Bibliothèque compute :{summary['compute_library_SHA256']}
Driver :2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Versions exactes macOS/clang/SDK et sources SHA :
results/cpu-icb-indexed-progress/provenance.json. Git main UNBORN, aucun commit.
Sources modifiées :KeplerCPUICB et KeplerNativeRenderDraws; les shaders NVIDIA
natifs restent inchangés. Le manifeste ajoute indexed_vertex_domain.

Reproduction depuis bridge, dossiers de sortie neufs :
python3 tools/reproduce_cpu_icb_indexed.py --out results/repro-indexed-prepare
python3 tools/verify_cpu_icb_indexed.py results/repro-indexed-prepare --current
python3 tools/reproduce_cpu_icb_indexed.py --execute --out results/repro-indexed-gpu
python3 tools/verify_cpu_icb_indexed.py results/repro-indexed-gpu --current
Les scripts archivent les inputs, argv de clang, exécutables originaux/signés
avec SHA, PID, status et raw. Les captures anciennes restent intactes.

Limites :L1, CPU materialisation/copie, une amorce native par record.
ICB GPU-résident/généré, ressources fragment, autres états/cibles, pression/
concurrence/conformance globale et intégration L2/L3 restent ouverts.
Aucun benchmark, gain CPU/GPU ou accélération WindowServer annoncé.
Qwen :les deux MCP/moteurs sont disponibles; job_ids=[] / revue NOT RUN,
car la copie actuelle des sources sur MrWhite n'est pas vérifiée.
Prochaine action :raccorder les ressources fragment depuis les fixtures
natives et préserver l'état du caller, puis qualifier leurs vrais résultats.
'''
(ROOT/'CPU_ICB_RENDU_INDEXE.txt').write_text(report);print(json.dumps(summary,ensure_ascii=False,indent=2))

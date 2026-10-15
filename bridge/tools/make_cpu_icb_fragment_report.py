#!/usr/bin/env python3
"""Reconcile native fragment resources with the ongoing full driver/API goal."""
from pathlib import Path
import csv,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/cpu-icb-fragment-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
cohorts=['cpu-icb-fragment-prepared-02','cpu-icb-fragment-gpu-qualified','cpu-icb-fragment-indexed-regression-prepared','cpu-icb-fragment-indexed-regression-gpu-qualified','cpu-icb-fragment-vertex-regression-prepared','cpu-icb-fragment-vertex-regression-gpu-qualified','cpu-icb-fragment-mixed-regression-prepared','cpu-icb-fragment-mixed-regression-gpu-qualified'];history=[];ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True)
for n in cohorts:
    p=ROOT/'results'/n;m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and not any(m['signed_executable'] in x for x in ps.splitlines())
    for f,h in read(p/'inputs.json')['source_hashes'].items():
        assert sha(p/f)==h;folder='src' if f.startswith('Kepler') or f.endswith(('.metal','.json')) else 'tools';assert sha(ROOT/folder/f)==h
    v=read(p/('independent-verification.json' if 'mixed-' in n else 'verification.json'));assert v['status']=='PASS';history.append({'cohort':n,'pid':m['pid'],'exit_code':0,'terminal':True,'verifier_status':v['status']})
gpu=read(ROOT/'results/cpu-icb-fragment-gpu-qualified/verification.json');baseline=read(ROOT/'results/native-fragment-arguments-gpu-baseline/independent-verification.json');index=read(ROOT/'results/cpu-icb-fragment-indexed-regression-gpu-qualified/verification.json');vertex=read(ROOT/'results/cpu-icb-fragment-vertex-regression-gpu-qualified/verification.json');mixed=read(ROOT/'results/cpu-icb-fragment-mixed-regression-gpu-qualified/independent-verification.json');assert gpu['correct_float32_channels']==98304 and baseline['correct_float32_channels']==36864
system=read(OUT/'system-check.json');assert system['system_files_unchanged']==83 and system['rootpatch_unchanged']
for row in system['system_files']:assert sha(Path(row['path']))==row['sha256']
assert sha(Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist'))==system['rootpatch_sha256']
summary={k:v for k,v in gpu.items() if k not in ('source_sha256','raw_sha256')};summary.update({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,'Git_branch':'main','Git_commit':None,'native_baseline_float32_channels':36864,'argument_buffer_encoded_length':24,'argument_buffer_reflected_alignment':256,'argument_buffer_encoder_alignment':8,'argument_resources':['Texture2D<float>','sampler','read-only buffer pointer'],'argument_buffer_CPU_accessible_only':True,'argument_buffer_native_encoding_certificates':True,'indirect_resources_leased_until_completion':True,'indexed_fragment_resources_qualified':False,'GPU_generated_argument_buffers_in_ICB_qualified':False,'pressure_concurrency_conformance':False,'ordinary_application_integration_complete':False,'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,'indexed_regression_float32_channels':index['correct_float32_channels'],'indexed_regression_compute_invocations':index['GPU_compute_invocations_counted'],'vertex_regression_float32_channels':vertex['correct_float32_channels'],'legacy_mixed_regression_float32_channels':mixed['correct_float32_channels'],'legacy_mixed_regression_compute_invocations':mixed['GPU_compute_invocations_counted'],'library_SHA256':sha(ROOT/'results/cpu-icb-fragment-gpu-qualified/fragment_resources.metallib'),'manifest_SHA256':sha(ROOT/'src/cpu_icb_fragment_profiles.json'),'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; current source transfer to MrWhite not verified'})
dump(OUT/'summary.json',summary);dump(OUT/'verification-history.json',history);dump(OUT/'provenance.json',{'machine':system,'current_source_hashes':gpu['source_sha256'],'verifier_SHA256':sha(ROOT/'tools/verify_cpu_icb_fragment.py'),'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),'Qwen_job_ids':[]})
coverage=read(ROOT/'results/hardware-coverage.json');assert not coverage['complete'] and len(coverage['coverage'])==30
addition=' Native fragment resources through CPU ICB setFragmentBuffer: three shader profiles use a native-encoded24-byte argument buffer carrying Texture2D/sampler/read-only parameter-pointer. Reflected ABI and per-execution payload certificate checked; indirect resource usage declared and exact certificate leases retained through completion.8CB/13records/98304 float32 exact on fixtures, read/nearest/linear, mutable parameters, rebinding resources without rematerialization, copies/reset, caller buffer/offset/inline restore and pending-CB scope teardown. Native baseline36864 float32 also passes. This does not implement direct ICB texture/sampler setters, GPU-resident/generated ICB, Private/GPU-written argument buffer certificates or general pressure/concurrency conformance.'
for row in coverage['coverage']:
    if row['category'] in ('Texture/sampler/surface units','Rasterization and render state','CPU-recorded compute ICB selectors and bounded resource lifetime'):
        if addition not in row['tested_scope']:row['tested_scope']+=addition
        for e in ['CPU_ICB_RESSOURCES_FRAGMENT.txt','results/cpu-icb-fragment-progress/summary.json','results/cpu-icb-fragment-gpu-qualified/verification.json']:
            if e not in row['evidence']:row['evidence'].append(e)
for p in [ROOT/'results/hardware-coverage.json',RESEARCH/'inventory/hardware-coverage.json',RESEARCH/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
matrix=read(RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.json')
for row in matrix:
    if row['id'] in ('B10','B10C'):
        row['pipeline_execution_justesse']+=' Fragment:argument buffer natif texture/sampler/pointer via setFragmentBuffer;8CB/13records/98304float32 exacts, read/nearest/linear, payload/data updates, copies/reset/caller/lifetime et6refus PASS. Baseline36864float32 native PASS.'
        row['modification_necessaire']='Combiner ressources fragment et stage-in indexé; argument buffers Private/écritsGPU avec résidence/cohérence, autres types/formats/états/cibles, mélange legacy, ranges/timeline, ICBGPU-résident/génération, pression/concurrence, benchmark et L2/L3 restent ouverts.'
        row['preuve']+='; ../bridge/CPU_ICB_RESSOURCES_FRAGMENT.txt; ../bridge/results/cpu-icb-fragment-gpu-qualified/verification.json'
dump(RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.json',matrix)
with (RESEARCH/'reports/METAL_CAPACITES_ACTUALISEES.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(matrix[0]));w.writeheader();w.writerows(matrix)
plans=read(RESEARCH/'reports/EXPERIMENTATIONS_PRIORISEES.json')
for row in plans:
    if row['id']=='B2':row['etat']='Fragment resources via native argument buffers qualified L1;8CB/98304float32 exacts, read/nearest/linear and caller/lifetime PASS. Indexed/vertex/legacy regressions PASS.';row['travail']='Combiner les domaines stage-in/indexé et fragment, puis qualifier ressources/argumentbuffersPrivate-GPUécrits et états/cibles/pression/concurrence. Format GPU-résident/génération et L2/L3 restent des intégrations distinctes.'
dump(RESEARCH/'reports/EXPERIMENTATIONS_PRIORISEES.json',plans)
(ROOT/'CPU_ICB_RESSOURCES_FRAGMENT.txt').write_text(f'''KEPLERMETAL — RESSOURCES FRAGMENT DANS LE PROTOTYPE ICB

PROGRESS. Objectif global encore incomplet. Branche B : extension applicative
du contrat CPU ICB. Aucune nouvelle modernisation Linux/pilote déployée.

Résultat GTX 880M :8CB,13 records copiés,98304 float32 corrects,21504 pixels
colorés. Erreur mesurée0 sur ces fixtures, tolérance2e-6. Référence native
directe séparée :3CB/36864float32 corrects. Read/nearest/linear, Texture2D
RGBA32Float Private, sampler natif et pointeur de paramètres readonly.

Contrat API :le SDK26.2 MTLIndirectRenderCommand contient setFragmentBuffer,
sans setter direct de texture/sampler. Les références sont regroupées dans
un argument buffer encodé par MTLArgumentEncoder de la fonction native vérifiée.
Sources :SDK MTLIndirectCommandEncoder.h/MTLArgument.h/MTLArgumentEncoder.h;
https://developer.apple.com/documentation/metal/mtlargumentencoder
https://developer.apple.com/metal/sample-code/
Ces interfaces sont distinctes de la prise en charge globale d'une famille Metal.

ABI observée :argument buffer24octets, alignmentencoder8, alignmentbinding256.
Membres :Texture2D<float> id0/offset0, sampler id1/offset8, pointeur de struct
params32octets/alignment16 id2/offset16. Reflection et taille d'encoder comparées
au manifeste; PSO et fonctions possédés depuis des octets in-memory SHA vérifiés.
Les références opaques restent encodées par le pilote natif, sans layout inventé.

Le certificat lie buffer/offset/ABI/payload natif exact et les objets référencés.
Chaque exécution, même cached/copied, refuse le payload modifié ou non encodé ici.
Textures/params/argumentbuffer déclarés useResource; références du certificat
courant capturées jusqu'à completion, même si le registre est ensuite actualisé.
Paramètres variables restent hors du payload certifié. Leur changement et celui
de texture/sampler/pointer donnent l'image attendue sans rematérialiser le draw.
La sécurité et la synchronisation de modifications concurrentes ne sont pas
qualifiées; l'application respecte la durée de vie et les échéances CPU/GPU.

Preuve :macro native0x3830 à3sommets remplace une amorce à1sommet qui ne forme
pas de triangle. Prefixes natifs conservés; lecteur Mach recapture les bytes;
raster/source-texture CPU indépendante calcule filtres et scale/bias. Aucun
setter texture/sampler fictif ajouté aux commandes ICB. Le buffer fragment
sélectionne ses références via l'argument buffer natif.

Contrôles :six refus d'alignement/index/capacité de copie, extent de buffer
référencé, payload non encodé et payload modifié. Source reset reste vide;
commandes copiées et données réutilisées passent. Caller :bulk fragmentbuffers,
offset et bytes inline restaurés avant un dessin natif ordinaire. Dernier CB
avec ressources :scope/classes/ICB et refs locales fermés avant commit, image
correcte. Les samplers utilisés sont créés avec supportArgumentBuffersYES.
Le backend accepte leur identité/device et l'encodage natif; il ne déduit pas
leur filtre d'un label ou d'une propriété inexistante sur MTLSamplerState.

Régressions aux bytes actuels :indexé147456float32 et128invocations compute;
vertex110592float32; legacy scope calcul+rendu110592float32/192invocations PASS.
Huit processus de ces cohortes terminés exit0, sans SIGKILL.83fichiers système
et rootpatch OCLP rehashés inchangés. Native baseline et captures conservées.

Bibliothèque :{summary['library_SHA256']}
Manifeste :{summary['manifest_SHA256']}
Driver :2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Git main UNBORN, aucun commit; versions macOS/clang/SDK et SHA sources dans
results/cpu-icb-fragment-progress/provenance.json.

Reproduction depuis bridge, dossiers neufs :
python3 tools/reproduce_native_fragment_arguments.py --execute --out results/repro-native-fragment
python3 tools/verify_native_fragment_arguments.py results/repro-native-fragment --current
python3 tools/reproduce_cpu_icb_fragment.py --out results/repro-fragment-prepare
python3 tools/verify_cpu_icb_fragment.py results/repro-fragment-prepare --current
python3 tools/reproduce_cpu_icb_fragment.py --execute --out results/repro-fragment-gpu
python3 tools/verify_cpu_icb_fragment.py results/repro-fragment-gpu --current
Sources/library/argv de clang, originaux/signés SHA, PID/status et raw archivés.

Limites :L1, CPU materialisation/copie et amorce par record. Argumentbuffers
Shared/Managed CPU-accessibles et payloads encodés ici seulement. Argumentbuffers
Private/écritsGPU, ressources fragment+indexé, autres types/formats/états/cibles,
pression/concurrence/conformance générale, formatICBGPU-résident/génération,
benchmark et intégration L2/L3 restent ouverts. Aucun gain CPU/GPU annoncé.
Qwen :deux MCP et moteurs disponibles; job_ids=[] / revueNOTRUN, copie actuelle
du code sur MrWhite non vérifiée. Les exécutions matérielles ont lieu sur l'iMac.
Prochaine action :combiner le contrat fragment avec stage-in/indexé, puis
généraliser mémoire des arguments et synchronisation sans modifier le système.
''')
print(json.dumps(summary,ensure_ascii=False,indent=2))

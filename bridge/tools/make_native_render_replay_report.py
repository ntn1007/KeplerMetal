#!/usr/bin/env python3
"""Reconcile native render transport proofs without starting another GPU test."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'driver-research-2026-10-13';OUT=ROOT/'results/native-render-replay-progress'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
gpu=read(ROOT/'results/native-render-replay-gpu-qualified/independent-verification.json')
prepared=read(ROOT/'results/native-render-replay-index-controls-prepared/independent-verification.json')
passive=read(ROOT/'results/native-render-command-stream-captured/independent-verification.json')
assert gpu['status']==prepared['status']=='PASS' and passive['status']=='PASS_PASSIVE_CAPTURE'
assert gpu['correct_float32_channels_including_native_control']==98304 and gpu['correct_replay_float32_channels']==86016
cohorts=['native-render-command-passive','native-render-command-fields-qualified','native-render-command-stream-captured','native-render-replay-prepared','native-render-replay-index-controls-prepared','native-render-replay-gpu-qualified']
ps=subprocess.check_output(['ps','-axo','pid,stat,command'],text=True);history=[]
for name in cohorts:
    folder=ROOT/'results'/name;m=read(folder/'execution/manifest.json')
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert not any(m['signed_executable'] in line or m['original_executable'] in line for line in ps.splitlines())
    hashes=read(folder/'inputs.json')['source_hashes']
    for file,h in hashes.items():assert sha(folder/file)==h
    if name in ['native-render-command-stream-captured','native-render-replay-index-controls-prepared','native-render-replay-gpu-qualified']:
        for file,h in hashes.items():assert sha(ROOT/('src' if file.startswith('Kepler') else 'tools')/file)==h
    history.append({'cohort':name,'pid':m['pid'],'exit_code':0,'terminal':True,'source_hashes':hashes})
baseline=read(RESEARCH/'reports/STRATEGIE_PREUVES.json');checked=[]
for row in baseline['system_files']:
    h=sha(Path(row['path']));assert h==row['sha256'];checked.append({'path':row['path'],'sha256':h})
rootpatch=Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert len(checked)==83 and sha(rootpatch)==baseline['rootpatch_sha256']
assert sha(ROOT/'src/KeplerCPUICB.mm')=='7251ce7ab852cf042a9baf8695f35dcfe1a448767084b8be271f4077372aa550'
assert sha(ROOT/'src/KeplerNativeCommands.mm')=='b4f04b324135d2a4049c84bbf0dcd26dffaf794500387a25113fa638ffe73244'
OUT.mkdir(exist_ok=True)
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'goal_turn':'PROGRESS','goal_complete':False,
    'Git_branch':'main','Git_commit':None,'Git_state':'UNBORN; lab untracked; frozen SHA snapshots',
    'integration_level':1,'native_render_transport_GPU_qualified':True,'GPU_render_command_buffers':8,
    'native_control_command_buffers':1,'replay_command_buffers':7,'correct_float32_channels_total':98304,
    'correct_replay_float32_channels':86016,'colored_pixels_total':2605,
    'Private_index_UInt16_UInt32_data_dependence_qualified':True,'selective_and_total_draw_removal_qualified':True,
    'caller_release_lifetime_qualified':True,'exact_instance_invocation_count_qualified':False,
    'framebuffer_profile':{'width':64,'height':48,'format':'RGBA32Float','storage':'Private','sample_count':1},
    'record_bytes':[216,252,252],'bare_draw_bytes':[24,60,60],
    'GPU_resident_ICB':False,'render_ICB_public_API_implemented':False,'full_render_state_qualified':False,
    'native_shader_code_patched':False,'performance_benchmark':False,'all_children_terminal':True,
    'system_files_unchanged':83,'rootpatch_unchanged':True,'system_modified':False,
    'library_SHA256':'965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7',
    'Qwen_job_ids':[],'Qwen_review_status':'NOT RUN; MCP authenticated, current central source copy not verified'}
sources=['src/KeplerNativeRenderDraws.h','src/KeplerNativeRenderDraws.mm','tools/native_render_command_capture.mm',
    'tools/native_render_replay_probe.mm','tools/reproduce_native_render_capture.py','tools/reproduce_native_render_replay.py',
    'tools/verify_native_render_capture.py','tools/verify_native_render_replay.py','tools/decode_native_commands.py',
    'tools/run_signed_probe.py','tools/make_native_render_replay_report.py']
sdk=Path(subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True).strip())
header=sdk/'System/Library/Frameworks/Metal.framework/Headers/MTLIndirectCommandEncoder.h'
sdkcopy=OUT/header.name;sdkcopy.write_bytes(header.read_bytes())
provenance={'macOS':subprocess.check_output(['sw_vers'],text=True),'clang':subprocess.check_output(['clang++','--version'],text=True),
    'SDK_version':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),
    'Git_status':subprocess.check_output(['git','status','--short','--branch'],cwd=ROOT.parent.parent,text=True),
    'inputs':[{'path':str(ROOT/p),'sha256':sha(ROOT/p)} for p in sources],
    'system_files':checked,'rootpatch_sha256':sha(rootpatch),'SDK_indirect_command_header_SHA256':sha(header),
    'native_register_reference':read(ROOT/'results/native-render-references/references.json'),
    'system_modified':False,'Qwen_job_ids':[]}
dump(OUT/'summary.json',summary);dump(OUT/'provenance.json',provenance);dump(OUT/'verification-history.json',history)
coverage=read(ROOT/'results/hardware-coverage.json');assert len(coverage['coverage'])==30 and not coverage['complete']
for row in coverage['coverage']:
    if row['category']=='Rasterization and render state':
        addition=' Native render replay transport qualified separately: one pinned native vs_state/fs_state pipeline, Private64x48RGBA32F, direct and Private UInt16/UInt32 indexed draws, three scissors, raw CPU packet copies. Eight CB/98304float32 total (86016 replay); selective/total removal, private index degeneration and caller-release lease pass. Public render ICB API remains unimplemented.'
        if addition not in row['tested_scope']:row['tested_scope']+=addition
        for e in ['results/native-render-replay-gpu-qualified/independent-verification.json','results/native-render-replay-progress/summary.json','REJEU_RENDU_NATIF.txt']:
            if e not in row['evidence']:row['evidence'].append(e)
    if row['category']=='CPU-recorded compute ICB selectors and bounded resource lifetime':
        note=' A native-render packet transport is now GPU-qualified as an adjacent foundation; it is not yet connected to indirectRenderCommandAtIndex or executeCommandsInBuffer on render encoders.'
        if note not in row['remaining_requirements']:row['remaining_requirements']+=note
for p in [ROOT/'results/hardware-coverage.json',RESEARCH/'inventory/hardware-coverage.json',RESEARCH/'inventory/evidence-summaries/hardware-coverage.json']:dump(p,coverage)
report=f'''KEPLERMETAL — TRANSPORT DE RENDU NVIDIA NATIF QUALIFIÉ SUR GPU

Résultat: PROGRESS expérimental L1. Le nouveau module enregistre des commandes
de rendu générées par le pilote NVIDIA existant et les rejoue dans notre processus.
Le shader natif vs_state/fs_state et ses métadonnées restent inchangés, sans NAK.
Ce n'est pas encore une implémentation des objets/API ICB de rendu.

Preuve de calcul GPU
Huit CB de rendu complétés: un contrôle avec les appels natifs ordinaires et
sept essais de rejeu, dont un retire tous les dessins.98304 composantes float32
correctes selon le CPU, dont86016 dans les essais de rejeu.2605 pixels colorés
au total, fonds/effacements et toutes les gardes également vérifiés byte-à-byte.
Les cibles Private64x48RGBA32Float sont relues par blit dans des buffers Shared
avec256B de garde de chaque côté. Aucun pixel n'est écrit par le CPU après
l'initialisation des sentinelles. Capture et comparaison indépendante archivées.

Cas / sélection / pixels colorés:
0 natif[0,1,2]:535;1 rejeu[0,1,2]:535;2 rejeu[0,2]:348;
3 rejeu[1]:187;4 aucun dessin:0;5 après libération des refs client:535;
6 indices16 rendus dégénérés par blit GPU:348;7 indices32 dégénérés aussi:117.
Les index Private contiennent initialement0,1,2; UInt16 offset64/128B, UInt32
offset96/192B. Ils sont ensuite modifiés en0,0,0 puis1,1,1 sans changer les
records ou leurs adresses. Les zones concernées disparaissent exactement.
Les copies GPU relues confirment les données et les octets de garde des indices.
Ces contrôles distinguent l'usage réel des index d'un simple dessin direct.

Rectangles scissor:(3,4,13,9),(25,8,11,17),(9,30,21,11), trois triangles.
Le compteur d'instances2 est présent dans le record32bits; le shader actuel
n'observe pas instance_id: le nombre exact d'invocations d'instances n'est pas
qualifié par ce test. Pas de compteur d'invocations vertex/fragment annoncé.

Mécanisme et limites
Ivar m_renderer du NVMTLRenderCommandEncoder_KEPLER_A:offset120/objet128B.
Contexte CPP:queue+16,PushBuffer+32; cursor+0/end+136. La capacité observée du
push rendu est262144B; l'ancien filtre64Kio du contexte calcul ne s'applique pas.
Notre collecte lit les champs runtime et la mémoire du processus propre.
Un dessin direct:24B; indexé:60B; scissor16slots:192B supplémentaires.
Records216/252/252B,720B la séquence entière. Priming natif24B retiré avant
commit, puis commandes copiéesCPU; pas d'appels draw supplémentaires par record
dans les essais de rejeu. Un lease garde batch/library/pipeline/records/index/RT
jusqu'à completion, y compris après le drainage du pool et libération du client.
Les buffers d'enregistrement ne sont jamais soumis. Préparation: un CB de blit
d'initialisation des indices, zéro CB de rendu soumis. Qualification: quatre CB
de copies d'indices distincts des huit CB de rendu. Aucun benchmark/performance.

Les paquets sont strictement bornés au profil triangle trois sommets, une seule
library/PSO,64x48/format/sample1, trois scissors, indices16/32 et leases en série.
Les variations d'état complet, pipeline, viewport, targets/depth/blend, bindings,
primitives, vertexStart/baseVertex/baseInstance et la concurrence sont ouvertes.
Les registres de classeNVA097 sont définis dans le header NVIDIA fourni par Mesa:
scissor0xe04/0xe08+j*16, index0x17c8..0x17d8, restart0x1644.
Les méthodes0x3830 et0x3840 appellent les slotsMME6/8. Leur contenu est défini
par le pilote courant; les noms des slots Mesa/Nouveau ne lui sont pas attribués.
Header SHAa19bdee7c004b82dafd819c2b22246b80d7dc5bf3e175c87abfcd96699c5d348.
Cette copievendor n'a pas de .git: pas de commit inféré depuis le dépôt parent.
Premiers essais de capture conservés: m_renderer découvert après les hypothèses
m_render/m_graphics; puis capacité rendue observée, toutes collectes terminées.

Suite API Metal: le SDK26.2 MTLIndirectRenderCommand fournit setPipeline/buffers
et draw/indices/patches, sans setter scissor. Le scissor actuel par record est
un outil de preuve. Le raccord public doit respecter l'état de l'encodeur de
rendu au lieu d'inventer un setter ICB scissor. Les déclarations runtime des
méthodes sont insuffisantes: executeCommandsInBuffer se résout au stub MetalOld,
déjà refusé dans les essais ICB archivés, et pas à une implémentation NVIDIA.
Raccord CPU ICB rendu, indirection/générationGPU et intégrationL2/L3 restent ouverts.
BrancheB: fondation de transport native, pas de support Metal3/4 complet.
BrancheA: aucune amélioration Linux portée ni fichier du pilote installé modifié.

Versions/provenance
Git mainUNBORN, aucun commit; lab non suivi, snapshots SHA sources exécutées.
Library965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7
Driver2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
macOS/clang/SDK/sources/83fichiers:results/native-render-replay-progress/provenance.json.
83 fichiers système et plist rootpatch OCLP rehashés inchangés. Modules calcul
KeplerCPUICB/KeplerNativeCommands inchangés; aucune nouvelle régression calcul
exécutée, les preuves grilles2D/3D précédentes portent sur les mêmes bytes.
Tous les six processus signés de l'étape ont exit0, aucun encore actif/SIGKILL.

Commandes depuis {ROOT}; nouveaux dossiers uniquement:
python3 tools/reproduce_native_render_capture.py --out results/NOUVELLE-capture
python3 tools/verify_native_render_capture.py --input results/NOUVELLE-capture
python3 tools/reproduce_native_render_replay.py --out results/NOUVEAU-render-prepare
python3 tools/verify_native_render_replay.py --input results/NOUVEAU-render-prepare --check-current-sources
Après PASS, sous le même pilote:
python3 tools/reproduce_native_render_replay.py --out results/NOUVEAU-render-gpu --execute
python3 tools/verify_native_render_replay.py --input results/NOUVEAU-render-gpu --check-current-sources
Compiler/commandes signées/exit/SHA et résultats bruts sont figés par cohorte.

Qwen: deux MCP authentifiés/disponibles au contrôle; job_ids=[]; review NOT RUN.
Source centrale correspondant à cette nouvelle extension non vérifiée, solo autorisé.
Tâche T-20261013-230031-fe3487, propriétairecodex. Objectif global incomplet/actif.
Prochaine action: intégrer conservativement ce transport aux objets CPU ICB de
rendu et aux sélecteurs publics, en conservant l'état hérité de l'encodeur.
'''
(ROOT/'REJEU_RENDU_NATIF.txt').write_text(report);print(json.dumps(summary,ensure_ascii=False,indent=2))

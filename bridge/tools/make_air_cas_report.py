#!/usr/bin/env python3
"""Report the bounded AIR CAS result and native register-flow evidence."""
from pathlib import Path
import argparse, datetime, hashlib, json

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--compiler-input',type=Path,required=True);args=parser.parse_args()
OUT=args.input.resolve();COMP=args.compiler_input.resolve();OUT.relative_to(ROOT/'results');COMP.relative_to(ROOT/'results')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
verification=json.loads((OUT/'independent-verification.json').read_text())
cases=json.loads((OUT/'results.json').read_text())
contracts=json.loads((OUT/'air-type-contracts.json').read_text())
assert len(contracts)==2 and all(row['calls'][0]['return_bits']==32 and
       row['calls'][0]['expected_pointee_bits']==32 for row in contracts)
assert (verification['cases'],verification['passed'],verification['failed'],verification['captures'],verification['words'])==(9,8,1,27,108)
assert verification['bad_words']==3 and not verification['guard_mismatches']
assert [c['name'] for c in cases if not c['result']['passed']]==['threadgroup-native-v1']
assert all(not c['process']['authoritative_ps_status'] and not c['process']['SIGKILL_requested'] for c in cases)
points={'comparand':'00000238','atomic_old':'00000250','success_compare':'000002c8',
        'old_register_overwritten':'000002f0','output_store':'00000328'}
lines=(OUT/'threadgroup-native-decode/execution.stdout').read_text().splitlines()
flow={name:next(line for line in lines if line.startswith(address)) for name,address in points.items()}
assert 'xor b32 $r0' in flow['comparand'] and 'ld lock $p1 $r4' in flow['atomic_old']
assert 'eq u32 $r0 $r4' in flow['success_compare'] and 'add b32 $r4' in flow['old_register_overwritten']
assert 'st b128 wb g[$r4d] $r0q' in flow['output_store']
system_snapshot=json.loads((ROOT.parent/'driver-research-2026-10-13/reports/STRATEGIE_PREUVES.json').read_text())
errors=[]
for item in system_snapshot['system_files']:
    if sha(Path(item['path']))!=item['sha256']:errors.append(item['path'])
assert len(system_snapshot['system_files'])==83 and not errors
programs=[]
for space in ['device','threadgroup']:
    for mode in ['native','nak']:
        path=OUT/(space+'-native-compiler/native.sass') if mode=='native' else COMP/space/'program.sass'
        listing=OUT/(space+'-'+mode+'-decode/execution.stdout')
        text=listing.read_text()
        programs.append({'space':space,'mode':mode,'code_path':str(path),'code_bytes':path.stat().st_size,
                         'sha256':sha(path),'decoder_unknown_instructions':text.count('[unknown instruction]'),
                         'decoder_unknown_annotations':text.count('[unknown'),'listing':str(listing)})
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'verification':{k:v for k,v in verification.items() if k!='results'},
         'AIR_NAK_cases_passed':4,'AIR_NAK_captures':12,
         'single_thread_single_group_only':True,'memory_order':'relaxed',
         'new_source_patch':'src/opennvda-air-cas-result.patch',
         'patch_effect':'Return previous i32 value, not bool, for observed AIR ABI; expected pointer receives the same atomic result.',
         'compiler_passes_added':['nir_lower_scratch_to_var','nir_lower_vars_to_ssa','lower_local_invocation_index'],
         'native_register_flow':flow,'programs':programs,'AIR_call_types':contracts,
         'system_files_rechecked':83,'system_hash_errors':errors,'installed_driver_repaired':False,
         'performance_benchmark':False,'full_hardware_goal_complete':False,
         'scope':'Same Apple-generated AIR executed natively and through corrected OpenNVDA/NAK; explicit app-local alternative. Narrow CAS qualification, not universal API or driver conformance.'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
inputs=[OUT/'results.json',OUT/'independent-verification.json',OUT/'manifest.json',COMP/'manifest.json',
        ROOT/'src/opennvda-air-cas-result.patch',ROOT/'tools/air_cas_compile.c',ROOT/'tools/prepare_cas_lowering.py',
        ROOT/'tools/air_cas_probe.mm',OUT/'reproduce_air_cas.py',ROOT/'tools/verify_air_cas.py',
        ROOT/'src/air_cas_carrier.metal',ROOT/'tools/make_air_cas_report.py',
        OUT/'air-type-contracts.json',OUT/'air_contract_probe.c']
provenance={'inputs':[{'path':str(p),'sha256':sha(p)} for p in inputs],
            'upstream_OpenNVDA_commit':'da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5',
            'upstream_Mesa_version':'26.2.4','upstream_Mesa_commit':'96cb43121031992b85767f9c1be8f3f48e22b1d2',
            'envytools_source_revision':'f102b82381f3f11cee113d16374c87091db039d9',
            'reference_revisions_are_not_local_patch_versions':True,
            'script_fingerprints_captured_after_execution':True}
(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
report='''CAS PARTAGÉ — MÊME AIR, CHEMIN NATIF ET CHEMIN NAK, 13 octobre 2026

Résultat: le CAS uint32 du shader Metal traduit automatiquement AIR→NIR→SM30
fonctionne sur la GTX 880M pour le cas minimal testé. Il rend correctement
expected, le booléen et la valeur finale, y compris après un échec de comparaison.
Cela étend la chaîne AIR expérimentale au-delà du précédent add_buffers;
les anciens fixtures CAS construits directement en NIR restent conservés.

Neuf configurations: huit correctes, un échec natif partagé conservé.
27 captures, 108 mots uint32 vérifiés indépendamment, trois mots incorrects
(expected dans le seul cas natif partagé miss), aucune garde corrompue.
Les quatre configurations AIR/NAK passent: global et partagé, comparaison
égale et différente, trois graines chacune. Un thread/un groupe, ordre relaxed.
Pas de contention ni de progression générale qualifiées dans cette série.
L’oracle autorise l’échec spurieux du weak-CAS sur comparaison égale.

Exemple commun, entrée GPU initialisée à 4660, comparaison 4661:
                expected    swapped    objet final
CPU requis         4660          0           4660
Metal natif shared 4661          0           4660  ÉCHEC
AIR/NAK shared     4660          0           4660  CORRECT
Global natif et AIR/NAK produisent aussi le résultat correct.
L’échec persiste sans boucle de retry et avec seulement quatre octets partagés.
Les trois jeux d’entrée sont réinitialisés et relus par blit synchronisé.

Correctifs locaux du chemin AIR
Le frontend OpenNVDA existant supposait que air.atomic.*.cmpxchg retournait
un booléen. L’AIR Apple observé retourne l’ancienne valeur i32 et la compare
ensuite à la comparaison initiale. Cette mauvaise largeur causait une assertion
NAK RegFile::GPR lors de l’encodage. La copie corrigée retourne old en i32 et
affecte expected depuis ce même résultat atomique. Aucune lecture séparée
après CAS ne masque l’erreur. Un retour i1 conserve l’ancien traitement, mais
ce retour n’est pas qualifié ici; les autres ABIs sont refusés.

Le temporaire next_expected est promu de scratch vers SSA et l’index local
est abaissé avant NAK. Les deux programmes finaux ont scratch=0 et CRS=0.
Ils utilisent l’ABI explicite 56 octets, quatre adresses de buffers, grille
et groupe, miroir en banque constante 2. Le carrier réserve 128 octets partagés
et produit une sentinelle native différente: son contrôle passe et ce résultat
ne peut pas être confondu avec l’exécution des programmes importés.

Programme AIR/NAK global: 448 octets, 46 instructions, 24 GPR déclarés.
Programme AIR/NAK partagé: 576 octets, 59 instructions, 4 octets partagés,
24 GPR déclarés. Contrat KPCreatePipeline audité, bytes importés identiques,
pilote existant responsable des ressources, commandes et synchronisations.
Tous les processus signés ont terminé, aucun timeout ni child vivant.

Localisation plus précise du défaut natif
Capture distincte de l’entrée du constructeur natif, sans dispatch dans
l’observateur; cela n’est pas un dump d’instructions GPU résidentes.
Dans ce shader partagé, le décodeur suit le comparand dans r0 et l’ancienne
valeur chargée par ld lock dans r4. La comparaison de succès utilise ces deux
registres, puis r4 devient l’adresse de sortie, tandis que st b128 écrit r0q.
La première composante conserve donc le comparand; aucun transfert de old
vers cette composante n’apparaît sur ce chemin. C’est cohérent avec chacun
des trois résultats numériques fautifs et désigne le code natif généré comme
le prochain point d’investigation. Les annotations de bits ld/st lock restent
incomplètes; on ne revendique pas une interprétation intégrale de l’ISA.
Les cinq offsets exacts, hashes et listings sont dans summary.json.

Capture native globale: 512 octets; partagée: 832 octets. La boucle 128 du
précédent fixture n’est donc pas nécessaire au défaut; son fort déroulement
reste un autre facteur à étudier. Taille et nombre de GPR ne donnent pas
une mesure de performance. Aucun benchmark et aucun gain annoncés ici.

État du projet et suite
Pas de correctif installé dans GeForceAIRPlugin/GeForceMTLDriver, pas de
nouvelle famille Metal. L’alternative reste explicitement appelée par notre
application (L1). Prochaines étapes: étendre ce même chemin à plusieurs lanes/
groupes et à la contention, puis concevoir une réparation du code natif dans
le seul processus du lab en préservant branches, barrières et scheduling.
Une modification globale du pilote/runtime reste hors de l’autorisation.
83 fichiers système inventoriés sont rehashés identiques; OCLP reste inchangé.
Le support de toutes les fonctionnalités matérielles n’est pas encore atteint.

Reproduction depuis le workspace, toujours avec un dossier de sortie inédit:
python3 nvidia-880m-lab/bridge/tools/prepare_cas_lowering.py --out nvidia-880m-lab/bridge/results/cas-lowering-reproduction
python3 nvidia-880m-lab/bridge/tools/reproduce_air_cas.py --input nvidia-880m-lab/bridge/results/cas-lowering-reproduction --out nvidia-880m-lab/bridge/results/air-cas-reproduction
python3 nvidia-880m-lab/bridge/tools/verify_air_cas.py --input nvidia-880m-lab/bridge/results/air-cas-reproduction
Le vérificateur retourne 1 tant que le défaut natif est présent; les quatre
cas AIR/NAK doivent passer. Ne pas convertir cet échec connu en succès.
Commandes exactes, sources, compilations, captures et échecs initiaux sont
conservés dans les dossiers cas-lowering-initial/corrected/final et air-cas-final.
Révisions exactes et fingerprints sont dans provenance.json et les manifests.
'''
(OUT/'RAPPORT.txt').write_text(report)
coverage_path=ROOT/'results/hardware-coverage.json'
coverage=json.loads(coverage_path.read_text())
entry={'category':'Apple AIR compare-exchange translated to SM30',
       'status':'sample_qualified_application_local',
       'tested_scope':'Same Apple AIR device/threadgroup uint32 weak CAS, equal/miss comparisons, one thread/group, relaxed order; corrected i32 return ABI and expected value, 12 NAK raw captures.',
       'remaining_requirements':'Multi-lane/group/contention/progression and broader ABI/order coverage; repair of native generated code and supported application integration. Installed native shared CAS remains defective.',
       'evidence':['results/air-cas-final/summary.json','results/air-cas-final/independent-verification.json',
                   'results/cas-lowering-final/manifest.json','src/opennvda-air-cas-result.patch']}
coverage['coverage']=[row for row in coverage['coverage'] if row['category']!=entry['category']]+[entry]
coverage['complete']=False
coverage_path.write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['native_register_flow','programs','verification']},indent=2))

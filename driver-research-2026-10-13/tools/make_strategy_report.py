#!/usr/bin/env python3
"""Reconcile the two research branches against existing evidence; never dispatch GPU work."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import plistlib
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT.parent
BRIDGE = LAB / 'bridge'
REPORTS = ROOT / 'reports'
AIR = BRIDGE / 'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/tools/nakc/air_nir.c'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def table(name, rows):
    dump(REPORTS / (name + '.json'), rows)
    with (REPORTS / (name + '.csv')).open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

summary = read(BRIDGE / 'results/native-features-report/summary.json')
source_manifest = read(ROOT / 'sources/strategy/manifest.json')
assert (summary['cases'], summary['cases_passed'], summary['cases_failed']) == (126, 98, 28)
assert summary['raw_runs_checked'] == 304 and summary['words_checked'] == 147736
assert summary['numeric_mismatches_in_preserved_failures'] == 571
assert not summary['performance_benchmark'] and not summary['guard_mismatches']

# Closed Linux/macOS cores prevent identifying equivalent or missing patches.
history = read(REPORTS / 'HISTORIQUE_KEPLER.json')
a = []
for i, old in enumerate(history):
    a.append({
        'id': f'A{i:02}', 'version': old['version'], 'date': old['date'],
        'evolution': old['changement'], 'composant': 'voir classification ci-dessous',
        'GK104': old['applicabilite_GK104'],
        'presence_macOS': 'Indéterminée pour la correction Linux; aucune équivalence de code établie.',
        'dependances': 'Noyau/ABI et pile graphique Linux, selon le composant.',
        'adaptation': old['transposition_macOS'],
        'nature_preuve': 'Comportement documenté; code propriétaire du correctif non disponible.',
        'preuve': old['source'] + ('; ancre ' + old['ancre_locale'] if old['ancre_locale'] else ''),
        'priorite': 'P3 — référence ou périmètre peu pertinent',
        'risque': 'Port direct non justifié; contrats macOS différents et régressions possibles.',
        'validation': 'Identifier un comportement macOS défectueux avant de concevoir un correctif.',
        'gain_attendu': 'Non mesuré; aucun gain macOS déduit du changelog Linux.',
    })

def update_a(i, **values):
    a[i].update(values)

for i in [0, 2, 3, 15]:
    update_a(i, composant='Identification/version/provenance', nature_preuve='Métadonnées et listes PCI observées; pas identité du code.',
             validation='Conserver les hashes et labels OCLP; ne pas apparier des versions par leur seul numéro.')
update_a(0, presence_macOS='Chaîne OpenCL 16.0.12 / 355.11.11.10.10.143 effectivement observée.')
update_a(2, presence_macOS='PCI 10de:1198 présent sur cette machine; exécution Linux R470 non testée.',
         GK104='880M listée dans la page NVIDIA legacy R470, mais omise des tables intégrées 450/470 examinées; contradiction documentaire.',
         preuve='sources/mobile-kepler-support-check.json; https://www.nvidia.com/en-us/drivers/unix/legacy-gpu/',
         validation='Aucune conclusion de rejet du binaire R470 sans essai Linux distinct; aucune installation ici.')
update_a(1, composant='Compilateur Vulkan SPIR-V / allocation', dependances='API Vulkan et bibliothèques ELF utilisateur fermées.',
         validation='Profiler la compilation/cache Metal existants; SPIR-V Linux ne remplace pas AIR/GeForceAIRPlugin.')
update_a(4, composant='Attente de fences / mémoire Vulkan', dependances='VkFence, types VkMemory, modèle cohérence CPU/GPU Vulkan.',
         priorite='P1 — diagnostic CPU/transferts, aucune correction pilote encore identifiée',
         validation='A1: mesurer CPU submit/wait, copies et synchronisation Metal, résultat identique; pas de supposition que le bug Vulkan existe sur Mac.',
         gain_attendu='Hypothèse: diminuer une attente active ou des transferts inutiles, seulement si observés.')
update_a(5, composant='Ordonnancement des copies Vulkan', dependances='Soumission Vulkan; implémentation des copies propriétaire.',
         priorite='P2 — contrôle ciblé de correction', validation='A1: chaîne blit→compute→blit avec sentinelles, modes tracked puis fences explicites qualifiées; oracle CPU.')
update_a(6, composant='Cache shaders OpenGL/Vulkan', dependances='Politique de cache utilisateur Linux, pas cache AIR identique.',
         validation='Séparer compilation froide/chaude du dispatch; comparer hashes et résultats, sans toucher au cache système.')
update_a(7, composant='VDPAU et transferts vidéo YCbCr', dependances='VDPAU Linux; équivalent macOS exige AppleGVA/VideoToolbox et ABI des surfaces.',
         presence_macOS='H.264 GPU refusé dans les tests; GeForceVA observé comme stub. Présence du correctif de transfert Linux indéterminée.',
         priorite='P2 — moteur GPU sous-utilisé, faisabilité transport à établir',
         preuve=history[7]['source'] + '; ../bridge/results/video-summary.json; sources/470-vdpau.html',
         validation='A2: retracer statiquement VA/AppleGVA et un payload historique référencé hors système; pas de transfert ELF ni nouveau test vidéo identique.')
update_a(8, composant='Gestion énergie / reprise Linux', dependances='Linux 5.10, runtime PM; pas IOKit power management.',
         validation='Documenter transitions IOKit déjà exposées; pas écriture registre/horloge ni manipulation de la veille.')
update_a(9, composant='Affichage / G-SYNC', dependances='VRR du moniteur et chemin affichage.',
         validation='Établir d’abord si le panneau interne prend en charge VRR; aucune pertinence calcul ou Metal déduite.')
update_a(10, composant='Extensions synchronisation / mémoire Vulkan', dependances='VK_KHR_synchronization2 et API/layouts Vulkan, support GK104 à vérifier.',
         validation='Définir le besoin de synchronisation Metal, plutôt que traduire le nom d’une extension en capacité Metal.')
update_a(11, composant='Compilateur/API OpenCL', GK104='L’annonce OpenCL 3.0 concernait Maxwell et plus récent; pas preuve Kepler.',
         presence_macOS='OpenCL 1.2 déclaré; compilation GPU bloquée par cl_kernel.nvptx64.pch absent.',
         preuve='sources/nvidia-opencl3.html; inventory/opencl-pch-status.json',
         validation='Étudier cohérence des payloads LLVM/NVPTX hors système; pas remplacer un PCH LLVM3.5 par un PCH d’une autre version.')
update_a(12, composant='Correction graphique explicitement Kepler', dependances='Chemin jeu/API et cœur NVIDIA fermés; cause publique non détaillée.',
         validation='Trouver un workload macOS donnant la même corruption avant hypothèse de correction homologue.')
update_a(13, composant='Gestion des contextes OpenGL', dependances='OpenGL, allocation des contextes et erreurs.',
         validation='Seulement si une limite de contextes est reproduite sous macOS; pas une nouvelle fonction Metal.')
for i in [14, 15, 19]:
    update_a(i, dependances='X11/Xwayland/PRIME/Wayland/simpledrm ou présentation Vulkan selon le changement.',
             risque='Port des interfaces Linux sans consommateur macOS; faible valeur pour cet iMac.')
update_a(16, composant='Reprise / allocations vkd3d-proton', dependances='Cycle Linux suspend/resume et workload vkd3d-proton.',
         validation='Ne pas induire d’erreur système pour tester; partir uniquement de symptômes macOS déjà observés.')
update_a(17, composant='Verrouillage / récupération RM', dependances='RM propriétaire; course multi-GPU hors configuration mono-GPU.',
         validation='Auditer les interfaces/verrous accessibles; aucun diagnostic de bug RM Mac et pas de fault injection GPU.')
update_a(18, composant='NvFBC / pression VRAM', dependances='Capture NvFBC et Vulkan Linux; pas WindowServer.',
         priorite='P2 — budget des ressources, test borné seulement',
         validation='A1: allocations propres plafonnées, erreurs contrôlées et ressources conservées; jamais remplir la VRAM globale.')
update_a(20, composant='Maintenance non détaillée', validation='Note trop vague pour identifier une amélioration transposable.')
update_a(21, composant='Sécurité du RM Linux', dependances='CVE et implémentation RM Linux, non diagnostiquées dans le pilote Mac.',
         validation='Étude de contrat et code accessible seulement; aucun exploit ni affirmation de vulnérabilité Mac.')
update_a(22, composant='GSP / NGX / RTD3', presence_macOS='Ne s’applique pas aux mécanismes matériels GK104.',
         adaptation='Exclu comme source de fonctionnalités natives pour GK104; composants d’autres générations.',
         validation='Vérifier les générations dans les documents NVIDIA; ne pas activer artificiellement des capacités.')
update_a(23, composant='Architecture CUDA / SM30', presence_macOS='Aucun runtime CUDA moderne qualifié ici.',
         adaptation='CUDA 11+ ne fournit pas une base SM30; Hyper-Q et dynamic parallelism GK110 ne sont pas GK104.',
         validation='Utiliser tableaux matériels/ISA SM30 et non l’étiquette Kepler seule.')
semantic_path=BRIDGE/'results/native-cas-semantic-qualification/independent-verification.json'
three_modes_path=BRIDGE/'results/submission-benchmark-three-modes/summary.json'
icb_methods_path=BRIDGE/'results/icb-contract-inspection/methods.json'
icb_noop_path=BRIDGE/'results/icb-contract-inspection/noop-verification.json'
icb_gpu_path=BRIDGE/'results/icb-gpu-encoding-pipeline/summary.json'
if semantic_path.exists():
    semantic=read(semantic_path)
    assert semantic['experiment_contract']=='PASS' and semantic['repaired_logical_CAS_operations']==8694
    a.append({'id':'A24','version':'Pile macOS actuelle, GeForceMTLDriver hash 2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054',
              'date':'2026-10-13','evolution':'Réparation ciblée du retour expected produit par le backend NVIDIA natif; distincte des évolutions Linux.',
              'composant':'Backend AIR → SM30 natif, puis payload shader dans le processus du lab.',
              'GK104':'Exécution correcte sur la GTX 880M pour quatre shaders au total; types/scopes supplémentaires non qualifiés.',
              'presence_macOS':'Défaut présent dans les programmes natifs testés; compilateur installé inchangé.',
              'dependances':'AIR sémantique, binaire natif, version pilote et ABI constructeur exactes; aucun noyau Linux.',
              'adaptation':'L1 opérationnel: filtre AIR + reconnaissance structurelle SASS + empreintes + trampoline. L2/L3 non déployés.',
              'nature_preuve':'AIR typé, captures du constructeur, différences binaires contrôlées, sorties GPU et oracle CPU indépendant.',
              'preuve':'../bridge/results/native-cas-summary.json; ../bridge/results/native-cas-semantic-qualification/independent-verification.json',
              'priorite':'P0 — généralisation conservatrice du correctif natif',
              'risque':'Collision SASS démontrée entre shader défectueux et shader valide; réparation SASS seule interdite. Autres erreurs Invalid Resource distinctes.',
              'validation':'Ancien shader: 21912 CAS corrects. Trois nouveaux: 8694 CAS corrects, 36 captures; 24 contrôles fautifs conservés, quatre refus avant pipeline.',
              'gain_attendu':'Justesse corrigée dans le périmètre qualifié. Aucun gain de débit CAS mesuré et aucune transposition Linux établie.'})
metallib_path=BRIDGE/'results/metallib-native-preservation/independent-verification.json'
indirect_compute_path=BRIDGE/'results/indirect-compute-native-qualified/independent-verification.json'
transport_symbols_path=BRIDGE/'results/indirect-transport-audit/symbol-resolution-rechecked/verification.json'
if metallib_path.exists():
    library_repair=read(metallib_path)
    assert library_repair['status']=='PASS' and library_repair['all_native_metadata_preserved']
    a[-1]['adaptation']+=' Nouveau chemin: extraction AIR indexée et HASH vérifiée depuis une metallib à quatre entrées; noms de kernels sélectionnés explicitement. Pas de source ou AIR externe requis.'
    a[-1]['validation']+=' Nouveau mode préservant les 232 octets de metadata d’origine: 12 configurations, 36 captures, 8694 CAS corrects, GPR7/8 et launch736/544 conservés.'
    a[-1]['risque']+=' Champs metadata liés à taille/instructions encore à auditer; liveness/alias/CFG restent limités. Planning depuis la metallib est un diagnostic, pas un déploiement automatique.'
    a[-1]['preuve']+='; ../bridge/results/metallib-native-preservation/independent-verification.json; ../bridge/results/native-cas-clobber-rejection/verification.json'
normalized_count_path=BRIDGE/'results/native-metadata-count-normalized/independent-verification.json'
native_launches_path=BRIDGE/'results/native-command-capture/launches-cb-size-corrected.json'
native_relocations_path=BRIDGE/'results/native-command-relocation-capture/independent-verification.json'
native_ownership_path=BRIDGE/'results/native-command-ownership/independent-verification.json'
native_descriptor_path=BRIDGE/'results/indirect-descriptor-gpu-readback/independent-verification.json'
native_replay_path=BRIDGE/'results/native-replay-mixed-gpu/independent-verification.json'
cpu_icb_path=BRIDGE/'results/cpu-icb-weak-gpu-qualified/independent-verification.json'
cpu_icb_lifetime_path=BRIDGE/'results/cpu-icb-lifetime-readback-gpu-qualified/independent-verification.json'
if normalized_count_path.exists():
    normalized_count=read(normalized_count_path)
    assert normalized_count['status']=='PASS' and normalized_count['correct_CAS_operations']==1782
    a[-1]['adaptation']+=' Metadata.word0 identifié comme instruction count du pipeline, normalisé après ajout de code selon convention qualifiée code_words-1; autres champs natifs conservés.'
    a[-1]['validation']+=' Six nouvelles configurations GPU,18captures,1782CAS corrects et champ décodé+44 concordant; usage complet hors reporting encore non inventorié.'
    a[-1]['preuve']+='; ../bridge/results/native-metadata-count-normalized/independent-verification.json; ../bridge/results/driver-runtime-layout/instruction-count-verification.json'
table('MODERNISATION_NVIDIA_ACTUALISEE', a)

base = read(REPORTS / 'MATRICE_METAL.json')
b = []
for i, old in enumerate(base):
    b.append({'id': f'B{i:02}', 'fonction': old['fonction'],
              'generation_intro': 'Non redatée sans preuve individuelle; le tableau Apple actuel décrit le support, pas la date d’introduction.',
              'SDK': 'À vérifier par fonction; présence SDK distincte du pilote.',
              'compilateur': 'Non qualifié pour l’ensemble de cette ligne.',
              'MTLDevice': old['exposition_actuelle'],
              'pipeline_execution_justesse': old['exposition_actuelle'],
              'classification': 'Indéterminé', 'capacite_GK104': old['capacite_GK104'],
              'modification_necessaire': old['travail_pile_macOS'],
              'couche_obstacle': 'À localiser',
              'integration': 'API système existante ou expérimentation L1; aucune nouvelle intégration transparente démontrée.',
              'preuve': old['preuve'], 'performance': 'Non mesurée pour cette fonction.',
              'priorite': old['priorite']})

def update_b(i, **values):
    b[i].update(values)

native = '../bridge/results/native-features-report/summary.json'
update_b(0, classification='Fonctionnel partiellement', SDK='Enums de familles présents dans SDK 26.2.',
         pipeline_execution_justesse='Mac1/Common1/2 annoncés; épreuves individuelles disponibles, aucune famille moderne complète qualifiée.',
         couche_obstacle='Contrat complet runtime/compilateur/pilote/matériel', performance='Aucun gain global Tahoe ou WindowServer démontré.')
update_b(1, classification='Indéterminé', generation_intro='Version MSL demandée distincte d’une fonction et d’une famille GPU.',
         compilateur='Addition simple compilée avec options 1.1..4.0; cela ne qualifie pas les fonctions de ces versions.',
         couche_obstacle='Frontend puis backend AIR puis exécution; qualification fonction par fonction.')
update_b(2, classification='Fonctionnel partiellement', pipeline_execution_justesse='Addition/GEMM et oracles CPU sur tailles et entrées documentées; pas conformité arithmétique/application complète.',
         couche_obstacle='Couverture numérique/compilateur et performance', integration='API native et imports NAK L1 selon le kernel; aucun pilote nouveau.')
update_b(3, classification='Fonctionnel partiellement', pipeline_execution_justesse='288 cas de base conservés: 48Kio, groupes jusqu’à 1024 threads, phases/permutations et barrières; limites exactes dans shared-units-summary.',
         couche_obstacle='Extensions du contrat de synchronisation non qualifiées',
         preuve='../bridge/results/shared-units-summary.json; ../bridge/MEMOIRE_PARTAGEE.txt',
         performance='64 groupes/batch64: natif 0.372482ms, NAK 0.747540ms; ratio apparié 2.008; durée murale incluant readback.')
update_b(4, classification='Déclaré mais défectueux', generation_intro='MSL spec p305: overload CAS volatile depuis Metal1; non volatile depuis Metal2. Pas nouveauté Metal3/4.',
         SDK='metal_atomic installé fournit API device et threadgroup.',
         compilateur='Compile offline/runtime et crée les pipelines minimaux actuels.',
         MTLDevice='Pas de booléen de propriété établissant la conformité CAS.',
         pipeline_execution_justesse='CAS global14/14; partagé4/14, dix échecs expected (571 mots); compteurs/booléens corrects. Completed dans ces dix échecs. Ancien Invalid Resource distinct.',
         capacite_GK104='CAS NAK partagé précédemment correct; mécanisme matériel réalisable dans le périmètre testé.',
         modification_necessaire='Localiser et corriger la restitution de expected; pas atomic_load ultérieur non linéarisable.',
         couche_obstacle='Chemin de compilation/exécution natif partagé; responsabilité exacte non isolée.',
         integration='NAK CAS L1 correct sur fixtures; CAS natif partagé défectueux pour les apps standard.',
         preuve='../bridge/results/native-features-report/DIAGNOSTIC_CAS.txt; '+native,
         priorite='P0 — défaut réel et minimal')
update_b(5, classification='Non exposé mais matériellement réalisable',
         pipeline_execution_justesse='ADD/EXCH/CAS globaux uint64 NAK qualifiés sur72cas; pas atomic64 MSL natif qualifié.',
         couche_obstacle='Frontend et ABI/types/ordres atomiques', integration='L1 import explicite; pas support MSL généralisé.')
update_b(6, classification='Fonctionnel partiellement',
         generation_intro='MSL spec p219 et p222: simd_shuffle macOS Metal2; simd_sum macOS Metal2.1. Ne pas attribuer ces opérations à Metal3.',
         compilateur='Shuffle/xor passent; neuf opérations réduction/vote échouent aux pipelines offline et runtime (18 échecs).',
         MTLDevice='Ne pas inférer ces intrinsics depuis Mac1 ou la seule taille de warp.',
         pipeline_execution_justesse='8 contrôles/shuffles natifs corrects; 54 configurations helper/162 captures passent; all-lanes convergentes, warp32, groupes1/31/32/33/63/128.',
         capacite_GK104='Shuffles physiques fonctionnels; réductions et votes convergents réalisables par composition, divergence générale non qualifiée.',
         modification_necessaire='Réutiliser lowerings AIR→NIR existants après validation ABI, ou helper source explicite; ne pas recréer le frontend.',
         couche_obstacle='Compilateur natif pour intrinsics; sémantiques divergence/FP et intégration app.',
         integration='Shuffles: API native. KeplerSIMD.metalh: helper applicatif L1, interface source utilisable explicitement; pas extension système L3.',
         preuve=native+'; ../bridge/src/KeplerSIMD.metalh; OpenNVDA tools/nakc/air_nir.c:2073-2096',
         priorite='P1 — extension app/compiler crédible')
update_b(7, classification='Déjà fonctionnel', generation_intro='Argument encoder macOS10.13/iOS11 (période Metal2); ne pas dater tout tier2 depuis un enum.',
         SDK='MTLArgumentEncoder.h; tier1=0/tier2=1 dans MTLDevice.h.',
         compilateur='Tableaux de buffers/textures/samplers et producteur GPU acceptés dans les shaders éprouvés.',
         MTLDevice='argumentBuffersSupport brut1 = tier2.',
         pipeline_execution_justesse='8configs/24captures/18432mots corrects: arrays4/32buffers,32texturesR32Float,2samplers, références réécrites GPU puis consommées dans un autre encodeur.',
         capacite_GK104='Indirection de ressources démontrée pour ces tailles/formats.',
         modification_necessaire='Aucun ajout pilote pour ces cas; qualifier durées de vie/useResource puis mesurer coût CPU des bindings.',
         couche_obstacle='Couverture additionnelle et utilisation par apps; pas absence de tier2.',
         integration='API système native déjà accessible aux applications; les tests ne prouvent pas toute la conformité tier2.',
         preuve=native+'; ../bridge/results/native-features-arguments-expanded/independent-verification.json',
         priorite='P1 — exploitation d’existant, pas nouvelle API')
update_b(8, classification='Fonctionnel partiellement', pipeline_execution_justesse='Formats sélectionnés SULD/SUST testés via NAK; propriété tier1, tier2 non. Pas qualification MSL générale read_write.', couche_obstacle='Formats/ABI texture et contrat read_write')
update_b(9, classification='Déjà fonctionnel', pipeline_execution_justesse='Arguments draw indirect GPU utilisés dans fixtures; pas validation des objets ICB.', couche_obstacle='Couverture des cas hors fixtures')
update_b(10, generation_intro='SDK: ICB rendu macOS10.14/iOS12; ICB compute concurrent macOS11/iOS13.',
         SDK='MTLIndirectCommandBuffer.h présent; disponibilité dépend aussi des propriétés MTLDevice.',
         pipeline_execution_justesse='Création, encodage et exécution ICB non qualifiés; indirect simple distinct.',
         couche_obstacle='Runtime/pilote commandes et residency/hazards', priorite='P1 — sonde progressive avant conception')
update_b(11, generation_intro='SDK: heaps/fences macOS10.13; placement heaps macOS10.15; events macOS10.14; residency sets macOS15, avant Metal4.',
         SDK='MTLHeap/MTLFence/MTLEvent/MTLResidencySet présents.',
         pipeline_execution_justesse='Factories, aliasing/lifetime, fences inter-encodeurs et events inter-queues non qualifiés dans les preuves examinées.',
         couche_obstacle='Runtime/gestion ressources/pilote, pas génération SASS seule', priorite='P1 — qualifier ce qui existe')
update_b(12, couche_obstacle='Dispatch runtime et métadonnées de groupes', modification_necessaire='Sonde dispatchThreads non uniforme avec garde et oracle; ne pas confondre grille multidimensionnelle uniforme et groupes incomplets.')
update_b(13, classification='Fonctionnel partiellement', pipeline_execution_justesse='Triangles, facteurs0..64, coordonnées et stage d’évaluation NAK qualifiés; limites raster haute densité conservées, pas quads généralisés.', couche_obstacle='Couverture du tessellateur/ABI et cas limites')
update_b(14, classification='Fonctionnel partiellement', pipeline_execution_justesse='Rendu, MRT2/4/8, MSAA2/4/8 resolve et états depth/stencil sur fixtures; 16x non.', couche_obstacle='Conformité formats/états hors épreuves')
for i in [15,16,17,18,19,20,21,22,23,25,26]:
    update_b(i, couche_obstacle='Contrats matériels et runtime/compilateur/pilote à traiter séparément; pas déduit d’un simple sélecteur.')
update_b(19, modification_necessaire='Relocations, tables de fonctions, métadonnées et durée de vie des programmes; capacité de branchement SASS ne fournit pas une bibliothèque dynamique Metal.')
update_b(20, modification_necessaire='Pas de chemin matériel mesh moderne dédié qualifié; émulation compute→rendu envisageable mais pas support natif automatique de l’API mesh.')
update_b(21, capacite_GK104='Pas de RT cores; ray tracing logiciel compute possible en principe, contrat Metal acceleration structures/intersection non implémenté.', modification_necessaire='Implémentation logicielle et runtime complet si poursuivis; aucun gain natif RT attendu sans mesure.')
update_b(22, capacite_GK104='GPU discret immédiat; aucune équivalence avec la mémoire de tuile Apple qualifiée.', modification_necessaire='Émulation éventuelle distincte d’une capacité matérielle native; priorité faible.')
update_b(23, pipeline_execution_justesse='Conversion/stockage FP16 observés; SIMD matrices/BF16/tensors non qualifiés. Absence Tensor cores ne signifie pas impossibilité de calcul matriciel FP32.', couche_obstacle='Types et ABI/layouts; contrats API tensor et compilateur; moteurs dédiés absents.')
update_b(24, classification='Non exposé mais matériellement réalisable', pipeline_execution_justesse='DADD NAK correct sur1041doubles; MSL double natif non qualifié; OpenCL annonce fp64 mais compilation GPU bloquée.', couche_obstacle='Frontend/types/ABI, couverture FP64, throughput', integration='L1 kernel expérimental; pas prise en charge générale MSL double.')
update_b(25, generation_intro='MTL4CommandQueue/Allocator/ArgumentTable: SDK macOS26/iOS26, Metal4 WWDC2025.',
         SDK='ObjC dans SDK26.2; metal-cpp '+source_manifest['metal_cpp_commit']+' est un wrapper de messages ObjC.',
         compilateur='Shader simple compilé ne qualifie pas les nouveaux objets ni commandes.',
         MTLDevice='Famille Metal4 false; selector queue présent, factory nil.',
         pipeline_execution_justesse='Aucune queue MTL4 créée, aucun flux de commandes MTL4 exécuté.',
         modification_necessaire='Nouveaux objets/runtime, encodage/allocateurs, résidence/ressources, barrières, métadonnées et contrats du pilote; NAK seul insuffisant.',
         couche_obstacle='Runtime/framework et pilote: premier blocage observé avant shader/GPU.',
         integration='Aucun L1 MTL4 fonctionnel; aucune extension L2/L3. Support officiel Apple M1+/A14+, pas Kepler.',
         preuve='inventory/capabilities.json; sources/strategy/manifest.json; sources/strategy/sdk-MTL4CommandQueue.h; https://developer.apple.com/videos/play/wwdc2025/205/',
         priorite='P3 — recherche de contrats, pas première implémentation')
update_b(27, classification='Fonctionnel partiellement', pipeline_execution_justesse='CPU H.264 fonctionne; encode/decode GPU imposé refusé, VA stub; voie matérielle non raccordée.', couche_obstacle='VA/AppleGVA/VideoToolbox/pilote vidéo; branche A hors ajout Metal.', integration='Aucune accélération vidéo GPU supplémentaire démontrée.')
update_b(28, classification='Fonctionnel partiellement', couche_obstacle='Pile affichage/WindowServer et gestion énergie; tests app locaux insuffisants.', performance='Aucune amélioration système mesurée; aucun correctif global.')
update_b(29, performance='Deux kernels instrumentés shared, NAK/natif ratios appariés2.008 et3.143 (64groupes,batch64). Pas GPU-time/occupation qualifiés ni gain général.',
         pipeline_execution_justesse='216échantillons,209952groupes GPU terminés vérifiés; oracles corrects pour ces kernels.',
         classification='Indéterminé', couche_obstacle='Mesure workload et CPU/transferts vs kernels; pas chiffre d’occupation sans mesure.',
         preuve='../bridge/COMPARAISON_METAL_NAK.txt; ../bridge/results/shared-benchmark-summary.json')
air_cas_path=BRIDGE/'results/air-cas-final/summary.json'
if air_cas_path.exists():
    air_cas=read(air_cas_path)
    assert air_cas['AIR_NAK_cases_passed']==4 and not air_cas['installed_driver_repaired']
    b[4]['pipeline_execution_justesse']+=' Nouveau test sans retry: même AIR global/shared traduit via NAK correct sur4configurations/12captures; native shared miss conserve expected incorrect (3graines).'
    b[4]['compilateur']+=' Frontend AIR local corrigé: retourne old i32; promotion scratch→SSA et index local abaissé.'
    b[4]['couche_obstacle']='Dans le shader minimal natif capturé, old est en r4 mais la sortie conserve le comparand r0; transfert manquant cohérent avec les résultats. Bits lock partiellement décodés; pas réparation native appliquée.'
    b[4]['preuve']+='; ../bridge/results/air-cas-final/summary.json; ../bridge/results/air-cas-final/RAPPORT.txt'
progress_path=BRIDGE/'results/current-progress/summary.json'
if progress_path.exists():
    progress=read(progress_path)
    native_repair=progress['native_CAS'];resources=progress['native_resources'];submission=progress['submission_benchmark']
    assert native_repair['repaired_configurations']==10 and not native_repair['installed_driver_repaired']
    b[4]['pipeline_execution_justesse']+=' Correction du shader natif exact dans le processus:10configurations/30captures/21912CAS corrects, jusqu’à1024threads/groupe; contrôles original et NOP conservent le défaut.'
    b[4]['couche_obstacle']='Omission old→expected du code natif corrigée par trampoline strictement hashé. Le backend système reste défectueux pour les applications non adaptées; autres shaders/ABI non qualifiés.'
    b[4]['integration']='L1: réparation d’un shader exact, aucun correctif compilateur/pilote système ni prise en charge CAS générale. AIR/NAK multi-lanes:24configurations/13896opérations correctes.'
    b[4]['preuve']+='; ../bridge/results/native-cas-summary.json; ../bridge/results/current-progress/RAPPORT.txt; ../bridge/results/air-cas-extended/independent-verification.json'
    icb_index=next(i for i,row in enumerate(b) if row['id']=='B10')
    update_b(icb_index, classification='Indéterminé', MTLDevice='Les factories rendu/calcul échouent: NVMTLDevice ne fournit pas newIndirectCommandBufferWithDescriptor:maxCount:options:.',
             pipeline_execution_justesse='Deux exceptions de factory capturées; aucun ICB créé, aucun dispatch. Pas une preuve d’incapacité physique GK104.',
             couche_obstacle='Méthode absente dans la pile runtime/pilote actuelle, avant pipeline ou instructions GPU.',
             preuve='../bridge/results/resource-sync-initial/results.json; ../bridge/results/resource-sync-summary.json')
    heap_index=next(i for i,row in enumerate(b) if row['id']=='B11')
    update_b(heap_index, classification='Fonctionnel partiellement', MTLDevice='NVMTLHeap et fences créés; Event/SharedEvent sont _MTLSharedEvent.',
             pipeline_execution_justesse='Heaps et réallocation après makeAliasable, fences Untracked et dépendances event inter-queues corrects sur les samples;202782mots positifs corrects,33797mots faux dans contrôle sans producteur; aucune garde corrompue.',
             couche_obstacle='Fonctions natives déjà utilisables; placement/résidence et stress de lifetime/concurrence non qualifiés. Backend matériel/CPU de l’event non identifié.',
             integration='API native actuelle appelée par une app standard; aucune extension de famille Metal requise pour ces samples.',
             preuve='../bridge/results/resource-sync-summary.json; ../bridge/results/resource-sync-initial/independent-verification.json; ../bridge/results/resource-sync-alias/independent-verification.json')
    b[29]['performance']+=' Regroupement applicatif natif mesuré: boucle 10.379→3.063 ms, CPU processus 10.083→1.003 ms médianes, trois échauffements et neuf paires; 1536 dispatchs comptés au total, dont 384 échauffements et 1152 mesurés. Temps GPU exclusif et gain pilote/global non établis.'
    b[29]['preuve']+='; ../bridge/results/submission-benchmark-counted/summary.json'
if semantic_path.exists():
    b[4]['pipeline_execution_justesse']+=' Trois nouveaux shaders natifs réparés: 12 configurations, 36 captures, 8694 CAS corrects sous contention. Ancien + nouveaux: quatre shaders, 22 configurations, 66 captures, 30606 CAS corrects.'
    b[4]['compilateur']+=' Les programmes défectueux et un témoin valide ont un SASS identique; leur AIR distingue l’intention. Filtre sémantique et pins exacts obligatoires.'
    b[4]['couche_obstacle']='Branche A24: code produit par le backend NVIDIA natif. Transfert old→expected adapté après reconnaissance AIR/SASS; pilote installé reste défectueux. Autres Invalid Resource non résolus.'
    b[4]['integration']='L1: quatre shaders qualifiés; nouvelles coordonnées découvertes, jamais substitution universelle r0/r4. Application standard sans intégration encore non corrigée.'
    b[4]['preuve']+='; ../bridge/results/native-cas-semantic-qualification/independent-verification.json'
if three_modes_path.exists():
    b[29]['performance']+=' Nouvel essai dans une même exécution: wait_each / submit32_wait_end / batch32, médianes murales 11.446 / 4.038 / 3.439 ms et CPU processus 9.109 / 6.755 / 1.181 ms. Trois échauffements et neuf triplets; 2304 dispatchs au total, dont 576 échauffements et 1728 mesurés. Optimisation applicative distincte des branches A/B.'
    b[29]['preuve']+='; ../bridge/results/submission-benchmark-three-modes/summary.json'
if icb_noop_path.exists() and icb_gpu_path.exists():
    noop=read(icb_noop_path);gpu_icb=read(icb_gpu_path)
    assert sum(r['six_byte_noop'] for r in noop['checks'])==5
    assert gpu_icb['frontend']=='PASS' and gpu_icb['native_pipeline']=='BLOCKED' and not gpu_icb['GPU_dispatch']
    b[10]['pipeline_execution_justesse']='Factories rendu/calcul refusées. Cinq méthodes compute/blit héritées sont des no-ops de six octets. MSL 2.4 accepte un kernel encodant un render_command, puis backend natif refuse air.command_buffer. Aucun ICB créé ou exécuté.'
    b[10]['couche_obstacle']='Trois contrats distincts manquent: factory/runtime, encodage/exécution (no-ops), et pour génération GPU compilation/layout des arguments air.command_buffer.'
    b[10]['preuve']+='; ../bridge/results/icb-contract-inspection/noop-verification.json; ../bridge/results/icb-gpu-encoding-pipeline/summary.json'
    cpu=dict(b[10]);cpu.update(id='B10C',fonction='ICB encodés par le CPU — rendu/calcul, réutilisation et exécution',
        compilateur='N’impose pas de shader qui génère des commandes. Pipelines ordinaires natifs déjà disponibles dans les fixtures.',
        pipeline_execution_justesse='BLOCKED: factory interne absente pour rendu/calcul. Compute execute(range/indirect range), blit reset/copy/optimize hérités sont vides; rendu execution non inspectée séparément.',
        capacite_GK104='Draw/dispatch indirect simple déjà exécutés; capacité à consommer un vrai objet ICB natif reste à établir.',
        modification_necessaire='Implémenter objet/commandes, états hérités/locaux, rétention des ressources et résidence, reset/copie/réutilisation/ranges, raccordement effectif au command stream NVIDIA.',
        integration='L1 banc futur. L2 et L3 exigent contrats compatibles; un rejeu CPU d’API directes ne constitue pas une preuve d’ICB matériel.')
    generated=dict(b[10]);generated.update(id='B10G',fonction='ICB générés par un kernel GPU — cible distincte',
        compilateur='Frontend MSL 2.4 PASS; création du pipeline natif BLOCKED: Unsupported indirect argument kind air.command_buffer.',
        pipeline_execution_justesse='Aucun dispatch ni ICB réel. Le refus se produit avant le constructeur de programme observé.',
        capacite_GK104='Écritures mémoire et arguments indirects réalisables sur les cas existants; format et exécution ICB générés par le GPU non qualifiés.',
        modification_necessaire='Tout le contrat B10C, plus ressource ICB dans argument buffer, layout et ABI du command_buffer, lowering render_command/compute_command, cohérence et résidence des commandes générées.',
        integration='Non implémenté; un compilateur alternatif seul ne répare ni la factory ni les encodeurs no-op.')
    b.extend([cpu,generated])
if metallib_path.exists():
    b[4]['compilateur']+=' Extraction du module AIR réel de la metallib, par nom et HASH vérifiée, sans sidecar source. Reconnaissance de liveness renforcée contre clobber de old.'
    b[4]['pipeline_execution_justesse']+=' Même profil de trois shapes qualifié depuis une bibliothèque à quatre fonctions avec metadata native intégralement préservée: 8694 opérations correctes supplémentaires, pas nouvelles familles CAS.'
    b[4]['preuve']+='; ../bridge/results/metallib-native-preservation/independent-verification.json'
if indirect_compute_path.exists():
    actual_indirect=read(indirect_compute_path)
    assert actual_indirect['status']=='PASS' and actual_indirect['consumer_invocations_counted']==11580
    b[9]['pipeline_execution_justesse']+=' Dispatch indirect compute avec arguments Private écrits sur GPU: neuf formes local32/33/128 et groups1/3/5, trois graines; géométrie, résultats et compteurs concordent avec direct. Six contrôles sans producteur conservés, 41688 mots positifs corrects.'
    b[9]['preuve']+='; ../bridge/results/indirect-compute-native-qualified/independent-verification.json'
if transport_symbols_path.exists():
    for row in b:
        if row['id'] in ['B10','B10C','B10G']:
            row['couche_obstacle']+=' Rendu ICB hérité: 0xced53/0xced68 forwardent à doesNotRecognizeSelector:, vérifié par chaînes dyld et symboles. Primitives indirectes NVIDIA véritables distinctes, contexte/paquets privés non encore réutilisés.'
            row['preuve']+='; ../bridge/results/indirect-transport-audit/symbol-resolution-rechecked/verification.json'
        if row['id']=='B10C':
            row['pipeline_execution_justesse']='BLOCKED: factory maxCount absente; compute execute et blit sont no-op; render execute est un chemin doesNotRecognizeSelector:. Indirect simple natif fonctionnel, aucun objet ICB ajouté.'
if normalized_count_path.exists():
    b[4]['compilateur']+=' Word0 metadata, source du compteur d’instructions rapporté, recalculé après extension; GPR/launch/LDS restants inchangés.'
    b[4]['preuve']+='; ../bridge/results/native-metadata-count-normalized/independent-verification.json'
if native_launches_path.exists():
    for row in b:
        if row['id'] in ['B10','B10C','B10G']:
            row['couche_obstacle']+=' Flux natif capturé sans submission: direct464B/9paquets, indirect1052B/21paquets; deux descriptors/lancements dans indirect (helper puis utilisateur). Bindings/offsets changent les templates; résidence/lifetime/réutilisation non qualifiées.'
            row['preuve']+='; ../bridge/results/native-command-capture/launches.json; ../bridge/results/native-command-relocation-capture/independent-verification.json'
if native_ownership_path.exists() and native_descriptor_path.exists():
    ownership=read(native_ownership_path);descriptor=read(native_descriptor_path)
    assert ownership['status']==descriptor['status']=='PASS' and descriptor['consumer_invocations']==4917
    for row in b:
        if row['id'] in ['B10','B10C','B10G']:
            row['couche_obstacle']+=' Backings QMD4096B/CB393216B reliés aux buffers internes de la file; retainedReferences privé qualifié avec contrôle unretained jamais soumis. GPU indirect:12exécutions montrent24mots QMD et108mots builtin constants changés exactement;4917invocations,17736valeurs positives correctes. Persistance/résidence/réutilisation/ICB restent non implémentées.'
            row['preuve']+='; ../bridge/results/native-command-ownership/independent-verification.json; ../bridge/results/indirect-descriptor-gpu-readback/independent-verification.json; ../bridge/results/native-command-capture/launches-cb-size-corrected.json'
if native_replay_path.exists():
    replay=read(native_replay_path)
    assert replay['status']=='PASS' and replay['replayed_consumer_invocations']==9054 and not replay['ICB_implemented']
    for row in b:
        if row['id'] in ['B10','B10C','B10G']:
            row['couche_obstacle']+=' Nouveau prototype L1: paquets natifs persistants, CB/QMD dédiés et bindings indépendants; séquence mixte de trois géométries,9054invocations vérifiées, une préparation native retirée avant commit. Command words recopiés CPU vers PushBuffer; aucun ICB GPU-résident/public, nouveau shader/compiler ou intégration transparente.'
            row['preuve']+='; ../bridge/results/native-replay-mixed-gpu/independent-verification.json; ../bridge/src/KeplerNativeCommands.mm; ../bridge/REJEU_NATIF_PERSISTANT.txt'
if cpu_icb_path.exists() and cpu_icb_lifetime_path.exists():
    cpu_icb=read(cpu_icb_path);cpu_life=read(cpu_icb_lifetime_path)
    assert cpu_icb['status']==cpu_life['status']=='PASS'
    assert cpu_icb['user_GPU_invocations']==4396 and cpu_life['GPU_user_invocations']==198
    assert not cpu_icb['ICB_contract_complete'] and not cpu_life['ICB_contract_complete']
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-weak-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-lifetime-readback-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_NATIF.txt'
        row['couche_obstacle']='Pile installée hors scope: factory absente, compute/blit no-op et rendu refusé; génération GPU refusée par air.command_buffer. Scope local expérimental: objets/états CPU et paquets natifs calcul fonctionnels, command words copiés CPU. Format ICB GPU-résident, autres pipelines/états, rendu, ranges indirects/blits timeline et intégration L2/L3 restent manquants.'
        if row['id'] in ['B10','B10C']:
            row['classification']='Fonctionnel partiellement — sous-ensemble CPU calcul expérimental L1'
            row['MTLDevice']='Factory publique fournie uniquement sur notre objet device par une sous-classe scoped sans ivar; classe originale restaurée. Pile installée inchangée, aucun drapeau de capacité falsifié.'
            row['pipeline_execution_justesse']='PASS historique borné: sept soumissions GPU de la première qualification,4396invocations et17584uint32; plages/réutilisation/reset/copie CPU/rebinding. Deux essais de lifetime après libération ICB/scope:198invocations,792uint32; contrôle unretained jamais soumis. Gardes intactes; un seul pipeline natif consume_grid, trois buffers et encoder série.'
            row['capacite_GK104']='Dispatchs natifs des commandes enregistrées réellement exécutés. Aucune indirection vers un buffer de commandes GPU-résident ni génération GPU ICB démontrée.'
            row['modification_necessaire']='Compléter la qualification des pipelines/bindings et états hérités, threadgroup memory/grilles, rendu, ranges indirects et reset/copy/optimize timeline; format/résidence ICB GPU et génération/compiler séparés. Qualifier concurrence, mémoire sous pression et performances.'
            row['integration']='L1: deux clients de laboratoire appellent explicitement le scope. Pas de contrat ICB complet ni support transparent L2/L3; metadata GPU utilisée pour propriétés/ownership, pas comme layout de commandes GPU.'
            row['priorite']='P1 — élargir le contrat CPU qualifié avant génération GPU séparée'
profile_path=BRIDGE/'results/cpu-icb-profiles-gpu-qualified/independent-verification.json'
profile_life_path=BRIDGE/'results/cpu-icb-profiles-lifetime-gpu-qualified/independent-verification.json'
if profile_path.exists() and profile_life_path.exists():
    profiles=read(profile_path);profile_life=read(profile_life_path)
    assert profiles['status']==profile_life['status']=='PASS'
    assert profiles['user_GPU_invocations']==4725 and profile_life['GPU_user_invocations']==594
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-profiles-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-profiles-lifetime-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_PIPELINES_NATIFS.txt'
        row['couche_obstacle']+=' Extension bornée: bibliothèque vérifiée913c4c1a, trois PSO créés/possédés par le scope, reflection ABI, métadonnées QMD conservées et caches de sous-classes réutilisés. Code des shaders NVIDIA natifs inchangé. Toute généralisation du contrat reste ouverte.'
        if row['id'] in ['B10','B10C']:
            row['pipeline_execution_justesse']='PASS multi-pipelines natifs borné: huit soumissions,4725invocations/18900uint32; entier, float FMA à résultats exacts,512B de shared avec barrière, local32/33/128; changements de programme, plages/reset/copie CPU/réutilisation/rebinding. Deux soumissions distinctes après libération ICB/scope/pipelines applicatifs:594invocations/2376uint32, gardes intactes. Sept contrôles API et négatif unretained jamais soumis; captures réelles de paquets et oracles indépendants.'
            row['modification_necessaire']='Enregistrement général des bibliothèques/ABI/metadata, héritage d’états, mémoire partagée dynamique, grilles non uniformes, rendu, ranges indirects/blits timeline; format ICB GPU-résident et génération/compiler séparés. Caches de sous-classes validés sur trois réinstallations; concurrence/pression/performance et intégration L2/L3 non qualifiées.'
manifest_path=BRIDGE/'results/cpu-icb-manifest-resize-gpu-qualified/independent-verification.json'
manifest_life_path=BRIDGE/'results/cpu-icb-manifest-lifetime-gpu-qualified/independent-verification.json'
manifest_regression_path=BRIDGE/'results/cpu-icb-manifest-regression-profiles-gpu-qualified/independent-verification.json'
if manifest_path.exists() and manifest_life_path.exists() and manifest_regression_path.exists():
    current_manifest=read(manifest_path);manifest_life=read(manifest_life_path);manifest_regression=read(manifest_regression_path)
    assert current_manifest['status']==manifest_life['status']==manifest_regression['status']=='PASS'
    assert current_manifest['user_GPU_invocations']==5496 and manifest_life['GPU_user_invocations']==594 and manifest_regression['user_GPU_invocations']==4725
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-manifest-resize-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-manifest-lifetime-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_MANIFESTE_MEMOIRE_DYNAMIQUE.txt'
        row['couche_obstacle']+=' Chemin générique sans noms imposés: manifeste et library SHA vérifiés, réflexion et identités PSO; trois buffers et facultatif threadgroup0. Enregistrer n’est pas qualifier le calcul. Formats natifs464B/496B préservés; autres ABI/états/rendu/GPU-resident restent ouverts.'
        if row['id'] in ['B10','B10C']:
            row['pipeline_execution_justesse']='PASS manifest/shared dynamique borné: neuf soumissions,5496invocations/21984uint32; allocation1/32/48Kio et resize même commande1→48Kio, plages/reset/copie/reuse/rebinding. Deux soumissions après releaseICB/scope594/2376;13contrôles, bornes cached/copied refusées avant submission, gardes intactes. Non-régression des trois anciens programmes4725/18900. Pas de benchmark, shaders natifs inchangés.'
            row['modification_necessaire']='Étendre l’ABI buffers/offsets et les états/héritages; combinaison static+dynamic/autres pointeurs, grilles2D/3D/nonuniformes, rendu, ranges indirects/blits timeline. Layout ICB GPU-résident/génération, concurrence/pression/performance et intégration L2/L3 restent manquants.'
buffers_path=BRIDGE/'results/cpu-icb-buffers-range-gpu-qualified/independent-verification.json'
buffers_life_path=BRIDGE/'results/cpu-icb-buffers-lifetime-gpu-qualified/independent-verification.json'
buffers_dynamic_path=BRIDGE/'results/cpu-icb-buffers-dynamic-regression-gpu-qualified/independent-verification.json'
buffers_legacy_path=BRIDGE/'results/cpu-icb-buffers-legacy-regression-gpu-qualified/independent-verification.json'
if all(p.exists() for p in [buffers_path,buffers_life_path,buffers_dynamic_path,buffers_legacy_path]):
    buffers=read(buffers_path);buffers_life=read(buffers_life_path)
    assert buffers['status']==buffers_life['status']=='PASS' and buffers['correct_float32_values']==919040 and buffers_life['correct_float32_values']==65536
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-buffers-range-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-buffers-lifetime-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_BUFFERS_IMPORT_IMMUABLE.txt'
        row['couche_obstacle']+=' Loader charge le snapshot SHA directement depuis la mémoire, copie mutable détruite/source temporaire supprimée. Schema2 quatre buffers AXPY/offsets/dimensions plus générales; autres ABI/états/rendu/GPU-resident non complets.'
        if row['id'] in ['B10','B10C']:
            row['pipeline_execution_justesse']='PASS buffers4 natifs:128/8192/65536float4 par commande,229760vecteurs/919040float32 sur quatre CB; offsets sortie128/256, A64/128,B256/512,constant3 256/512, inputs/gardes conservés. Lifetime deux CB16384/65536 après releaseICB/scope. Lib chargée depuis bytes immuables, pas nouvelle lecture URL après SHA. Range trop petit/align/index/grid refusés. Shared dynamique et trois anciens programmes régressionPASS. Aucun gain mesuré.'
            row['modification_necessaire']='Étendre les autres espaces/types/index de ressources, argument buffers/textures/multi-constant, états hérités et grilles2D/3D/nonuniformes; rendu, ranges/timeline, format/génération GPU, concurrence/pression/performance et intégration L2/L3 restent manquants.'
grid3d_path=BRIDGE/'results/cpu-icb-grid3d-gpu-qualified/independent-verification.json'
grid3d_buffers_path=BRIDGE/'results/cpu-icb-grid3d-buffer-regression-gpu-qualified/independent-verification.json'
grid3d_shared_path=BRIDGE/'results/cpu-icb-grid3d-dynamic-regression-gpu-qualified/independent-verification.json'
if all(p.exists() for p in [grid3d_path,grid3d_buffers_path,grid3d_shared_path]):
    grid3d=read(grid3d_path);grid3d_buffers=read(grid3d_buffers_path);grid3d_shared=read(grid3d_shared_path)
    assert all(x['status']=='PASS' for x in [grid3d,grid3d_buffers,grid3d_shared])
    assert grid3d['GPU_invocations_counted']==18632 and grid3d['correct_uint32_words']==149056
    assert grid3d_buffers['correct_float32_values']==919040 and grid3d_shared['user_GPU_invocations']==5496
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-grid3d-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_GRILLES_2D_3D.txt'
        row['couche_obstacle']+=' Sous-ensemble CPU calcul: géométrie uniformeXYZ et builtins natifs préservés; aucun ajout de capacité physique ou de génération GPU ICB.'
        if row['id'] in ['B10','B10C']:
            row['pipeline_execution_justesse']='PASS grilles2D/3D natifs L1:sept CB (six non vides/28dispatchs),18632invocations comptées et149056uint32 corrects; local1024threads/Z64, géométrie/lane/groupe/grid. Reshape, copie après reset source, ranges et source vide; quatre refus de dimensions. Sources actuelles régressionAXPY919040float32 et shared1/32/48Kio5496/21984 PASS. Pas de benchmark.'
            row['modification_necessaire']='Rendu et contrat des commandes/resources; autres ABI/types/indices, argument buffers/textures/multi-constant, états hérités, grilles non uniformes, shared combiné, timeline. Format ICB GPU-résident/génération, concurrence/pression/performance et L2/L3 restent ouverts.'
render_transport_path=BRIDGE/'results/native-render-replay-gpu-qualified/independent-verification.json'
if render_transport_path.exists():
    render_transport=read(render_transport_path)
    assert render_transport['status']=='PASS' and render_transport['correct_replay_float32_channels']==86016
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/native-render-replay-gpu-qualified/independent-verification.json; ../bridge/REJEU_RENDU_NATIF.txt'
        row['couche_obstacle']+=' Fondation rendu native L1: paquets de dessin direct/indexé/scissor rejoués avec PSO natif, Private indices16/32 et leases. Pas encore raccordée aux objets/sélecteurs ICB de rendu; slotsMME propres au pilote, pas noms Nouveau attribués.'
        if row['id'] in ['B10','B10C']:
            row['pipeline_execution_justesse']+=' Transport rendu distinct: huit CB/98304float32 (86016rejeu); retraits sélectif/total, index16/32 dégénérés sur GPU et caller-release PASS. Paramètreinstances2 transporté, comptage d’instances non qualifié. Module calcul précédent inchangé.'
            row['modification_necessaire']='Raccorder ce transport aux MTLIndirectRenderCommand et à executeCommandsInBuffer dans un scope propre, avec l’état de l’encodeur conforme au contrat; ne pas inventer un setter ICB scissor. Puis pipeline/états/bindings/ranges/timeline, ICB GPU-résident/génération, concurrence/pression/benchmark et L2/L3.'
public_render_path=BRIDGE/'results/cpu-icb-render-gpu-qualified/independent-verification.json'
public_render_life_path=BRIDGE/'results/cpu-icb-render-lifetime-gpu-qualified/independent-verification.json'
if public_render_path.exists() and public_render_life_path.exists():
    public_render=read(public_render_path);public_render_life=read(public_render_life_path)
    assert public_render['status']==public_render_life['status']=='PASS' and public_render['correct_float32_channels']==135168 and public_render_life['correct_float32_channels']==12288
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-render-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-render-lifetime-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_RENDU_PUBLIC.txt'
        row['couche_obstacle']+=' Dans le scope L1 seulement: factory et objetsCPU ICB rendu reliés aux sélecteurs publics, scissor de l’encodeur conservé/pipeline client rétabli. Pile installée inchangée. Un profil bufferless/pass fixe, pas d’ICB GPU-résident/génération.'
        if row['id'] in ['B10','B10C']:
            row['classification']='Fonctionnel partiellement — CPU calcul et rendu en scope expérimental L1'
            row['pipeline_execution_justesse']='Latest CPU render ICB:11CB135168float32, scissorA/B/C hérité et shader rouge natif aprèsICB correct; ranges/index16/32Private dégénérés, reset/copies/overlap. Une autre soumission après release scope/ICB, classes restaurées avant commit:12288float32. Sept refus. Sources communes régression3D18632/149056,shared5496/21984,ancienrejeu86016float32. Calcul qualifié précédemment; aucun benchmark.'
            row['modification_necessaire']='Étendre pipeline/bindings/état/geometry de rendu, scope ICB calcul+rendu simultané, timeline/rangesindirects; format ICB GPU-résident/génération, conformance/concurrence/pression/performance et L2/L3. Profil rendu actuel triangles3vertices/bufferless/64x48RGBA32F, état scissor hérité.'
mixed_scope_path=BRIDGE/'results/cpu-icb-mixed-gpu-qualified/independent-verification.json'
if mixed_scope_path.exists():
    mixed_scope=read(mixed_scope_path);assert mixed_scope['status']=='PASS' and mixed_scope['GPU_compute_invocations_counted']==192 and mixed_scope['correct_float32_channels']==110592
    for row in b:
        if row['id'] not in ['B10','B10C','B10G']:continue
        row['preuve']+='; ../bridge/results/cpu-icb-mixed-gpu-qualified/independent-verification.json; ../bridge/CPU_ICB_CALCUL_RENDU.txt'
        row['couche_obstacle']+=' DomainesICB calcul/rendu coexistent maintenant sur le même scope/device/file. Un shader calcul natif produit les indicesPrivate consommés par rendu dans le mêmeCB, aucune lectureCPU des indices entre étapes. Pas de générationGPU d’ICB.'
        if row['id'] in ['B10','B10C']:
            row['pipeline_execution_justesse']='Latest scope mixte L1:9CB,192invocations calcul comptées,110592float32/535pixels corrects; producer/consumer supprimés, indices dégénérés, copies de chaque domaine puis reset source. NativeQMD7GPR/binding0 identique à SET_INDEX_BUFFER. Régressions3D18632/149056,render135168,shared5496/21984 PASS. Pas de benchmark.'
            row['modification_necessaire']='Généraliser les PSO/bindings/états/geometry de rendu et les profils de calcul; timeline/rangesindirects, formatICBGPU-résident/génération, conformance/pression/concurrence/performance et L2/L3 restent ouverts. Synchronisation de cette chaîne sérielle qualifiée seulement dans les cas testés.'
table('METAL_CAPACITES_ACTUALISEES', b)

experiments = [
    {'id':'B1','branche':'B','priorite':0,'but':'Localiser le défaut expected du CAS partagé natif.',
     'reutiliser':'Fixture miss global/partagé, metal_atomic hashé, captures constructeur, air_nir.c cmpxchg et import ABI auditée.',
     'travail':'Réduire la capture à un CAS sans boucle; comparer AIR global/partagé avant backend et stores de expected après backend. Compiler ce même AIR via le frontend existant avec harness généralisé et carrier ABI vérifié, puis un seul dispatch borné si imports valides.',
     'criteres':'Expected=4660 sur miss (comparand4661), bool=false et objet inchangé; mêmes données/oracle. Sous contention, retours attendus linéarisables. Pas de lecture séparée pour masquer le défaut.',
     'decision':'AIR correct mais code natif erroné localise le backend; AIR déjà incorrect localise frontend/wrapper; décodage incomplet reste indéterminé. NAK correct sur ce même AIR prouve un chemin alternatif L1, pas une réparation système.',
     'risques_limites':'Ne pas tirer de conclusion ISA depuis les bits non décodés; ne pas appliquer de correctif système.'},
    {'id':'A1','branche':'A','priorite':1,'but':'Trouver une limitation matérielle/pilote macOS mesurable dans soumission, mémoire ou transferts.',
     'reutiliser':'Profil natif existant, buffers Private/Managed/Shared et oracles; notes455 fences et copies, budgets ressources.',
     'travail':'Charge identique: mesurer séparément encoding/submit CPU, attente CPU, durée murale compute, H→GPU/GPU→H et readback; comparer lots et ressources persistantes. Allocations propres strictement plafonnées, aucune pression VRAM globale.',
     'criteres':'3échauffements minimum,9essais alternés par cas; résultats/guards corrects; médiane/IQR et CPU ms; mêmes données et travail GPU. Signaler bruit et temps GPU non qualifié.',
     'decision':'Bottleneck app/bindings => optimisation app identifiée, pas modernisation pilote. Dysfonctionnement pilote reproductible => contrat/interface précise à auditer avant correctif A.',
     'risques_limites':'Pas de gain déduit de VkFence Linux. Pas de modification clocks/énergie/reset ni allocation jusqu’à OOM système.'},
    {'id':'B2','branche':'B','priorite':1,'but':'Qualifier les objets de ressources/commandes déjà potentiellement fournis avant ajout d’API.',
     'reutiliser':'SDKheaders et fixtures indirect simple/tier2; pilote natif.',
     'travail':'Sonde par étapes indépendantes: propriété→factory heap/fence/event puis ICB rendu et compute→pipeline→dispatch contrôlé. Tester aliasing/lifetime et chaîne producteur-consommateur avec guards; arrêter chaque chemin refusé et garder erreur.',
     'criteres':'Objets réellement créés et commandes exécutées avec oracle. Pas conclure ICB à partir du draw indirect, ni event à partir d’un sélecteur.',
     'decision':'Déjà fonctionnel => exploiter API existante; factory refusée => frontière runtime/pilote. Ne pas réimplémenter arbitrairement Metal4.',
     'risques_limites':'Fences/signals bornés, processus propres signés, délai<=60s, vérifier fin effective du child avant autre dispatch.'},
    {'id':'B3','branche':'B','priorite':1,'but':'Transformer le SIMD limité en interface utilisable explicitement par une application (L2).',
     'reutiliser':'KeplerSIMD.metalh,54cases réussis, shuffles natifs; lowerings OpenNVDA déjà présents.',
     'travail':'Ajouter seulement couverture manquante: signed/overflow définis, FP négatifs/cancellation/NaN/Inf selon contrat explicite; préciser sémantiques actives et interdire divergence non prise en charge. Mesurer contre réduction MSL partagée équivalente; puis tester un vrai shader/app adapté. AIR automatique reste candidat après B1 et qualification ABI.',
     'criteres':'Résultats corrects selon référence numérique justifiée, documentation de convergence, application cliente distincte; benchmark identique/warmups/répétitions et coûts transferts.',
     'decision':'L2 seulement si une application adaptée fonctionne. Pas L3, pas nouvelle famille, pas remplacement universel des intrinsics divergents.',
     'risques_limites':'Un helper correct sur entrées dyadiques ne fournit pas toute la conformité FP/divergence.'},
    {'id':'A2','branche':'A','priorite':2,'but':'Déterminer le raccordement manquant du moteur vidéo H.264.',
     'reutiliser':'Refus GPU précédents, contrôles CPU et GeForceVA stub; archivesLinux/VDPAU existantes.',
     'travail':'Analyse statique des entrées VA/AppleGVA, profils/surfaces et payloads historiques déjà disponibles; identifier l’interface réellement absente. Ne pas relancer les mêmes sondes refusées.',
     'criteres':'Carte des interfaces et provenance d’un composant candidat hors système, dépendances/ABI documentées; exécution GPU reste non prouvée tant qu’il n’existe pas de transport fonctionnel.',
     'decision':'Transport réutilisable précis => concevoir prototype non déployé; cœur fermé/ABI non résolu => blocage ciblé. VDPAU/ELF ne se charge pas comme pilote macOS.',
     'risques_limites':'Aucun remplacement VA système, chargement kext, nouvelle tentative sur anciens processus bloqués.'},
]
if air_cas_path.exists():
    experiments[0]['etat']='Premier résultat acquis: même AIR corrigé exécuté sur GPU; qualification minimale, native CAS non réparé.'
    experiments[0]['preuves_acquises']='../bridge/results/air-cas-final/summary.json; quatre cas AIR/NAK et douze captures correctes; omission de transfert old→expected dans le listing natif minimal.'
    experiments[0]['travail']='Étendre le même AIR à plusieurs lanes/groupes et contention. Concevoir ensuite une réparation de payload natif dans le seul processus du lab, en conservant comparaisons, barrières, branches et scheduling; ne pas refaire le diagnostic single-CAS déjà acquis.'
if progress_path.exists():
    experiments[0]['etat']='Jalon natif acquis: shader exact réparé dans le processus;10configurations/30captures/21912CAS. Même AIR/NAK qualifié multi-lanes. Pilote système non corrigé.'
    experiments[0]['preuves_acquises']='../bridge/results/native-cas-summary.json; ../bridge/results/air-cas-extended/independent-verification.json'
    experiments[0]['travail']='Qualifier reconnaissance de shaders/ABI supplémentaires et intégration applicative supportée, sans appliquer le trampoline à un code différent ni modifier le système.'
    experiments[1]['etat']='Coût applicatif mesuré: batching32 réduit CPU/soumission sur microbenchmark contrôlé; pas une modernisation NVIDIA.'
    experiments[1]['preuves_acquises']='../bridge/results/submission-benchmark-counted/summary.json; compteur1536dispatchs et768traces d’étape,3warmups+9paires.'
    experiments[1]['travail']='Intégrer le regroupement applicable dans une vraie application adaptée puis mesurer son workload complet. Conserver distinction coûts CPU, transferts et temps GPU exclusif.'
    experiments[2]['etat']='Heaps, alias capacity reuse, fences Untracked, event/shared-event inter-queues passent. ICB rendu/calcul bloqués par méthode absente de NVMTLDevice.'
    experiments[2]['preuves_acquises']='../bridge/results/resource-sync-summary.json;202782mots positifs corrects; contrôles et exceptions conservés.'
    experiments[2]['travail']='Qualifier placement et lifetime/concurrence manquants; auditer le contrat runtime/pilote ICB absent. Réutiliser les fonctions natives déjà correctes.'
if semantic_path.exists():
    experiments[0].update(id='A3',branche='A',but='Généraliser conservativement la correction du code produit par le backend NVIDIA natif.',
        etat='Quatre shaders natifs qualifiés en L1; trois nouveaux shapes, 8694 CAS corrects. Collision SASS valide/défectueux démontrée.',
        preuves_acquises='../bridge/results/native-cas-semantic-qualification/independent-verification.json; ../bridge/results/native-cas-summary.json',
        travail='Extraire/associer l’AIR exact des metallibs candidats, qualifier d’autres flux/types et rejeux/lifetimes dans le seul processus. Refuser une intention ambiguë ou un driver/ABI différent. Construire une intégration L2 seulement après ces garde-fous.',
        criteres='Empreintes et flux AIR/SASS cohérents, témoins d’intention opposée rejetés, oracles complets sous contention, version du pilote verrouillée. Toute généralisation non qualifiée est refusée.',
        decision='Correction native classée A, sans la présenter comme un port Linux. Transparent L3 reste l’ambition, aucun déploiement système autorisé.')
if three_modes_path.exists():
    experiments[1].update(id='APP1',branche='Applicatif',etat='Trois modes mesurés dans un même run; résultats et compteur identiques, 1728 dispatchs mesurés hors échauffements.',
        preuves_acquises='../bridge/results/submission-benchmark-three-modes/summary.json',
        travail='Réutiliser ce résultat lorsque l’intégration applicative pertinente existe. Pas de nouvelle soumission pilote ou gain global déduit du microbenchmark.')
if icb_noop_path.exists() and icb_gpu_path.exists():
    experiments[2].update(but='Définir puis raccorder les contrats ICB CPU et GPU séparément.',
        etat='Runtime factory manquante, cinq no-ops compute/blit, backend rejette air.command_buffer; trois obstacles logiciels localisés.',
        preuves_acquises='../bridge/results/icb-contract-inspection/noop-verification.json; ../bridge/results/icb-gpu-encoding-pipeline/summary.json',
        travail='Tracer statiquement les primitives NVIDIA d’indirect simple déjà fonctionnelles et les contrats de ressources/commandes. Définir un sous-ensemble CPU ICB compatible, avec reset/réutilisation/résidence. Génération GPU exige en plus layout et lowering; pas retour d’objet factice ni capability spoof.',
        criteres='Un objet réel, commandes réutilisées et compteurs/résultats GPU comparés à un dispatch direct; CPU encoding et GPU generation rapportés séparément. Aucun remplacement de framework système.')
if metallib_path.exists():
    experiments[0]['etat']+=' Nouveau mode metallib: AIR exact extrait, metadata native7/8GPR et736/544 conservée;8694CAS supplémentaires corrects.'
    experiments[0]['travail']='Auditer metadata liées à taille/instructions et liveness/CFG/alias restantes, puis interface du correcteur pour un client L2 distinct. Conserver la séparation diagnostic candidat / qualification GPU / intégration.'
if indirect_compute_path.exists():
    experiments[2]['etat']+=' Primitives compute indirect qualifiées: dimensions produites sur GPU, géométrie et compteurs corrects. Rendu ICB hérité réellement refusé.'
    experiments[2]['travail']='Inspecter en lecture seule le command stream émis dans le processus, identifier adresses/ressources à conserver ou relocaliser, contrat de réutilisation et ABI du contexte NVIDIA. Construire ensuite un vrai ICB CPU, puis génération GPU avec lowering command_buffer.'
if normalized_count_path.exists():
    experiments[0]['etat']+=' Metadata instruction count normalisé,1782CAS supplémentaires corrects, autres champs natifs inchangés.'
    experiments[0]['travail']='Inventorier usages metadata restants et contrôler contraintes d’ABI/CFG/alias, puis intégrer le correcteur normalisé dans un client L2 distinct. L3 reste non réalisé.'
if native_launches_path.exists():
    experiments[2]['etat']+=' Douze captures native command stream en lecture seule, descriptors/parser et restauration byte-exact contrôlés, aucun replay.'
    experiments[2]['travail']='Relier CB/QMD aux allocations et propriétaires, qualifier rétention/résidence/réallocation et fixups d’adresse. Ensuite représentation native réutilisable avant création de vrais ICB CPU/GPU; pas de rejeu CPU présenté comme support matériel.'
if native_ownership_path.exists() and native_descriptor_path.exists():
    experiments[2]['etat']+=' Backings identifiés et rétention privée bornée; relectureGPU des QMD et constantes builtin confirme les modifications du chemin indirect natif.'
    experiments[2]['travail']='Construire une représentation native persistante avec ressources/pipelines fortement retenus et backings dédiés; qualifier bindings/constantes builtin et réutilisation. Ensuite client ICB explicite L1; ni rejeu d’appels CPU présenté comme ICB matériel, ni intégration L3 déclarée.'
if native_replay_path.exists():
    experiments[2]['etat']+=' Rejeu de paquets natifs avec backings dédiés et séquence mixed-resources fonctionnel en L1;9054invocations exactes et suppressions sélectives/totales validées.'
    experiments[2]['travail']='Raccorder des objets CPU ICB réels: commandes/states, mutation/reset/copie/ranges et ownership; qualifier indirection GPU-résidente et autres shaders, puis génération GPU/compiler séparément. Mesurer coût CPU/copies. Ne pas présenter le prototype comme API disponible ou L3.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/native-replay-mixed-gpu/independent-verification.json; ../bridge/results/native-replay-progress/summary.json'
if cpu_icb_path.exists() and cpu_icb_lifetime_path.exists():
    experiments[2]['etat']='Première qualification du sous-ensemble CPU calcul public-selector en scope L1; sept CB/4396invocations,17584uint32. Lifetime après release ICB/scope qualifié sur deux CB/198invocations,792uint32; unretained négatif non soumis. Aucun ICB complet/render/GPU-résident ou génération GPU.'
    experiments[2]['travail']='Qualifier identité et métadonnées d’autres pipelines/bindings, états hérités/threadgroup mémoire/ranges, classes réutilisables et concurrence; compléter render et opérations timeline. Format GPU-résident et génération/compiler distincts. Mesurer coût CPU, copies et matérialisation; intégration L2/L3 reste à établir.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-weak-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-lifetime-readback-gpu-qualified/independent-verification.json'
if profile_path.exists() and profile_life_path.exists():
    experiments[2]['etat']='Trois pipelines natifs possédés par le scope, bibliothèque et reflection épinglées,4725invocations/18900uint32; entier/FMA/shared512B+barrière avec changements de programme. Lifetime distinct après release ICB/scope:594invocations/2376uint32. Caches réutilisés trois cycles; contrôles API et unretained non soumis. Contrat complet/GPU-résident/génération/rendu ouverts.'
    experiments[2]['travail']='Généraliser conservativement l’enregistrement de bibliothèques/fonctions/ABI et métadonnées, puis états CPU/hérités et mémoire partagée dynamique/grilles; qualifier concurrence et pression bornée. Rendu, opérations timeline et format ICB GPU/génération séparés. Benchmark CPU/copie/matérialisation et client adapté L2, sans gain ni transparence L3 anticipés.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-profiles-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-profiles-lifetime-gpu-qualified/independent-verification.json'
if manifest_path.exists() and manifest_life_path.exists() and manifest_regression_path.exists():
    experiments[2]['etat']='Enregistrement natif par manifeste/reflection sans noms imposés, trois buffers et threadgroup0. Shared dynamique1/32/48Kio, resize/reuse/copie et bornes cached/copied;5496/21984, lifetime594/2376, ancienne bibliothèque régression4725/18900. Contrat ICB complet/L2/L3 et GPU-résident/généré/rendu restent ouverts.'
    experiments[2]['travail']='Figer le contenu de library à l’import pour les clients généraux; étendre ABI/bindings/offsets et héritages, état shared combiné et grilles; puis rendu et format/génération GPU séparés. Vérifier concurrence/pression bornée et mesurer CPU/copie/matérialisation. Bibliothèque enregistrée seule ne vaut jamais qualification GPU.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-manifest-resize-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-manifest-lifetime-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-manifest-regression-profiles-gpu-qualified/independent-verification.json'
if all(p.exists() for p in [buffers_path,buffers_life_path,buffers_dynamic_path,buffers_legacy_path]):
    experiments[2]['etat']='Import immuable directement par bytes et schema2 buffers. AXPY4,128/8192/65536vecteurs,919040float32; lifetime65536 supplémentaires après release. Shared/anciennes bibliothèques régressionPASS. ICB complet/rendu/GPU-resident/génération/L2/L3 restent ouverts.'
    experiments[2]['travail']='Étendre les états et les grilles2D/3D, puis représentation/transport rendu CPU ICB; espaces de ressources supplémentaires et argument-buffer/texture/multi-constant. Concurrence et pression bornée, benchmark séparé; aucune substitution des améliorations driver A par optimisation d’application.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-buffers-range-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-buffers-lifetime-gpu-qualified/independent-verification.json'
if all(p.exists() for p in [grid3d_path,grid3d_buffers_path,grid3d_shared_path]):
    experiments[2]['etat']='Grilles uniformes2D/3D CPU ICB L1 qualifiées:18632invocations/149056uint32, local1024/Z64, reshape/copie/reset/ranges. RégressionsAXPY919040float32 et shared1/32/48Kio5496/21984 PASS. Contrat complet/rendu/GPU-résident/génération/L2/L3 ouverts.'
    experiments[2]['travail']='Capturer en lecture seule le contrat du contexte et des commandes rendu natif, avant extension CPU ICB rendu bornée. Poursuivre autres espaces de ressources/états/nonuniformes, timeline et indirection/générationGPU distinctes. Concurrence/pression/benchmark séparés; ne pas présenter une qualificationL1 comme modernisation globale.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-grid3d-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-grid3d-progress/summary.json'
if render_transport_path.exists():
    experiments[2]['etat']='Transport rendu natif L1 qualifié:98304float32,86016rejeu; Private indices16/32 à données modifiées sur GPU, retrait sélectif/total et leases après release. Les objets/API CPU ICB rendu restent non implémentés; ICB calcul qualifié précédemment et inchangé.'
    experiments[2]['travail']='Intégrer le transport aux objets CPU ICB rendu et aux sélecteurs publics dans le scope propre, en respectant l’état hérité de l’encodeur (le SDK ne fournit pas de setter ICB scissor). Étendre pipeline/bindings/états/ranges, puis indirection/générationGPU séparées. Benchmark distinct, pas d’intégration L3 déclarée.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/native-render-replay-gpu-qualified/independent-verification.json; ../bridge/results/native-render-replay-progress/summary.json'
if public_render_path.exists() and public_render_life_path.exists():
    experiments[2]['etat']='Sous-ensemble CPU ICB rendu aux sélecteurs publics qualifié L1:135168+12288float32, scissor hérité/pipeline client rétabli, reset/copie/overlap/lifetime. Régressions calcul et raw-rendu PASS. Contrat complet/GPU-résident/génération/L2/L3 non établis.'
    experiments[2]['travail']='Généraliser réellement les bibliothèques/PSO/bindings de rendu, puis scope mixte calcul+rendu et état/geometry; conserver la sémantique d’héritage. Étendre timeline/rangesindirects et format/générationGPU séparés. Mesurer avant gain; intégration L2/L3 reste distincte.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-render-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-render-lifetime-gpu-qualified/independent-verification.json'
if mixed_scope_path.exists():
    experiments[2]['etat']='Scope ICB mixte et chaîne GPU compute→indexPrivate→render qualifiésL1,192/110592,contrôlesabsence/degénérescence/copies/reset PASS. Calcul et rendu ne sont plus mutuellement exclusifs; contratcomplet/GPU-résident/génération/L2/L3 ouverts.'
    experiments[2]['travail']='Généraliser l’enregistrement natif PSO/bindings de rendu depuis les fixtures vertexIO existantes, puis état/geometry/timeline. Qualifier hazard/residency/lifecycle sous pression et concurrence; benchmark séparé, générationGPUICB distincte.'
    experiments[2]['preuves_acquises']+='; ../bridge/results/cpu-icb-mixed-gpu-qualified/independent-verification.json; ../bridge/results/cpu-icb-mixed-progress/summary.json'
dump(REPORTS / 'EXPERIMENTATIONS_PRIORISEES.json', experiments)

components = read(ROOT / 'inventory/components.json')
compiler_files = read(ROOT / 'inventory/compiler-payload-files.json')
checked = []
errors = []
for component in components:
    for path_key, hash_key in [('info_path','info_sha256'),('executable','sha256')]:
        if component.get(path_key) and component.get(hash_key):
            path=Path(component[path_key]); actual=sha(path)
            checked.append({'path':str(path),'sha256':actual})
            if actual != component[hash_key]: errors.append(str(path))
for item in compiler_files:
    path=Path(item['path']); actual=sha(path)
    checked.append({'path':str(path),'sha256':actual})
    if actual != item['sha256']: errors.append(str(path))
inventory=read(ROOT / 'inventory/inventory-manifest.json')
root_patch=Path(inventory['root_patch_plist'])
if sha(root_patch)!=inventory['root_patch_plist_sha256']: errors.append(str(root_patch))
assert len(checked)==83 and not errors, (len(checked),errors)
assert 'mem_store(c, eas, expp, old, 4)' in AIR.read_text()
assert 'simd_sum' in AIR.read_text() and 'simd_ballot' in AIR.read_text()

inputs=[REPORTS/'HISTORIQUE_KEPLER.json',REPORTS/'MATRICE_METAL.json',
        BRIDGE/'results/native-features-report/summary.json',
        BRIDGE/'results/native-features-report/DIAGNOSTIC_CAS.txt',
        BRIDGE/'results/import-audit-summary.json',BRIDGE/'results/shared-units-summary.json',
        BRIDGE/'results/shared-benchmark-summary.json',BRIDGE/'AUDIT_PONT_NAK.txt',
        BRIDGE/'tools/kepler_air_compile.c',BRIDGE/'src/KeplerProgramImport.h',
        BRIDGE/'src/KeplerSIMD.metalh',AIR,ROOT/'sources/strategy/manifest.json',
        ROOT/'sources/strategy/msl-evidence.json',Path(__file__).resolve(),
        ROOT/'tools/refresh_strategy_sources.py',ROOT/'tools/extract_strategy_msl.py']
if air_cas_path.exists():
    inputs += [air_cas_path,BRIDGE/'results/air-cas-final/independent-verification.json',
               BRIDGE/'src/opennvda-air-cas-result.patch']
if progress_path.exists():
    inputs += [progress_path,BRIDGE/'results/current-progress/provenance.json',BRIDGE/'results/native-cas-summary.json',
               BRIDGE/'results/resource-sync-summary.json',BRIDGE/'results/submission-benchmark-counted/summary.json']
for path in [semantic_path,three_modes_path,icb_methods_path,icb_noop_path,icb_gpu_path,metallib_path,indirect_compute_path,transport_symbols_path,normalized_count_path,native_launches_path,native_relocations_path,native_ownership_path,native_descriptor_path]:
    if path.exists():inputs.append(path)
if native_replay_path.exists():inputs.append(native_replay_path)
for path in [cpu_icb_path,cpu_icb_lifetime_path,profile_path,profile_life_path,manifest_path,manifest_life_path,manifest_regression_path,buffers_path,buffers_life_path,buffers_dynamic_path,buffers_legacy_path,grid3d_path,grid3d_buffers_path,grid3d_shared_path,render_transport_path,public_render_path,public_render_life_path,mixed_scope_path]:
    if path.exists():inputs.append(path)
proof={'captured_at':datetime.now(timezone.utc).isoformat(),
       'macOS':subprocess.check_output(['sw_vers'],text=True).strip(),
       'hardware':subprocess.check_output(['sysctl','hw.model','hw.memsize','hw.physicalcpu','hw.logicalcpu','machdep.cpu.brand_string'],text=True).strip(),
       'rootpatch':plistlib.loads(root_patch.read_bytes()),'rootpatch_sha256':sha(root_patch),
       'system_files_checked':len(checked),'system_hash_errors':errors,'system_files':checked,
       'inputs':[{'path':str(p),'sha256':sha(p)} for p in inputs],
       'git_status':subprocess.check_output(['git','status','--short'],cwd=LAB.parent,text=True),
       'new_GPU_experiments':0,'system_modifications':False,
       'scope':'Evidence reconciliation and static/source audit. Prior GPU results reused; no new performance or hardware conformance claim.'}
dump(REPORTS/'STRATEGIE_PREUVES.json',proof)

text=f'''KEPLERMETAL — ÉTAT ET TRAJECTOIRE À PARTIR DES PREUVES, 13 octobre 2026

Décision: conserver les deux branches et leur séparation. Priorité B: localiser
le CAS partagé natif incorrect, puis rendre les fonctions SIMD manquantes
utilisables explicitement. Priorité A: mesurer la soumission/attente/transferts
avant de choisir une modification du pilote. Aucun nouveau pilote construit
ou déployé; aucune nouvelle famille Metal qualifiée. Le projet global reste
inachevé, mais ses frontières et prochains résultats sont maintenant précis.

1. Ce que le prompt conserve et ce qu’il faut corriger

À conserver: workspace existant, preuves numériques, branche A indépendante
de B, niveaux L1/L2/L3, conservation du pilote natif lorsqu’il fonctionne,
mesures avant gain et système sans modification. Le frontend et les interfaces
d’import existants servent de base; pas besoin d’une nouvelle architecture.

À corriger: tier2 n’est plus seulement annoncé. Huit configurations natives,
24 captures et 18432 mots valident les tableaux buffers/textures/samplers et
la réécriture des références par GPU suivie de consommation. Cela réutilise
une capacité du pilote déjà installé, pas une extension nouvellement créée.

SIMD: shuffle et xor natifs fonctionnent. Réductions/votes échouent à la
création des pipelines sur neuf opérations, deux modes de compilation.
Le helper convergent KeplerSIMD passe54configurations/162captures; pas
divergence arbitraire, ni NaN/Inf/arrondi général qualifiés, ni benchmark.

CAS: global14/14configurations correctes; partagé4/14. Dix échecs numériques
isolent expected inchangé après comparaison ratée (571mots incorrects).
Exemple objet4660/comparand4661: false et objet correct, expected4661 au lieu
de4660. Les commandes terminent normalement. L’ancien Invalid Resource reste
un échec distinct. Le NAK CAS validé prouve que ce mécanisme est réalisable
sur le matériel, sans localiser encore le défaut du chemin natif.

Qualification récente:126configurations,98succès,28échecs conservés
(18pipelines SIMD,10résultats CAS),304captures et147736mots,aucune garde
incorrecte. Elle s’ajoute à la base précédente; ce total n’est pas un nouvel
inventaire de toutes les expériences ni une conformité Metal complète.

2. Configuration et intégrité

macOS26.7.1 build25G241 reconfirmé; iMac11,1/i7-870/32GiB et880M8GiB,
PCI10de:1198/SM30. Rootpatch déclare OCLPv3.0.0/support2.0.1, lienRC2;
ne pas confondre ce lien de release avec un commit prouvé de l’app installée.
Payload mixte BigSur/Monterey et frameworks ultérieurs: les numéros Apple
16.0.0/16.0.12/16.0.14 ne correspondent pas à un code Linux identique.
83fichiers système inventoriés et plist rootpatch rehashés ici: inchangés.
SHA GeForceMTLDriver:
2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054
Le reste des capacités est réutilisé de l’inventaire du même13octobre, avec
hashes système identiques; aucune nouvelle sonde GPU lancée pour ce rapport.
Git: lab et opencl-880m sont encore non suivis. Les archives/manifests donnent
des snapshots vérifiables, pas un historique Git des modifications du projet.

3. Branche A: recherche achevée, modernisation du pilote non implémentée

Cinq archives355.11/418.113/450.57/470.63.01/470.256.02 extraites existent;
aucun téléchargement de ces pilotes ni exécution de leur installateur refait.
Le dernier répertoireR470 de l’index officiel examiné reste470.256.02.
La page legacy liste1198 sousR470 alors que les tables internes450/470
examinées l’omettent: exécution Linux880M non vérifiée, rejet non démontré.

Les corrections VkFence455.23.04, copies455.38, vidéo460.27.04 et pression
VRAM NvFBC proposent des questions pertinentes. Aucune correction de ces
changelogs n’est à ce jour démontrée à la fois absente de macOS et portable.
Les objets RM et bibliothèques graphiques restent fermés; les fichiers C de
glue Linux/UVM/DRM ne fournissent pas l’implémentation de ces corrections.
La matriceA précise pour24entrées version/composant/GK104/dépendance,
présenceMac indéterminée, risques, priorité et test. Gains hypothétiques.

Opportunités classées: A1 diagnostic soumission/transferts/ressources (valeur
CPU élevée si bottleneck confirmé); A2 vidéoH.264 (voie GPU actuellement
refusée, interface VA/AppleGVA non raccordée). AffichageG-SYNC Linux, PRIME,
Wayland et multi-GPU ont peu de valeur démontrée ici. GSP,RTD3 moderne,
Tensor cores et fonctionnalités GK110 ne deviennent pas des capacitésGK104.
Le projet open-gpu-kernel-modules NVIDIA requiert Turing+; Nouveau/NAK sont
pertinents pour Kepler, mais ne sont pas un pilote XNU/Metal prêt à intégrer.

4. Branche B: capacités réelles, limites et couches responsables

Déjà présent dans les cas validés: ressources Private/Managed/Shared,
argument buffers tier2,shuffle,xor,mémoire partagée48Kio,barrières,indirect
simple,rendu/MRT/MSAA/tessellation triangle. Refaire les288cas sans changement
n’ajouterait pas de preuve. Ils restent la base de non-régression.

Le pont KPCreatePipeline remplace dans le seul processus hôte le payload
validé d’un constructeur natif; le pilote existant garde les allocations,
commandes et synchronisations. Capture constructeur n’est pas dump du code
GPU résident; dispatch+oracles apportent la preuve d’exécution. NiveauL1.

Le harness kepler_air_compile sélectionne add_buffers et un ABI expérimental;
il n’est pas un compilateur MSL universel. Dans OpenNVDA déjà téléchargé,
air_nir.c contient pourtant cmpxchg avec mem_store(expected,old) et les
lowerings simd_sum/min/max/prefix/shuffle/ballot/all/any. Leur présence statique
n’est pas une qualification surSM30/macOS. Les tests NIR construits à la main
ne qualifient pas automatiquement cette traduction AIR. Adapter le harness
et vérifier ABI/carrier est le travail nécessaire avant réutilisation GPU.
Références de la chaîne existante:
Mesa26.2.4:96cb43121031992b85767f9c1be8f3f48e22b1d2
OpenNVDA:da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5
Les adaptations locales ne sont pas assimilées au code amont inchangé:
STRATEGIE_PREUVES.json conserve les hashes du harness,frontend et interface.

Mise à jour AIR CAS: le même AIR Apple, traduit avec une copie corrigée du
frontend, passe les cas global/partagé, comparaison égale/différente sur trois
graines (4 configurations, 12 captures NAK). La série conserve aussi le défaut
natif sans retry. Le retour AIR était i32 old, pas bool: correctif local de
largeur du résultat, expected issu du même CAS et promotion scratch vers SSA.
Le listing natif partagé suit old en r4 mais écrit le comparand r0 en sortie;
ce point de code généré est la prochaine cible, sans patch système appliqué.
Voir ../bridge/results/air-cas-final/RAPPORT.txt. Un thread/groupe et relaxed
seulement: pas encore contention, conformité générale ou intégration L3.

La matriceB réconcilie30lignes, SDK/compilateur/MTLDevice/exécution/justesse,
couche de blocage, intégration et limites. Une propriété false laisse souvent
la possibilité d’une émulation, mais n’établit pas un contrat Metal natif.
Pas de RT/Tensor coresGK104; calcul logiciel ray/matrice envisageable, API
moderne et performance restent distinctes. Dynamic libraries/ICB/ressources
exigent runtime et ABI au-delà de la génération SASS.

Dates vérifiées dans SDK26.2: argument encoder/heaps/fences macOS10.13,
events/ICB rendu10.14, placement heaps10.15, ICB compute concurrent11.0.
Les residency sets existent depuis15.0, avantMetal4. Queues/allocators/tables
MTL4 sont des API26.0/WWDC2025. Le PDF Apple actuel(21mai2026) liste les
familles Apple et le support Metal3/4, pas une histoire d’introduction des
fonctions ni une table de conformité Kepler. Ne pas redater les anciennes
fonctions comme nouvelles fonctionsMetal3. La version MSL reste distincte.

metal-cpp pin:{source_manifest['metal_cpp_commit']}
MTL4CommandQueue/ArgumentTable/Allocator envoient des messages ObjC; ces
headers ne fournissent pas leur implémentation. Metal4 officiel viseM1+/A14+.
SurNVMTLDevice: familleMetal4false,factoryqueue nil. C’est un blocage de
runtime/pilote observé avant le shader; aucune création/exécutionMTL4 réussie.

5. Prochaines expériences, résultats qui décideront la suite

B1, premier jalon acquis: cas sans boucle, contrat AIR i32 vérifié et même
AIR→NIR→SM30 correct après validation ABI. Suite: plusieurs lanes/groupes et
contention, puis réparation de payload natif dans notre seul processus en
préservant branches, barrières et scheduling. Aucun atomic_load aprèsCAS
pour maquiller expected; cela casserait la linéarisation.

A1 indépendant: mesurer CPUsubmit/attente,transferts,readback et temps mural
sur une charge native constante,ressources persistantes et lots contrôlés.
3échauffements/9essais alternés minimum,oracles et médianes/IQR; budget VRAM
propre plafonné. Identifier d’abord si le coût vient de l’app ou du pilote.

B2: factories puis exécution heaps/fences/events/ICB, étapes séparées et
oracles. Le simple draw indirect n’est pas ICB; selector n’est pas factory.
B3: couverture numérique/divergence explicitement définie du helperSIMD,
benchmark contre réduction native partagée puis un client adapté réelL2.
A2: audit statique du transport vidéo; pas nouvelle sonde identique refusée.
Les protocoles complets et critères d’arrêt sont dans EXPERIMENTATIONS_PRIORISEES.json.

6. Conditions de livraison et limites

JalonB: une fonction nouvelle/corrigée avec contrat,API et client explicite,
résultats CPU/GPU corrects et paquet reproductible (L2). JalonA: limitation
pilote macOS reproduite, modification ciblée non déployée avec interfaces,
non-régression et bénéfice mesuré. Ces jalons ne finalisent pas à eux seuls
une pile transparente macOSL3; celle-ci nécessite encore un vrai raccordement
runtime/pilote, contrats complets et validation système autorisée séparément.

Benchmarks conservés: sur deux kernels instrumentés,NAK prend~2.008 et
~3.143fois la durée native(64groupes,batch64). Mesure murale compute+readback,
pas pure latenceGPU ni occupation mesurée. Aucun gain général annoncé.

Commandes de ce rapport depuis le workspace:
python3 nvidia-880m-lab/driver-research-2026-10-13/tools/refresh_strategy_sources.py
Extraction MSL (première fois, avec Python fourni par Codex contenant pypdf):
python3 nvidia-880m-lab/driver-research-2026-10-13/tools/extract_strategy_msl.py
python3 nvidia-880m-lab/driver-research-2026-10-13/tools/make_strategy_report.py
Réutilise les snapshots officiels déjà téléchargés; aucune installation.
Python pypdf utilisé ici:
python3
Le fichier STRATEGIE_PREUVES.json contient hashes des entrées,83fichiers,
OS/RAM/CPU courants et état Git. Les anciens rapports/archives sont conservés.
Sources: HISTORIQUE_KEPLER.json; MATRICE_METAL.json; ../bridge/AUDIT_PONT_NAK.txt;
../bridge/results/native-features-report/summary.json et DIAGNOSTIC_CAS.txt;
../bridge/results/shared-units-summary.json et shared-benchmark-summary.json;
sources/strategy/manifest.json (MSL PDF, SDK et headers metal-cpp pinnés).
sources/nvidia-open-kernel-README.md; sources/nvk.html (périmètres Linux).
https://developer.apple.com/videos/play/wwdc2025/205/
https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf
https://www.nvidia.com/en-us/drivers/unix/legacy-gpu/
https://download.nvidia.com/XFree86/Linux-x86_64/
'''
# The prose is a technical handover, not a dense machine log. Keep names/paths
# unchanged while making the measurement phrases readable.
replacements = {
    'macOS26': 'macOS 26', 'iMac11,1/i7-870/32GiB': 'iMac11,1 / i7-870 / 32 GiB',
    '880M8GiB': '880M 8 GiB', 'PCI10de': 'PCI 10de', 'OCLPv3': 'OCLP v3',
    'support2.0.1': 'support 2.0.1', 'Metal4': 'Metal 4', 'Metal3': 'Metal 3',
    'Metal2': 'Metal 2', '3échauffements': '3 échauffements', '9essais': '9 essais',
    '83fichiers': '83 fichiers', '54configurations': '54 configurations',
    '162captures': '162 captures', '14/14configurations': '14/14 configurations',
    '571mots': '571 mots', 'objet4660/comparand4661': 'objet 4660 / comparand 4661',
    'expected4661': 'expected 4661', 'de4660': 'de 4660', '126configurations': '126 configurations',
    '98succès': '98 succès', '28échecs': '28 échecs', '18pipelines': '18 pipelines',
    '10résultats': '10 résultats', '304captures': '304 captures', '147736mots': '147736 mots',
    '13octobre': '13 octobre', '24entrées': '24 entrées', '30lignes': '30 lignes',
    '48Kio': '48 Kio', 'les288cas': 'les 288 cas', 'helperSIMD': 'helper SIMD',
    '64groupes': '64 groupes', 'batch64': 'batch 64',
    'api26.0': 'API 26.0', 'depuis15.0': 'depuis 15.0', 'macOS10.13': 'macOS 10.13',
    'ICB rendu10.14': 'ICB rendu 10.14', 'heaps10.15': 'heaps 10.15',
    'concurrent11.0': 'concurrent 11.0', 'SDK26.2': 'SDK 26.2', 'API26.0': 'API 26.0',
    'mémoire partagée48': 'mémoire partagée 48', 'passe54': 'passe 54',
    'global14/14': 'global 14/14', 'partagé4/14': 'partagé 4/14',
    'récente:126': 'récente: 126', 'et147736': 'et 147736',
    'build25G241': 'build 25G241', 'et880M': 'et 880M', 'lienRC2': 'lien RC2',
    'même13': 'même 13', 'archives355': 'archives 355', 'répertoireR470': 'répertoire R470',
    'reste470': 'reste 470', 'liste1198': 'liste 1198', 'sousR470': 'sous R470',
    'internes450': 'internes 450', 'Linux880M': 'Linux 880M',
    'VkFence455': 'VkFence 455', 'copies455': 'copies 455', 'vidéo460': 'vidéo 460',
    'vidéoH.264': 'vidéo H.264',
    'seuleMetal': 'seule Metal', 'NiveauL1': 'Niveau L1', 'applicationsL3': 'applications L3',
    'interfaceVA': 'interface VA', 'surSM30/macOS': 'sur SM30/macOS',
    'modesMetal': 'modes Metal', 'contratMetal': 'contrat Metal', 'contratSM30': 'contrat SM30',
    'depuisMetal': 'depuis Metal', 'avantMetal': 'avant Metal', 'pasMetal': 'pas Metal',
    'Metal 4false': 'Metal 4 false', 'factoryqueue': 'factory queue', 'viseM1': 'vise M1',
    'aprèsCAS': 'après CAS',
    'CPUsubmit': 'CPU submit', 'puisL2': 'puis L2', 'réelL2': 'réel L2',
    'macOSL3': 'macOS L3', 'branchA': 'branche A', 'tempsGPU': 'temps GPU',
    'latenceGPU': 'latence GPU', 'Mesa26.2.4': 'Mesa 26.2.4',
}
for compact, readable in replacements.items():
    text = text.replace(compact, readable)
text = re.sub(r'(\d)(configurations|captures|mots|cas|groupes|lignes|entrées|fois)', r'\1 \2', text)
text = text.replace('iMac11,1', 'IMAC_MODEL_PLACEHOLDER')
text = re.sub(r',(?=\S)', ', ', text)
text = text.replace('IMAC_MODEL_PLACEHOLDER', 'iMac11,1')
if progress_path.exists():
    text='MISE À JOUR COURANTE — CAS natif réparé sur un shader exact en L1; heaps/fences/events et alias natifs qualifiés; coût CPU batching mesuré. Voir ../bridge/PROGRES_CAS_RESSOURCES_CPU.txt et les matrices actualisées. Le support global matériel/Metal3/4 reste incomplet.\n\nLes analyses narratives ci-dessous décrivent les étapes antérieures; les matrices et la mise à jour ci-dessus donnent le dernier état vérifié.\n\n'+text
if semantic_path.exists():
    text='DERNIÈRE QUALIFICATION — Branche A24: quatre shaders CAS natifs réparés en L1 (30606 opérations correctes), reconnaissance AIR/SASS et refus conservateurs. Branche B10C/B10G: ICB CPU et génération GPU séparés; factory absente, cinq encodeurs no-op et air.command_buffer refusé. Benchmark applicatif à trois modes, 1728 dispatchs mesurés hors warmups. Voir ../bridge/CAS_SEMANTIQUE_ICB.txt et les matrices. Aucun pilote global modernisé; aucun port Linux appliqué.\n\nLes paragraphes historiques ci-dessous restent des comptes rendus d’étapes antérieures.\n\n'+text
if metallib_path.exists():
    text='DERNIER JALON — Réparation depuis l’AIR inclus dans une metallib à quatre fonctions; 8694 CAS supplémentaires corrects avec metadata NVIDIA originale7/8GPR et launch736/544. Dispatch indirect natif avec dimensions GPU, 11580invocations comptées et sorties exactes. Méthodes ICB rendu héritées: doesNotRecognizeSelector confirmé. Voir ../bridge/METALLIB_TRANSPORT_NATIF.txt. Objectif matériel complet toujours non atteint, aucun ICB ajouté ni intégration L3.\n\n'+text
if normalized_count_path.exists():
    text='MISE À JOUR MÉTADONNÉES/STREAM — Instruction count natif normalisé après ajout de code;1782CAS supplémentaires corrects. Flux NVIDIA capturé sans submission ni replay:464B direct/1052B indirect, helper puis utilisateur, changements d’offsets et restauration vérifiés. CB/QMD/ownership et réutilisation restent à construire; aucun ICB nouveau ou support global déclaré. Voir ../bridge/METADATA_COMMAND_STREAM.txt.\n\n'+text
if native_ownership_path.exists() and native_descriptor_path.exists():
    text='NOUVEAU JALON — Objets backing QMD/CB et rétention privée bornée localisés. Relecture GPU des descriptors et constantes:4917invocations,17736valeurs positives correctes,24mots QMD/108mots constants modifiés, négatifs conservés. Correction d’unité du décodeur CB (bytes, pas x256) distincte du calcul GPU. Aucun replay persistant, ICB, port Linux ou intégration système implémenté. Voir ../bridge/RESSOURCES_COMMANDES_NVIDIA.txt. Objectif global actif et incomplet.\n\nLes mises à jour suivantes décrivent les étapes précédentes.\n\n'+text
if native_replay_path.exists():
    text='REJEU NATIF QUALIFIÉ — Représentation persistante L1 de paquets NVIDIA avec CB/QMD dédiés, géométries/bindings indépendants et une préparation native retirée avant commit.9054invocations en séquence mixte, oracles et suppression sélective/totale PASS. Command words copiés CPU; contrat ICB public/GPU-résident et L2/L3 toujours non implémentés, pas de gain mesuré. Voir ../bridge/REJEU_NATIF_PERSISTANT.txt. Objectif global reste actif et incomplet.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if cpu_icb_path.exists() and cpu_icb_lifetime_path.exists():
    text='CPU ICB CALCUL, PREMIÈRE QUALIFICATION L1 — Objets et sélecteurs CPU fournis dans notre scope: plages/réutilisation/reset/copie CPU/rebinding,4396invocations et17584uint32. Deux essais lifetime après libération ICB/scope:198invocations,792uint32, classes restaurées avant commit; négatif unretained jamais soumis. Prototype sur consume_grid natif, command words recopiés CPU; pas de contrat ICB complet, GPU-résident/généré, render ou intégration L2/L3. Aucune modification système ni gain mesuré. Voir ../bridge/CPU_ICB_NATIF.txt. Objectif matériel complet toujours actif.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if profile_path.exists() and profile_life_path.exists():
    text='CPU ICB, TROIS PIPELINES NVIDIA NATIFS QUALIFIÉS L1 — Enregistrement depuis une bibliothèque vérifiée et reflection: entier, float exact, shared512B/barrière. Huit soumissions GPU,4725invocations/18900uint32, changements de pipeline/reset/copie/reuse et captures natives distinctes. Durée de vie après libération ICB/scope:594invocations/2376uint32 sur deux soumissions; trois pipelines et bindings conservés jusqu’à completion, négatif unretained jamais soumis. Caches de sous-classes réutilisés sur trois cycles. Contrat ICB complet, format GPU-résident/génération/rendu et intégration L2/L3 restent ouverts; aucun gain mesuré, système inchangé. Voir ../bridge/CPU_ICB_PIPELINES_NATIFS.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if manifest_path.exists() and manifest_life_path.exists() and manifest_regression_path.exists():
    text='CPU ICB, MANIFESTE ET SHARED DYNAMIQUE QUALIFIÉS L1 — Enregistrement natif sans noms imposés, SHA library/manifest et réflexion contrôlés; enregistrement distinct d’une qualification GPU. Deux nouveaux programmes, neuf soumissions5496/21984 et lifetime594/2376. Shared1/32/48Kio avec resize même commande1→48Kio, guards/cached/copied-bound contrôlés; treize refus API. Formats464B/496B et métadonnées natifs conservés; anciens trois programmes régression4725/18900. Aucun changement de pilote système/shader-code ou gain mesuré. Contrat complet, autres ABI/états/rendu/GPU-résident/génération et intégration L2/L3 restent ouverts. Voir ../bridge/CPU_ICB_MANIFESTE_MEMOIRE_DYNAMIQUE.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if all(p.exists() for p in [buffers_path,buffers_life_path,buffers_dynamic_path,buffers_legacy_path]):
    text='CPU ICB, IMPORT IMMUABLE ET BUFFERS4 QUALIFIÉS L1 — Library/manifest vérifiés puis chargés depuis leurs snapshots bytes, caller data détruite avant matérialisation. AXPY natif quatre buffers readonly/écriture/constant3, offsets et tailles128/8192/65536vecteurs;919040float32 corrects plus65536 après releaseICB/scope. Quatre contrôles de bornes/index/align/grille; inputs et gardes intacts. Shared dynamique et anciens programmes régressionPASS. Contrat complet, autres ABI/états/rendu/GPU-resident/génération et L2/L3 restent ouverts; système inchangé, aucun gain mesuré. Voir ../bridge/CPU_ICB_BUFFERS_IMPORT_IMMUABLE.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if all(p.exists() for p in [grid3d_path,grid3d_buffers_path,grid3d_shared_path]):
    text='CPU ICB, GRILLES2D/3D QUALIFIÉES L1 — GéométrieXYZ/builtins natifs préservés; sept CB dont un vide,28dispatchs/18632invocations comptées/149056uint32 corrects. Local1024threads/Z64, reshape, copie après reset et ranges; quatre contrôles de dimensions. Régressions4buffers919040float32 et shared1/32/48Kio5496/21984 PASS. Rendu/contrat complet/GPU-résident/génération/L2/L3 ouverts; système inchangé, aucun gain mesuré. Voir ../bridge/CPU_ICB_GRILLES_2D_3D.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if render_transport_path.exists():
    text='TRANSPORT RENDU NVIDIA NATIF QUALIFIÉ L1 — Dessins directs et indexés16/32, scissor et leases; huit CB98304float32 corrects (86016rejeu). Données Private d’indices dégénérées par GPU et retraits de dessins prouvent les dépendances attendues; aucun patch de shader/NAK. Fondation pour le raccord CPU ICB rendu, pas encore ses objets/sélecteurs publics. Contrat complet/GPU-résident/génération/L2/L3 ouverts; système inchangé, benchmark non exécuté. Voir ../bridge/REJEU_RENDU_NATIF.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if public_render_path.exists() and public_render_life_path.exists():
    text='CPU ICB RENDU AUX SÉLECTEURS PUBLICS QUALIFIÉ L1 — Factory, commandes direct/index16/32, ranges/reset/copie/overlap; scissor de l’encodeur hérité et pipeline client rétabli, dessin ordinaire suivant correct.135168float32 plus12288 après release scope/ICB/classes avantcommit. Sources communes régressions3D/shared/raw-rendu PASS. Profil pass/PSO fixe, scope mixte et contrat complet/GPU-résident/génération/L2/L3 ouverts; aucun système modifié/benchmark. Voir ../bridge/CPU_ICB_RENDU_PUBLIC.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
if mixed_scope_path.exists():
    text='SCOPE CALCUL/RENDU ICB MIXTE QUALIFIÉ L1 — Un shader NVIDIA natif écrit les indicesPrivate qu’un rendu indexé natif consomme dans le mêmeCB sans lectureCPU intermédiaire.9CB/192invocations comptées/110592float32 corrects; absencesproducer/consumer/degénérescence/copies/reset et régressions3D/render/shared PASS. PSOrendu/passencorefixe, ressources/états/conformance/GPU-résident/génération/L2/L3 ouverts, aucun benchmark. Voir ../bridge/CPU_ICB_CALCUL_RENDU.txt.\n\nLes mises à jour suivantes sont historiques.\n\n'+text
(REPORTS/'STRATEGIE_KEPLERMETAL.txt').write_text(text)
outputs=[REPORTS/name for name in ['STRATEGIE_KEPLERMETAL.txt','MODERNISATION_NVIDIA_ACTUALISEE.json',
         'MODERNISATION_NVIDIA_ACTUALISEE.csv','METAL_CAPACITES_ACTUALISEES.json',
         'METAL_CAPACITES_ACTUALISEES.csv','EXPERIMENTATIONS_PRIORISEES.json','STRATEGIE_PREUVES.json']]
dump(REPORTS/'STRATEGIE_LIVRAISON.json', {'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in outputs],
                                         'matrice_A_rows':len(a),'matrice_B_rows':len(b),'experiments':len(experiments)})
print(json.dumps({'rapport':str(REPORTS/'STRATEGIE_KEPLERMETAL.txt'),'matrice_A_rows':len(a),
                  'matrice_B_rows':len(b),'experiments':len(experiments),'system_files_unchanged':len(checked),
                  'new_GPU_experiments':0},ensure_ascii=False,indent=2))

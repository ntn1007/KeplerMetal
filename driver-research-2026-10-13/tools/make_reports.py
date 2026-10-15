#!/usr/bin/env python3
"""Write two independent evidence-calibrated reports. No driver code is built."""
from pathlib import Path
import csv,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports';REPORT.mkdir(exist_ok=True)
def save_table(name,rows):
    (REPORT/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    with (REPORT/(name+'.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
history=[]
def H(version,date,change,gk104,mac,source,anchor=''):
    history.append(dict(version=version,date=date,changement=change,applicabilite_GK104=gk104,transposition_macOS=mac,source=source,ancre_locale=anchor))
C='extracted/470.256.02/NVIDIA_Changelog'
H('355.11 / 16.0.12','2015 / inventaire 2026','La chaîne OpenCL installée rapporte 355.11.11.10.10.143; le paquet Linux 355.11 liste PCI 1198.','Lignée ancienne observée; aucune identité binaire Mac/Linux établie.','Point de référence; pas une équivalence de code.','inventory/capabilities.json; extracted/355.11/html/supportedchips.html')
H('396.18','2018-04-10','Nouveau compilateur SPIR-V Vulkan; allocation et binding Vulkan améliorés.','Générique au pilote; gain spécifique GTX 880M non mesuré.','Idées de compilation/cache/allocateur; bibliothèques ELF fermées sans entrée Metal.','https://www.nvidia.com/en-us/drivers/details/133571/','new Vulkan SPIR-V compiler')
H('418.113 / 430.09','2019','PCI 1198 est listé en 418.113 et absent dès 430.09 dans les tables examinées.','Contradiction documentaire avec la page legacy 470 qui liste 1198; fonctionnement Linux non testé.','Conserver 418 comme contrôle historique; ne pas déduire rejet matériel de l’absence du nom.','https://download.nvidia.com/XFree86/Linux-x86_64/418.113/README/supportedchips.html; https://www.nvidia.com/en-us/drivers/unix/legacy-gpu/','comparison/support-1198.json; sources/mobile-kepler-support-check.json')
H('450.57','2020-07-09','Repère Linux contemporain des bundles Big Sur bêta 3; corrections noyau Linux 5.8 et outils X/PRIME.','Support du silicium Kepler distinct de la certification du modèle mobile.','Adaptations Linux 5.8 ne corrigent pas les interfaces XNU/IOAccelerator.','https://www.nvidia.com/en-us/drivers/details/162107/')
H('455.23.04','2020-09-17','Correction de consommation CPU excessive avec de nombreux VkFence; nouveau type mémoire Vulkan visible et cohérent au CPU.','Piste logicielle générale; disponibilité du type mémoire et effet sur 1198 non vérifiés.','Étudier l’attente des fences et la stratégie de transferts macOS; aucun gain Metal ne découle du correctif Vulkan.','https://www.nvidia.com/en-us/drivers/details/163522/','excessive CPU usage; host-coherent')
H('455.38','2020-10-29','Correction d’un ordre incorrect de copies Vulkan successives.','Pas de restriction GPU indiquée; chemin Vulkan.','Exigence de synchronisation pertinente; aucun patch source Metal fourni.',C,'back-to-back copies')
H('460.27.04','2020-12-15','Cache shaders OpenGL/Vulkan déplacé et plafond par défaut augmenté à 1024 Mo.','Mesure logicielle; ne modifie pas les unités GK104.','Politique de cache transposable en conception; format/cache Linux inutilisable directement par Metal.',C,'default size for new OpenGL/Vulkan Shader Disk Cache')
H('460.27.04','2020-12-15','Transferts de surfaces VDPAU YCbCr améliorés.','H.264 du feature set D pertinent; nouveaux codecs limités par le matériel.','Interface VideoToolbox/AppleGVA et gestion surfaces requises; hors ajout Metal.',C,'VdpVideoSurfaceGetBitsYCbCr')
H('460.39','2021-01-26','Corrections de reprise/gestion runtime avec Linux 5.10.','Applicable au chemin Linux sous ses conditions; pas une preuve de reprise sur cet iMac.','Il faut des contrats de veille/réveil XNU propres. Pas de port direct du glue Linux.',C,'Linux 5.10')
H('460.67','2021-03-18','Correction G-SYNC après changement de mode sur Kepler.','Kepler explicitement nommé; écran interne et capacité VRR non établis ici.','Piste d’affichage; pas une nouvelle API Metal ni un gain de calcul.','https://www.nvidia.com/download/driverResults.aspx/171392/en-us/1000/')
H('465.19.01','2021-03-30','Extensions Vulkan de synchronisation et de mémoire workgroup; corrections allocation/arrays.','Pas de qualification 1198 ni exposition Metal établie.','Mappage des barrières, layout et initialiseurs dans compilateur/runtime à implémenter.',C,'VK_KHR_synchronization2')
H('R465/R470','2021','NVIDIA annonce OpenCL 3.0, avec maintien des fonctions 1.2 et fonctions 2.x optionnelles.','L’annonce officielle cible Maxwell et plus récent, pas Kepler. Aucun clinfo Linux 880M collecté. OpenCL 3.0 ne signifie pas toutes les fonctions OpenCL 2.x.','Ce n’est pas une amélioration Kepler établie; ICD/compilateur/ABI Darwin requis. Copier libnvidia-opencl.so ne restaure pas le compilateur Apple.','https://developer.nvidia.com/blog/nvidia-is-now-opencl-3-0-conformant/')
H('470.42.01','2021-06-22','Correction de corruption Wolfenstein Youngblood, explicitement Kepler/Maxwell/Pascal/Volta.','Une vraie correction Kepler dans le journal; pas un nouveau moteur matériel.','Cause et implémentation fermées; audit reproductible nécessaire avant équivalent Mac.','https://www.nvidia.com/download/driverResults.aspx/176525/en-us/','Wolfenstein')
H('470.42.01','2021-06-22','Limite du nombre de contextes OpenGL élargie et meilleure gestion de l’échec.','Gestion logicielle générique des contextes.','Idée d’allocation et de gestion d’erreur; Metal a d’autres contrats de contexte.','https://www.nvidia.com/download/driverResults.aspx/176525/en-us/','concurrent OpenGL contexts')
H('470.42.01','2021-06-22','Accélération OpenGL/Vulkan sous Xwayland; PRIME et capture NvFBC corrigés.','Peut utiliser Kepler sous Linux; aucun rapport avec WindowServer démontré.','Xwayland/GLX/DRM/PRIME doivent être remplacés par des interfaces macOS, pas copiés.','https://www.nvidia.com/download/driverResults.aspx/176525/en-us/','Xwayland')
H('470.63.01','2021-08-10','Repère Linux contemporain du noyau Monterey bêta 6; VK_KHR_wayland_surface et correctif rFactor2.','Extension de présentation et correctif application; pas une qualification 880M.','Pas de couche Wayland sur la pile étudiée.','https://www.nvidia.cn/Download/driverResults.aspx/179605/cn/1000/')
H('470.74','2021-09-20','Correction de pertes d’applications après suspend et de consommation RAM vkd3d-proton.','Logiciel générique; présence du défaut sur le Mac non établie.','Exigences de conservation VRAM et cycle de vie pertinentes, reproduction sous macOS requise.','https://forums.developer.nvidia.com/t/linux-solaris-and-freebsd-driver-470-74-production-branch-release/189679')
H('470.103.01','2022-01-31','Correction de spinlock non relâché et d’une course lors d’erreurs Xid multi-GPU.','Spinlock potentiellement général; course multi-GPU hors configuration mono-GPU.','Contrats de verrouillage/récupération intéressants; logique fermée non récupérable dans les fichiers C publiés.','https://forums.developer.nvidia.com/t/linux-solaris-and-freebsd-driver-470-103-01-production-branch-release/202129')
H('470.129.06 / 470.161.03','2022','Compatibilité NvFBC avec loader Vulkan récent; correction capture quand VRAM pleine.','Concernent capture Linux; pressure mémoire pertinente en principe.','Tester budgets et erreurs ressources Metal; pas d’accès automatique à NvFBC depuis WindowServer.',C,'Vulkan loader versions 1.3.204; video memory is full')
H('470.182.03 / 470.223.02','2023','Corrections PRIME multi-écrans, restauration console simpledrm et timing de présentation Vulkan.','Pile Linux/écrans; pas un meilleur compilateur de kernels prouvé.','Pas de transposition directe; interfaces display et temps de présentation distinctes.',C,'simpledrm; VK_NV_present_barrier')
H('470.239.06','2024-02-22','Note publique limitée à corrections mineures et améliorations.','Aucune amélioration GK104 identifiée dans cette note vague.','Ne permet ni patch Mac ciblé ni annonce de gain.',C,'2024-02-22')
H('470.256.02','2024-06-04','Maintenance finale publiée R470; bulletin juin 2024: R470 Linux traite CVE-2024-0090 et CVE-2024-0092.','Corrections logicielles de branche; aucun diagnostic de vulnérabilité du pilote Mac effectué.','Pas de source du correctif RM; ne prouve pas que le binaire Mac contient le même défaut.','https://nvidia.custhelp.com/app/answers/detail/a_id/5551; https://docs.nvidia.com/datacenter/tesla/pdf/NVIDIA_Data_Center_GPU_Driver_Release_Notes_470_v12.0.pdf')
H('R465/R470 GSP, NGX/DLSS, RTD3','2021 et après','Composants GSP/NGX dans l’archive et gestion D3 moderne.','GSP et modules ouverts: Turing+; RTD3 exige Turing+ et plateforme adaptée. DLSS ne confère aucun Tensor Core au GK104.','Ne pas choisir ces composants comme voie Kepler.','https://github.com/NVIDIA/open-gpu-kernel-modules; https://download.nvidia.com/XFree86/Linux-x86_64/470.256.02/README/dynamicpowermanagement.html')
H('CUDA 11+ / Kepler GK110','2020 et après','CUDA 11 retire SM30/SM32. Hyper-Q et dynamic parallelism de Kepler concernent GK110.','880M = GK104 SM30: ces fonctions ne sont pas héritées des Tesla K80/K110.','Pilote 470 récent ne rend pas CUDA 11 ou ces unités compatibles avec 880M.','https://docs.nvidia.com/cuda/archive/11.0/cuda-toolkit-release-notes/index.html; https://docs.nvidia.com/cuda/archive/11.8.0/kepler-tuning-guide/index.html')
save_table('HISTORIQUE_KEPLER',history)
metal=[]
def M(feature,scope,current,hardware,work,evidence,priority='étude'):
    metal.append(dict(fonction=feature,perimetre_API=scope,exposition_actuelle=current,capacite_GK104=hardware,travail_pile_macOS=work,preuve=evidence,priorite=priority))
E='inventory/capabilities.json'
P='inventory/prior-evidence.json -> ../bridge/results/'
M('Familles et versions','Metal 1/2/3/4','Mac1 et Common1/2 oui; Mac2/Common3/Metal3/Metal4 non. FeatureSets Mac1 v1/v2/v3/v4 oui.','Des fonctions modernes individuelles peuvent utiliser le GK104; aucune famille complète supplémentaire qualifiée.','Couverture complète du contrat de famille, formats, limites et sémantiques avant d’annoncer une famille.',E,'préalable')
M('Version du langage MSL','Compilateur','Ancien test addition accepte options 1.1 à 4.0; aucune nouvelle fonction 4.0 dans ce shader.','Acceptation d’une option ne crée pas d’unité matérielle.','Frontend AIR/NIR, bibliothèque standard et ABI SM30 fonction par fonction; tests utilisant vraiment les nouveautés.','../results/metal-capabilities.json; tools/metal_capabilities.mm dans le lab parent','préalable')
M('FP32 / GEMM / FMA','Calcul Metal existant','Kernels simples natifs disponibles; couverture applications modernes incomplète.','NAK add/GEMM sur échantillons 64 à 1024 vérifiés au CPU.','Généraliser compilation, disposition matrices, valeurs limites et intégration aux bibliothèques utilisées par les applications.',P+'compute-reproduction/','haute')
M('Mémoire partagée et barrières','Calcul Metal existant','49152 octets par threadgroup déclarés; groupes 1024 threads testés auparavant.','16/32/48 Kio, échange de données et synchronisation vérifiés sur cas sélectionnés.','Abaisser les barrières avec bon scope/ordre; couvrir divergence et interactions global/shared.','inventory/evidence-summaries/shared-units-summary.json','haute')
M('Atomiques uint32 en mémoire partagée','Calcul / MSL','ADD natif testé; CAS weak natif échoue Invalid Resource dans l’épreuve isolée.','NAK ADD/EXCH/CAS vérifiés sous contention; CAS par boucle lock/unlock.','Diagnostiquer CAS natif indépendamment; qualifier progrès, scopes et mémoire. Référence CAS sérialisée ne prouve pas builtin natif.','inventory/evidence-summaries/shared-units-summary.json; ../bridge/results/shared-cas-reference-isolated/','haute')
M('Atomiques globales uint64','Fonction supplémentaire ciblée','Pas de qualification MSL atomic64 native dans cette pile.','72 cas NAK ADD/EXCH/CAS, 35610 opérations, retours/carry/wrap vérifiés.','Types/builtins AIR/NIR, mapping SM30, ordre mémoire et atomiques restantes; pas de déclaration globale atomic64 après 3 opérations.','inventory/evidence-summaries/atomic64-summary.json','haute')
M('Warp shuffle et réductions SIMD','MSL / kernels modernes','Couverture des intrinsics SIMD moderne non établie.','SHFL XOR sur warps complets validé; opérations masquées/divergentes non couvertes.','Abaisser shuffle/ballot/reduction, définir lanes actives et edge cases; tests de conformité puis workload réel.',P+'compute-reproduction/shuffle-resident.json','haute')
M('Argument buffers','Metal 2','Tier 2 déclaré: enum brut 1. L’ancienne étiquette tier 1 était erronée.','Ressources et descripteurs sont exécutables; grand bindless, indexation et résidence non qualifiés dans le lab.','Tester d’abord le tier 2 déjà annoncé: textures/samplers/buffers, tableaux, indices dynamiques et useResource.',E+'; inventory/SDK-MTLDevice.h lignes 298-302','haute')
M('Textures read_write','Metal 2','Read/write textures tier 1 déclaré; feature set ReadWriteTextureTier2 non.','SULD/SUST qualifiés sur quatre formats et OOB zero; FP16 store RTZ observé.','Formats du tier 2, permissions, cohérence/cache et aliasing; vérification de l’arrondi avant conformité.','inventory/evidence-summaries/image-load-summary.json; '+E,'haute')
M('Draw / dispatch indirect simple','Metal existant','Commandes indirectes utilisées dans les épreuves de rendu du lab.','Arguments produits sur GPU et consommés en rendu testés.','Couverture offset/alignment/bounds, synchronisation producteur-consommateur et réutilisation.',P+'resource-summary.json','moyenne')
M('Indirect command buffers','Extension Metal 2','Non inventoriés par un test de création/exécution actuel. Le draw indirect simple ne les valide pas.','Peut nécessiter interprétation/lowering de commandes GPU; capacité spécifique non démontrée.','Encodage ICB, résidence, limites, invalidation et barrières; vérifier création native avant émulation.',E+'; aucune preuve ICB','moyenne')
M('Heaps / placement / fences / events','Gestion Metal 2+','Contrats précis non qualifiés dans cette phase; présence d’un sélecteur insuffisante.','Allocation/copie/synchronisation par pilote actuel utilisées dans le lab; aliasing et placement restent ouverts.','Allocateur, résidence, réutilisation mémoire et ownership CPU/GPU; tests de races, contention et budgets.',P+'resource-summary.json','haute')
M('Groupes de threads non uniformes','Fonction Metal 2','Grids et groupes uniformes testés; dispatchThreads non uniforme non qualifié.','Possibilité de padding avec masques; sémantique barrières/threads partiels à résoudre.','Adaptation launcher et masque des lanes, builtins de dimension exacts; pas seulement arrondir la taille.',P+'resource-summary.json','moyenne')
M('Tessellation','Rendu Metal existant','Tessellation triangle native et stade NAK d’évaluation testés.','Facteurs 0..64 et coordonnées capturées; limites raster à grands facteurs observées.','Compléter quad/topologie, facteurs partitionnés et cas raster non conformes; éviter d’en faire une nouvelle capacité universelle.','inventory/evidence-summaries/tessellation-summary.json','moyenne')
M('Rendu, MRT, MSAA, depth/stencil','Metal existant','MSAA 1/2/4/8 déclaré; 16 non. FP32 filtering/MSAA oui.','Triangles, états de rendu, MRT 2/4/8 et resolve vérifiés sur échantillons.','Formats supplémentaires, combinaisons et erreurs; conserver driver gestion des ressources.','inventory/evidence-summaries/render-state-summary.json; '+E,'moyenne')
M('BC compression / LOD / sample positions','Formats et sampling','BC oui; query LOD et sample positions programmables non.','BC fait partie du matériel; exposition étendue de sampling à tester, pas déduite des performances.','Compilateur/descripteurs, limites de sampler et formats; identifier refus API ou manque hardware.',E,'moyenne')
M('Raster order groups','Fonction avancée','areRasterOrderGroupsSupported = false.','Conformité d’ordre fragment non démontrée; émulation multi-pass possible en théorie avec restrictions.','Ordre par pixel, accès concurrents et garanties blend; qualifier la conformité avant publicité.',E,'basse')
M('Barycentriques / pull interpolation','Fonction avancée','Deux propriétés false.','Interpolation raster déjà testée; accès barycentrique général non qualifié.','ABI fragment et sources des coordonnées, dérivées et perspective; émulation possible à évaluer.',E+'; ../bridge/results/vertex-io-summary.json','moyenne')
M('Textures / buffers sparse','Fonction avancée','supportsSparseTextures = false; supportsPlacementSparse absent.','MMU présente; granularité/residency/zero et réaffectation compatibles Metal non établies.','Mapping de pages, faults, residency et synchronisation via driver; pas un ajout de compiler seulement.',E,'basse')
M('Bibliothèques dynamiques / function pointers','Fonction avancée','Compute/render dynamic libraries et function pointers false.','Branchement/call SASS ne valide pas ABI de liaison Metal ou tables de fonctions.','Linker, relocation, metadata, scratch/stack, cycle de vie et contrôle d’accès aux ressources.',E,'basse')
M('Mesh / object shaders','Metal 3','supportsMeshShaders = false.','Pas de stade mesh natif qualifié; compute + vertex/indirect peut émuler certains algorithmes.','Frontends/stages, payload, sorties primitives, synchronisation et conformance; coût non mesuré.',E,'basse')
M('Ray tracing','Metal 3+','Compute/render ray tracing et primitive motion blur false.','Pas d’unité RT dédiée GK104; BVH/intersection logiciels sur GPU restent concevables.','Structures accélération, traversée, fonctions intersection, stack et barrières; aucun support API complet prouvé.',E,'basse')
M('Tile shaders / imageblocks / memoryless','Fonctions Apple GPU','Non qualifiés sur cette carte.','GK104 est un renderer immédiat; on ne lui ajoute pas le tile storage Apple par pilote.','Émulation par VRAM et passes pourrait couvrir des cas; coût et contrat memoryless à établir.','sources/metal-feature-tables.pdf; matériel GK104','basse')
M('FP16 / BF16 / SIMD matrices / tensors','MSL / Metal 4 ML','Conversions/stockage FP16 vus; tensors non exposés par la sonde.','Pas de Tensor Cores; conversion/arithmétique FP32 ou entières peuvent émuler certains formats.','Math kernels, types/arrondis/NaN/overflow et layout coopératif; comparer débit au FP32 avant bénéfice.',P+'image-load-summary.json','moyenne pour formats; basse pour API ML complète')
M('FP64','Extension de calcul hors MSL standard','OpenCL expose fp64; MSL double natif non établi.','DADD NAK vérifié sur 1041 doubles; ce n’est pas toute la bibliothèque FP64.','Frontend/ABI et fonctions math; extension application locale possible, pas support officiel Metal double.',P+'compute-reproduction/fp64-resident.json; '+E,'moyenne')
M('Queues, allocators, argument tables, barriers MTL4','Metal 4','Sélecteur queue présent mais création nil; famille Metal4 false.','Programmation classique compute/raster possible. Modèle de commande MTL4 non exécuté.','Implémentation objets MTL4 et protocoles driver, mémoire explicite/résidence, encoding et barrières; chantier runtime au-delà NAK.',E+'; https://developer.apple.com/documentation/metal/understanding-the-metal-4-core-api','basse')
M('MetalFX / fast resource loading / MPS','Frameworks au-dessus Metal','Aucune qualification complète dans cette phase.','Kernels de resampling/ML possibles; fonction framework dépend shaders, API, formats et CPU.','Auditer les kernels/objets réellement consommés, compilation et I/O; un remplacement math local ne valide pas MetalFX/MPS.',E,'étude par application')
M('Vidéo H.264 encode/decode','VideoToolbox, distinct de Metal','Tests antérieurs imposant hardware refusés; CPU contrôlé fonctionne. VA installé est un stub dans analyse précédente.','880M listée VDPAU D en 418.113: moteurs H.264 historiques. Aucun transport moteur vidéo réussi sous macOS.','Backend AppleGVA/VideoToolbox, bitstreams, surfaces, DMA et fences; pas de réactivation NVENC en modifiant une famille Metal.','inventory/evidence-summaries/video-summary.json; extracted/418.113/html/supportedchips.html','haute si objectif vidéo')
M('Affichage / WindowServer / veille / clocks','Intégration système','Affichage fonctionne via pilotes restaurés; amélioration système non mesurée.','Exécution applicative NAK ne teste ni scanout ni gestion thermique ou reprise.','ABI IOAccelerator/IOFramebuffer, scheduler, recovery et politiques énergie; tests isolés avant toute intégration.','inventory/loaded-kexts.txt; inventory/oclp-root-patches.json','étude seulement')
M('Bénéfice CPU et performance','Objectif utilisateur','Benchmarks locaux antérieurs disponibles; aucun gain d’application entière démontré.','NAK plus lent sur deux kernels shared instrumentés; softmax résident peut réduire CPU dans son workload précis.','Identifier workload/utilisateur, maintenir données GPU, mesurer transferts/CPU/GPU et comparer meilleurs backends adaptés.','../bridge/COMPARAISON_METAL_NAK.txt; ../PORTAGE.txt','haute')
save_table('MATRICE_METAL',metal)
manifest=json.loads((ROOT/'archives/manifest.json').read_text());components=json.loads((ROOT/'inventory/components.json').read_text())
kernel=json.loads((ROOT/'comparison/package-comparison.json').read_text())
intro='''HISTORIQUE NVIDIA KEPLER — 13 octobre 2026

Objet: inventaire en lecture seule et archives Linux inspectées hors système.
Aucun installateur .run exécuté, pilote compilé/porté ou changement macOS/OCLP.

1. Configuration actuelle et origine des composants

iMac11,1; Intel i7-870 2,93 GHz, 4 cœurs/8 threads, 32 Gio RAM.
macOS 26.7.1, build 25G241; GTX 880M, PCI 10de:1198, 8 Gio VRAM,
PCIe x16. La fréquence 1908 MHz retournée par OpenCL est une déclaration
du pilote; elle n’est pas une mesure de fréquence physique ni un overclock.

Chargés d’après kmutil: GeForce, NVDAResman et NVDAGK100Hal 16.0.0;
IOAcceleratorFamily2 487.4.4. NVDAGF100Hal existe sur disque mais n’apparaît
pas chargé. NVDAStartup existe sur disque; ne pas confondre fichier et module chargé.

Le plist du root patch indique OCLP v3.0.0, support package v2.0.1,
patch du 8 octobre 2026, référence release 3.0.0-rc.2.
Commit de référence: d622cd5de86e5cb9a8c975c2809dbdbd2822c86e.
Ce commit est celui de la release référencée, pas une preuve du commit de
construction exact de l’application installée. SHA des composants enregistrés.

Pile mixte déclarée par le plist:
- GeForce.kext: 12.0 Beta 6-23.4; HAL/RM/Startup/VA: 12.0 Beta 6.
- AIR et GL: 11.0 Beta 3; MTL: 11.0 Beta 3-22.
- Metal et GPUCompiler: 13.2.1-25; MTLCompiler: 13.6-25.
- OpenCL: merges de 11.6 et 12.5.
Ces chaînes sont des noms de payload OCLP; les suffixes désignent des
adaptations et ne donnent pas de commit NVIDIA. Les versions bundles sont
16.0.0, short 16.0.12 pour AIR/GL/MTL et 16.0.14 pour noyau/VA.
OpenCL rapporte séparément 16.0.12 355.11.11.10.10.143.
Les plugins NVPTX.dylib et libCLVMNVPTXPlugin.dylib sont présents; leurs
empreintes et celles du payload GPUCompiler/3802 sont dans
inventory/compiler-payload-files.json. GPUCompiler a plusieurs dossiers
Versions (dont 3802, 31001 et 32023); le seul lien Current ne décrit donc
pas toute la pile de compilation restaurée.
L’historique Linux ne permet pas de prouver quels correctifs sont déjà dans
chaque binaire Apple fermé. Ni 16.0.0 ni 355.* ne prouvent un code identique.
Source OCLP et fichiers locaux: inventory/oclp-root-patches.json,
inventory/components.json, sources/oclp-kepler.py et sources/oclp-metal3802.py.
https://raw.githubusercontent.com/dortania/OpenCore-Legacy-Patcher/d622cd5de86e5cb9a8c975c2809dbdbd2822c86e/opencore_legacy_patcher/sys_patch/patchsets/hardware/graphics/nvidia_kepler.py

2. Références choisies et archives

355.11 (31 août 2015): contrôle de lignée lié au numéro OpenCL actuel.
418.113 (5 novembre 2019): contrôle qui liste explicitement 1198.
450.57 (9 juillet 2020): contemporain des bundles Big Sur bêta 3.
470.63.01 (10 août 2021): contemporain des pilotes Monterey bêta 6.
470.256.02: release Linux publiée 4 juin 2024 dans les notes NVIDIA;
date de fichier FTP 23 mai 2024, distincte de la date de publication.
La page Unix actuelle donne encore 470.256.02 comme dernière legacy R470:
https://www.nvidia.com/en-us/drivers/unix/
Les branches plus récentes affichées sur cette page ne constituent pas des
pilotes Kepler. Aucun pilote Linux n’a été installé ou exécuté sur ce Mac.

Anomalie documentaire: legacy-gpu associe GTX 880M/1198 à 470, tandis que
les README/JSON des paquets 450/470 ne listent pas 1198. Les README 355 et
418 le listent; les pages examinées 430.09/430.14/440.100 ne le listent plus.
Cette absence ne prouve pas un rejet à l’exécution. R470 est bien la dernière
branche Kepler annoncée; sa compatibilité concrète 880M n’a pas été testée ici.
https://www.nvidia.com/en-us/drivers/unix/legacy-gpu/
https://download.nvidia.com/XFree86/Linux-x86_64/418.113/README/supportedchips.html
Voir comparison/support-1198.json et sources/mobile-kepler-support-check.json.

Les .run sont conservés en mode 0644. Extraction Python de la charge XZ/tar:
tous les fichiers réguliers et dossiers; liens/special files inscrits au manifeste
mais non matérialisés. SHA256 NVIDIA externe vérifié lorsqu’il existe; MD5
embarqué vérifié sur les octets depuis la ligne 4 jusqu’à EOF pour tous les
paquets, conformément au header. MD5 établit l’intégrité embarquée, pas une
authentification indépendante. Les versions sans SHA externe ont une empreinte
SHA256 calculée localement; aucune empreinte fournisseur n’est inventée.

'''
for a in manifest:
    intro+=f"{a['version']}: {a['bytes']} octets\nURL {a['url']}\nSHA256 {a['archive_sha256']}\nSHA fournisseur vérifié: {a['official_sha256_verified']}; MD5 embarqué: {a['embedded_archive_md5_verified']}\n\n"
intro+='''3. Changements documentés et transposition

Les éléments ci-dessous sont des changements publics identifiés, pas un diff
complet du cœur NVIDIA fermé, ni une liste de nouveautés absentes du Mac.
Le CSV/JSON distingue silicium GK104, API Linux et travail macOS.
Les journaux NVIDIA contiennent des préambules sans version/date; l’index
les conserve comme tels. Certains journaux ont été révisés rétrospectivement.
Ne pas attribuer une ligne non datée au tag courant sans autre source.

'''
for i,h in enumerate(history,1):
    intro+=f"{i}. {h['version']} — {h['date']}\n{h['changement']}\nGK104: {h['applicabilite_GK104']}\nmacOS: {h['transposition_macOS']}\nSource: {h['source']}\n"
    if h['ancre_locale']:intro+=f"Repère: {h['ancre_locale']}\n"
    intro+='\n'
intro+='''4. Ce que l’inspection des fichiers démontre

Le noyau contient des interfaces C Linux, UVM, DRM/modeset et un cœur
RM nv-kernel.o_binary ELF fermé. Le Kbuild le décrit comme commun aux
plates-formes UNIX; cela ne fournit ni le format Mach-O ni les services XNU.
Les paquets n’ont pas de couche Metal/AIR Apple. Les .so de compilation,
Vulkan, OpenGL, CUDA et vidéo sont des binaires Linux, pas du code Metal.
Le diff des fichiers lisibles n’expose pas les algorithmes internes du RM.
Le cœur RM passe de 11886320 octets en 355 à 41624296 en 470.256.02;
cette croissance n’est pas une mesure de performance ou de qualité.

Comparaisons statiques reproductibles:
'''
for k in kernel:intro+=f"{k['before']} -> {k['after']}: {len(k['changed'])} fichiers communs modifiés; {len(k['added'])} ajoutés; {len(k['removed'])} retirés; {len(k['readable_kernel_changes'])} fichiers noyau lisibles modifiés/ajoutés/retirés.\n"
intro+='''Les bibliothèques versionnées changent de nom: les nombres ajoutés/retirés
incluent ces renommages. Voir comparison/package-comparison.json et les .diff.

5. Ce qui mérite une étude ultérieure

Premier lot: attente des fences, conservation des ressources, budgets mémoire,
transferts et cache de compilation. Ces problèmes logiciels pourraient toucher
GK104, mais chaque défaut doit être reproduit sur la pile macOS avant patch.
Deuxième lot distinct: compilateur et API Metal, décrit dans MATRICE_METAL.txt.
Les gains CPU des VkFence Linux ne sont pas des gains de WindowServer.

NVIDIA open-gpu-kernel-modules est ouvert mais cible Turing et plus récent,
avec firmware GSP correspondant. Il ne fournit pas un driver Kepler libre.
Nouveau/NVK est la piste libre pertinente: documentation Mesa actuelle annonce
Kepler+, avec backend noyau Linux. Cela ne fournit pas les contrats XNU.
https://github.com/NVIDIA/open-gpu-kernel-modules
https://docs.mesa3d.org/drivers/nvk.html

Conclusion de l’inventaire: des améliorations et corrections Linux existent;
leur transposition est une étude d’interfaces/algorithmes, pas une mise à jour
directe du pilote Mac. Aucun gain de débit, fréquence ou utilisation CPU du
nouveau pilote n’a été annoncé ni mesuré dans cette phase. Portage non lancé.
'''
(REPORT/'HISTORIQUE_KEPLER.txt').write_text(intro)
report='''MATRICE METAL / GTX 880M GK104 — 13 octobre 2026

1. Résultat vérifié aujourd’hui

Sonde propre au processus, signée ad hoc; propriétés et factory queue,
sans compilation shader, dispatch GPU, interposition NAK ou modification système.
OpenCL énumère actuellement CPU et GTX en 1.2 et annonce un compilateur.
Le PCH NVPTX LLVM 3.5 exigé par l’échec précédent reste absent sur disque:
/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/A/lib/clang/3.5/include/cl_kernel.nvptx64.pch
Cela confirme l’absence du fichier, sans relancer un build OpenCL. Les plugins
présents et compiler_advertised=1 ne prouvent pas une compilation fonctionnelle.
NVMTLDevice GTX 880M, registry ID 4294968458, mémoire dédiée.
Mac1/Common1/Common2 oui; Mac2/Common3/Metal3/Metal4 non.
FeatureSets Mac1 v1/v2/v3/v4 annoncés; Mac2 v1 non.
48 Kio de mémoire threadgroup; limite par dimension 1024/1024/64,
à ne pas multiplier: les anciens essais qualifient 1024 threads au total.
Budget recommandé 8 Gio; maxBufferLength 6 Gio. currentAllocatedSize=0
concerne les ressources de cette sonde, pas l’utilisation globale de la VRAM.

Correction de l’inventaire précédent: argumentBuffersSupport brut 1 = tier 2
(tier 1 = 0). readWriteTextureSupport brut 1 = tier 1 (none=0, tier2=2).
Les deux enums ne doivent pas être interprétés avec la même numérotation.
La sonde compare maintenant aux constantes du SDK, et conserve leurs noms.
Cette correction de lecture ne constitue pas une nouvelle fonction activée.
Le tier 2 déclaré doit encore être testé sur tableaux/indexation/résidence.

Ray tracing, mesh, dynamic libraries, function pointers, sparse textures,
query texture LOD, barycentriques, raster order groups et sample positions
programmables non annoncés par les getters interrogés. Null = sélecteur absent,
pas un getter qui retourne false. Les noms corrects areRasterOrderGroupsSupported
et areProgrammableSamplePositionsSupported sont aussi interrogés.
Le sélecteur de queue Metal4 existe; sa factory retourne nil.
BC texture compression, float32 filtering et float32 MSAA annoncés.
MSAA 1/2/4/8 oui, 16 non. Ce sont des déclarations, pas des rendus de conformité.

2. Comment lire les niveaux de preuve

Exposition: réponse API actuelle. Matériel exécuté: résultats des fixtures
du laboratoire antérieur, dont les SHA du pilote concordent avec aujourd’hui.
Les tests GPU précédents n’ont pas été relancés lors de cet inventaire.
Proposition: travail à construire et qualifier, sans garantie de conformité.
La preuve d’import NAK porte sur les octets transmis au constructeur et sur
les sorties/contrôles GPU; elle n’est pas un dump de l’instruction résidente.

Mac1 n’est pas un plafond “Metal 1 seulement”: les familles, le modèle API,
le langage MSL et la version du SDK sont des axes différents. L’addition simple
acceptée avec option MSL 4.0 ne prouve pas une implémentation MSL 4.0 complète.
Le tableau Apple actuel (21 mai 2026) est centré sur Apple GPU; il ne sert
pas de certification rétroactive Mac1. Les caractéristiques legacy sont
inventoriées directement et confrontées aux headers installés.
https://developer.apple.com/documentation/metal/detecting-gpu-features-and-metal-software-versions
https://developer.apple.com/metal/Metal-Feature-Set-Tables.pdf

Le modèle de commande Metal4 requiert de nouveaux objets distincts MTL4.
Apple annonce officiellement M1/A14 et plus récent; la 880M n’est pas une
cible officielle. Une couche compatible partielle resterait un projet propre
dont les familles ne pourraient être annoncées avant qualification complète.
https://developer.apple.com/videos/play/wwdc2025/205/
https://developer.apple.com/documentation/metal/understanding-the-metal-4-core-api

3. Matrice fonction par fonction

Mêmes lignes en CSV et JSON, avec exposition, potentiel matériel, travail et preuve.
Les étiquettes Metal2/3/4 situent le travail; elles n’attribuent pas une
fonction exclusivement à une version ni ne certifient toute cette version.

'''
for i,m in enumerate(metal,1):report+=f"{i}. {m['fonction']} ({m['perimetre_API']})\nActuel: {m['exposition_actuelle']}\nGK104: {m['capacite_GK104']}\nÀ ajouter/qualifier: {m['travail_pile_macOS']}\nPreuve: {m['preuve']}\nPriorité: {m['priorite']}\n\n"
report+='''4. Architecture des travaux et ordre recommandé

A. Frontend/compilateur: définir les intrinsics/types réellement manquants,
les traduire en NIR/SM30 et respecter masques, arrondis, mémoire et ABI.
B. Driver utilisateur Metal: ressources/descripteurs, formats, commande,
résidence et contrats de pipeline. NAK seul ne crée pas ces objets/API.
C. Noyau macOS: canaux, VM GPU, interruptions, fences, isolation, recovery,
énergie et suspension; pertinent uniquement si le driver actuel ne suffit pas.
D. Frameworks/applications: utilisent les shaders et objets réels; mesurer
le workload complet et les transferts. L’affichage système est une intégration
additionnelle, pas un résultat déduit d’un kernel hors écran réussi.

Priorité concrète proposée après cet inventaire: qualifier le tier 2 déjà
annoncé, les intrinsics SIMD et le CAS natif; choisir ensuite une fonction
manquante réellement consommée par une application, sans changer les pilotes.
Une étude de scheduler/fences Linux forme un autre lot, si un défaut macOS
reproductible ou une dépense CPU mesurée la justifie. Aucun lot lancé ici.

5. Performance: garder les résultats déjà mesurés et leur portée

Comparaison précédente Metal natif/NAK: 3 échauffements et 9 essais par chemin,
ordre alterné, instrumentation équivalente. 64 groupes, 128 threads, batch64:
- échanges shared48Kio: natif 0,372482 ms/dispatch; NAK 0,747540;
  ratio apparié NAK/natif 2,008.
- ADD shared32: natif 0,012488 ms/dispatch; NAK 0,039103;
  ratio apparié 3,143.
Les durées comprennent submit/wait et lecture amortie; ce ne sont pas des
latences GPU isolées. NAK provient de NIR construit pour ces deux kernels,
pas d’une traduction automatique de toute application. Occupation non mesurée.
Ce benchmark montre NAK plus lent dans ces cas; il n’établit pas un gain de
pilote, de LLM ou de WindowServer. Données: ../bridge/COMPARAISON_METAL_NAK.txt.

Les tests shared288 sont de justesse: 96 NAK/96 référence/96 contrôle,
dont 52224 threads atomiques NAK et 786432 mots de sortie capacity NAK.
Ces nombres ne sont pas 288 kernels NAK ni 52224 tests indépendants.
Le CAS de référence Metal utilise load/compare/store sérialisés; le builtin
CAS weak natif reste en échec distinct. Ne pas confondre les deux références.

Cette matrice ouvre des extensions ciblées plausibles; elle n’établit pas
Metal3/4 complet sur GK104. Aucun score de performance n’est déduit de l’âge
plus récent d’un pilote Linux ou de la version d’OCLP.
'''
(REPORT/'MATRICE_METAL.txt').write_text(report)
print('Reports:',len(history),'history rows;',len(metal),'Metal rows')

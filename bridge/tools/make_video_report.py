#!/usr/bin/env python3
"""Report the public video transport blocker without qualifying hardware by fallback."""
from pathlib import Path
import argparse,hashlib,json

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=root/'results/video-evidence-final')
folder=parser.parse_args().input.resolve();folder.relative_to(root/'results');manifest=json.loads((folder/'manifest.json').read_text())
lifePath=root/'results/video-probe-lifecycle.json'
if lifePath.exists():manifest['later_probe_lifecycle']=json.loads(lifePath.read_text())
assert manifest['drivers_unchanged'] and manifest['driver_before_sha256']==manifest['driver_after_sha256']
for a in manifest['source_snapshot']+manifest['runtime_snapshot']+manifest['fixtures']+manifest.get('static_artifacts',[]):
    assert hashlib.sha256((root/a['path']).read_bytes()).hexdigest()==a['sha256']
records=[]
for case in manifest['cases']:
    d=json.loads((root/case['result']).read_text());assert d['CPU_control_valid'] and d['benchmark'] is False
    assert d['auto_decode_comparison']['missing_frames']==d['auto_decode_comparison']['different_bytes']==0
    records.append({**case,'hardware_decode_advertised':bool(d['hardware_decode_supported_h264']),
                    'hardware_encode_status':d['encode_hardware']['create_status'],'GPU_selected_encode_status':d['encode_hardware_gpu']['create_status'],
                    'hardware_decode_status':d['decode_hardware']['create_status'],'auto_CPU_values_checked':d['auto_decode_comparison']['values_checked'],
                    'auto_CPU_different_bytes':d['auto_decode_comparison']['different_bytes'],'preload_loaded':d.get('preload_loaded'),
                    'hardware_decode_output_frames':d['decode_hardware'].get('output_frames',0)})
assert len(records)==6
# This report is specifically the demonstrated not-found result, never a generic
# assertion that every possible native video interface is unusable.
assert all(r['hardware_encode_status']==r['GPU_selected_encode_status']==-12908 and r['hardware_decode_status']==-12906 for r in records)
assert all(not r['hardware_decode_advertised'] and r['hardware_decode_output_frames']==0 for r in records)
assert not manifest['loader']['hardware_execution_proved']
staticCode=(folder/'VA-disassembly.stdout').read_text();assert staticCode.count('movl\t$0xe, %eax')==2
assert 'Section __text: 22' in (folder/'VA-sections.stdout').read_text()
exports={'scope':'static file disassembly; loaded code bytes not verified','text_bytes':22,'unconditional_eax_value':14}
vdaRecords=[]
for c in manifest.get('VDA_cases',[]):
    d=json.loads((root/c['result']).read_text());assert d['create_status']==-12473 and d['hardware_frames_produced'] is False
    vdaRecords.append({**c,'create_status':d['create_status'],'destination':d['destination'],'width':d['width'],'height':d['height']})
assert len(vdaRecords)>=2
first=json.loads((root/manifest['cases'][0]['result']).read_text())
encoders=[e for e in first['registered_encoders'] if e.get('CodecName')=='H.264']
ledgerPath=root/'results/hardware-coverage.json';ledger=json.loads(ledgerPath.read_text())
row=next(r for r in ledger['coverage'] if r['category']=='Video engines')
row.update({'status':'public_api_blocked',
            'tested_scope':'Six valid H264 CPU fixtures/control cases at320x240/640x480/1280x720 and process-local NVIDIA VA preload/supplemental registration; hardware-only VT encoder fails-12908 with/without required880M registryID; hardware-only decoder fails-12906; legacy VDA fails-12473 with NV12/default output; installed VA file has two unconditional eax14 stub exports and22B total text; native GPU client initialization observed, no video submission proved; automatic decode matches CPU but does not qualify hardware',
            'remaining_requirements':'Implement/qualify the existing NVIDIA VA or another user-space video transport; map actual880M decode/encode engine capabilities; output on hardware with numerical comparison, then benchmarks; no GPU video execution demonstrated and no full codec conformance',
            'evidence':['results/video-summary.json',str((folder/'manifest.json').relative_to(root)),'tools/video_engine_probe.mm','tools/video_loader_probe.mm','VIDEO.txt']})
ledger['complete']=False;ledgerPath.write_text(json.dumps(ledger,indent=2)+'\n')
summary={'collected_at':manifest['collected_at'],'cases':records,'CPU_frames':sum(c['frames'] for c in records),
         'auto_CPU_values_checked':sum(r['auto_CPU_values_checked'] for r in records),'GPU_video_executed':False,
         'public_VT_hardware_transport_blocked':True,'legacy_VDA_cases':vdaRecords,'VA_library_load_succeeded':any(r.get('preload_loaded') for r in records),'installed_VA_static_analysis':exports,'registered_H264_encoders':encoders,
         'drivers_unchanged':True,'driver_sha256':manifest['driver_after_sha256'],'performance_benchmark':False,
         'global_hardware_goal_complete':False,'coverage_updates':[row],
         'later_probe_lifecycle':manifest.get('later_probe_lifecycle'),
         'scope':'Previously completed VT and initial VDA observations; later complete reproductions did not finish; actual silicon is not declared missing and other transports remain to implement'}
(root/'results/video-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
text=f'''KEPLERMETAL — moteurs vidéo : blocage VideoToolbox démontré
Relevé : {manifest['collected_at']}

RÉSULTAT
La voie publique VideoToolbox actuelle ne permet pas de créer une session
matérielle H.264. Aucune exécution des moteurs vidéo de la GTX n’est qualifiée.
Six cas : trois résolutions320x240/640x480/1280x720 ; chargement préalable du
VA NVIDIA, enregistrement supplemental H264, puis combinaison de ces deux
options dans notre processus. Les trois variantes supplémentaires utilisent320x240.
Chaque cas possède un flux H264 Baseline valide, encodé et décodé en logiciel.

Encodage matériel exigé : -12908 (kVTCouldNotFindVideoEncoderErr), six cas.
Même erreur avec RequiredEncoderGPURegistryID de la GTX880M, six autres essais.
Décodage matériel exigé : -12906 (kVTCouldNotFindVideoDecoderErr), six cas.
Ces codes concernent l’absence d’un composant sélectionnable par cette API,
pas un diagnostic de panne du GPU ; les codes ressource temporairement indisponible
sont différents. La cause exacte de la non-sélection n’est pas établie.
VTIsHardwareDecodeSupported(H264) retourne0, ainsi queHEVC (déclaration seule).
Le seul encodeur H264 enregistré est Apple H.264(SW), ID
com.apple.videotoolbox.videoencoder.h264.

TÉMOINS ET PREUVE LIMITÉE
{summary['CPU_frames']} images CPU encodées, puis décodées ; {summary['auto_CPU_values_checked']} octets NV12 actifs
du décodage automatique comparés aux mêmes flux décodés avec hardware désactivé :
aucune différence. Les trois modes matériels ne produisent aucune image.
Le test ne compare pas un codec avec pertes à l’image source non compressée.
La propriété UsingHardwareAcceleratedVideoEncoder/Decoder renvoie-12900 dans
les sessions logicielles/automatiques ; ce retour n’est pas traité comme une preuve GPU.
UsingGPURegistryID nul peut désigner un codec logiciel ou un GPU intégré :
ce champ seul n’est pas une preuve. Le SDK réserve la sélection explicite du
GPU de décodage aux eGPU ; elle n’est pas utilisée pour fabriquer ce blocage.
Le mode hardware-only sans ID explicite échoue également.

Le composant utilisateur GeForceVADriver16.0.0 (version courte16.0.14) existe
et dlopen(RTLD_NOW|RTLD_LOCAL) réussit, avec AppleGVA chargé. Aucun appel aux
deux exports propriétaires AVD_CreateAVDAccelerator/AVD_DestroyAVDAccelerator
n’a été effectué directement par nos sondes : leur contrat reste à établir.
Charger la bibliothèque n’est pas exécuter un codec sur le GPU.
Le préchargement ne résout pas l’erreur.
La seule carte de classe PCI display observée est10de:1198, GTX880M.

VDA ET COMPOSANT VA INCOMPLET
L’ancienne API publique VDADecoderCreate échoue également : -12473
(kVDADecoderDecoderFailedErr), deux appels initiaux320x240 avec la même fixture
valide et deux préférences de sortie, NV12 explicite/format natif par défaut.
Les variantes preload/registration VideoToolbox ne sont pas revendiquées pour VDA.
L’empreinte du binaire VDA n’a pas été capturée à l’instant de ces deux exécutions ;
son source n’a pas changé. L’archive VT, elle, fige bien ses exécutables utilisés.
Le SDK distingue ce code d’un format ou d’une configuration invalide ; la couche
décodeur peut aussi le retourner pour une indisponibilité de ressources. Son
origine précise n’est pas démontrée par le seul code. Aucune frame GPU produite.

Une trace de notre processus VDA observe IOSurfaceRoot, puis nvAccelerator
clients5 et6 et le mapping5 de4384B. Cette initialisation ne prouve pas la
soumission d’un décodage. L’erreur IOSurface selector44 figure aussi dans nos
traces Metal réussies ; elle n’est pas retenue seule comme cause du blocage.
Trace : VDA-iokit.jsonl ; inputs publics inchangés, aucune commande rejouée.

Le désassemblage entier de GeForceVADriver contient22B de __text :
AVD_CreateAVDAccelerator et AVD_DestroyAVDAccelerator,11B chacune :
  push rbp ; mov rsp,rbp ; mov eax,14 ; pop rbp ; ret
Ces deux exports du fichier installé sont des stubs à retour constant, sans
lecture de paramètres ni appel de calcul/allocation. Leurs octets dans le fichier
sont554889e5b80e0000005dc3. Les octets en mémoire n’ont pas été vérifiés.
Cette implémentation ne fournit pas un accélérateur par ces deux entrypoints.
La valeur privée14 n’est pas assimilée à un code public sans connaître son ABI.
Le fait que VDA atteigne précisément ce factory n’a pas été établi dynamiquement :
LLDB est resté en attente dans task_for_pid, avant exécution, puis a été arrêté.
Les processus de cette tentative ont été libérés ; aucune protection changée.
L’inspection statique et le retour des API sont des preuves distinctes.

HARDWARE ET PILE macOS
NVIDIA documente NVENC sur la génération Kepler et l’encodage H2644208bit.
Ce document décrit les capacités physiques par génération ; il ne valide pas
ce transport macOS. L’échec VideoToolbox ne démontre pas l’absence de NVENC.
GeForceVADriver est une piste pour le décodage ; ses deux noms d’exports
n’établissent ni son ABI complète ni l’existence d’un accès NVENC par cette voie.
Les moteurs physiques, autres codecs, flux interlaced et limites restent à qualifier.
Les temps diagnostic_wall_ms sont des observations uniques, sans échauffement
ni essais répétés : aucun gain de débit ou d’usage CPU n’est annoncé.

REPRODUCTION DEPUIS bridge
python3 tools/reproduce_video.py --skip-loader --out results/video-reproduction
python3 tools/make_video_report.py --input results/video-reproduction
Commandes exactes des six cas VT terminés, paramètres, versions Xcode/macOS :
results/video-final/commands.json
Sources/exécutables figés, bitstreams AVCC avec SPS/PPS et empreintes :
{folder.relative_to(root)}/manifest.json
Les contrôles CPU peuvent retourner0 tout en constatant un blocage matériel ;
ce code de sortie n’est jamais utilisé comme qualification des moteurs GPU.
Les dernières tentatives complètes n’ont pas terminé. L’assemblage publié réunit
les observations antérieures terminées et le désassemblage statique vérifié.
Les commandes de reproduction ci-dessus sont une recette pour après résolution
de l’incident ; le script refuse de lancer de nouvelles sondes tant que les
processus précédents sont encore présents (état recontrôlé avecps).

INCIDENT DE DIAGNOSTIC
La lecture des octets chargés n’a pas terminé. Le processus vidéo_loader_probe
20575 reste en état noyauU malgréSIGKILL ; une tentative ensuite configurée
sans cette observation a également laissé video_engine_probe20903 enU.
Les processus Python parents ont été terminés (retours143). Les deux enfants
restaient présents lors du dernier contrôle : results/video-probe-lifecycle.json.
La cause est inconnue ; aucune panne GPU/RAM ni rejet d’autorisation n’est
déduit de ce seul état. La question sur une éventuelle fenêtre macOS reste
ouverte. Aucune protection système n’a été changée pour forcer leur exécution.

Aucun pilote système, OCLP, protection, VBIOS, fréquence ou registre modifié.
Empreintes avant/après inchangées :
'''
for path,digest in manifest['driver_after_sha256'].items():text+=path+'\nSHA256 '+digest+'\n'
text+='''
Le but global reste ouvert. Prochaine exigence vidéo : raccordement du transport
VA NVIDIA ou d’une autre voie dont l’ABI serait établie, avant toute qualification
ou benchmark du moteur. Les autres fonctionnalités GPU restent poursuivables.

Sources primaires : SDK Xcode26.3/26.2, VTErrors.h, VTDecompressionProperties.h,
VTCompressionProperties.h et VTUtilities.h ; contrat public en ligne :
https://developer.apple.com/documentation/VideoToolbox/kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder
https://developer.apple.com/documentation/videotoolbox/kvtvideoencoderspecification_requirehardwareacceleratedvideoencoder
NVIDIA, tableNVENC Kepler :
https://docscontent.nvidia.com/dita/00000186-1a2d-d34f-a596-3f2d10d50000/video-codec-sdk/11.0/pdf/NVENC_Application_Note.pdf
'''
if manifest.get('later_probe_lifecycle',{}).get('CPU_tool_also_affected'):
    text+='\nDERNIER ÉTAT : rustc --version PID21115 est également enU malgréSIGKILL.\n'
    text+='Ce symptôme dépasse les sondes vidéo ; sa cause reste inconnue.\n'
    text+='Versions des outils conservées avec leur date ; empreintes rafraîchies\n'
    text+='sans lancer de binaires natifs, avec provenance.py --hash-only.\n'
(root/'VIDEO.txt').write_text(text);print('Recorded public VT hardware blocker, valid CPU controls, unchanged drivers')

#!/usr/bin/env python3
"""Local compiler-only Darwin build. No Linux transport or GPU runtime stubs."""
from pathlib import Path
import difflib
import tarfile
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
MESA = ROOT / 'vendor/mesa-26.2.4'
ARCHIVE = ROOT / 'vendor/mesa-26.2.4.tar.xz'
EXPECTED = 'bce5f7fbebb934373b86c999a064d52fb5065878dc57f287f95346648ec832e9'
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED
changes = {
    'meson.build': [
        ('  with_nouveau_vk, with_imagination_vk,',
         '  # KeplerMetal: offline NAK only; do not build NVK OpenCL helpers.\n  with_imagination_vk,'),
        ("elif with_nouveau_vk\n  error('NVK requires libelf')",
         "elif with_nouveau_vk and host_machine.system() != 'darwin'\n  error('NVK requires libelf')"),
    ],
    'src/nouveau/meson.build': [
        ("subdir('drm')\nsubdir('winsys')",
         "if host_machine.system() != 'darwin'\n  subdir('drm')\n  subdir('winsys')\nelse\n  # Compiler-only build: no DRM implementation and no fake GPU transport.\n  idep_nouveau_ws = null_dep\nendif"),
        ("if with_nouveau_vk\n  subdir('cubin')",
         "if with_nouveau_vk and host_machine.system() != 'darwin'\n  subdir('cubin')"),
    ],
    'src/nouveau/compiler/nak_bindings.h': [
        ('#include "nouveau_bo.h"\n#include "nouveau_context.h"\n#include "nouveau_device.h"\n\n#include <xf86drm.h>\n#include "drm-uapi/nouveau_drm.h"\n\n#define DRM_RS_IOCTL(FOO) \\\n   DRM_RS_IOCTL_##FOO = DRM_IOCTL_##FOO\n\nenum ENUM_PACKED drm_rs_ioctls {\n   DRM_RS_IOCTL(NOUVEAU_EXEC),\n};',
         '/* KeplerMetal: hardware-test bindings excluded in this offline build.\n * The shader compiler has no DRM dependency; cfg(test) hw_runner does. */'),
    ],
}
patch = []
provenance = []
with tarfile.open(ARCHIVE, 'r:xz') as archive:
    for relative, substitutions in changes.items():
        original = archive.extractfile('mesa-26.2.4/' + relative).read().decode()
        updated = original
        for before, after in substitutions:
            if updated.count(before) != 1:
                raise RuntimeError('Expected one match in ' + relative)
            updated = updated.replace(before, after)
        (MESA / relative).write_text(updated)
        patch.extend(difflib.unified_diff(original.splitlines(True), updated.splitlines(True),
                     fromfile='a/' + relative, tofile='b/' + relative))
        provenance.append({'path': relative,
                           'upstream_sha256': hashlib.sha256(original.encode()).hexdigest(),
                           'modified_sha256': hashlib.sha256(updated.encode()).hexdigest()})
(ROOT / 'src/mesa-26.2.4-darwin-compiler-only.patch').write_text(''.join(patch))
(ROOT / 'results/mesa-local-changes.json').write_text(json.dumps(provenance, indent=2) + '\n')
print('Prepared offline NAK build; no ISA transformations changed.')

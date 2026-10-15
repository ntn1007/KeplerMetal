#!/usr/bin/env python3
"""Make parser directives compatible with Xcode's Bison 2.3; ISA untouched."""
from pathlib import Path
import tarfile
import re
import difflib
import hashlib
import json

root = Path(__file__).resolve().parents[1]
name = 'envytools-f102b82381f3f11cee113d16374c87091db039d9'
with tarfile.open(root/'vendor'/(name+'.tar.gz')) as archive:
    original = archive.extractfile(name+'/easm/easm_parse.y').read().decode()
updated = original.replace('%define api.pure\n','%pure-parser\n').replace('%name-prefix "easm_"','%name-prefix="easm_"')
symbols = {}
for match in re.finditer(r'^%(?:type|token) <([^>]+)> (.*)$', original, re.MULTILINE):
    symbols.setdefault(match[1], []).extend(match[2].split())
def expand_destructor(match):
    return match[1] + ' '.join(symbols[match[2]])
updated = re.sub(r'^(%destructor .*? )<([^>]+)>$', expand_destructor, updated, flags=re.MULTILINE)
(root/'vendor'/name/'easm/easm_parse.y').write_text(updated)
(root/'src/envytools-bison23.patch').write_text(''.join(difflib.unified_diff(
    original.splitlines(True), updated.splitlines(True), fromfile='a/easm/easm_parse.y', tofile='b/easm/easm_parse.y')))
(root/'results/envytools-local-change.json').write_text(json.dumps({
    'path':'easm/easm_parse.y', 'upstream_sha256':hashlib.sha256(original.encode()).hexdigest(),
    'modified_sha256':hashlib.sha256(updated.encode()).hexdigest(),
    'reason':'Equivalent pure/prefix and symbol-destructor declarations for Bison 2.3; ISA unchanged',
},indent=2)+'\n')

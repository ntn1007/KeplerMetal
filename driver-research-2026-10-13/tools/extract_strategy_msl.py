#!/usr/bin/env python3
"""Extract selected official MSL evidence; requires the bundled pypdf runtime."""
from pathlib import Path
import json
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1] / 'sources/strategy'
reader = PdfReader(root / 'Metal-Shading-Language-Specification.pdf')
terms = ['atomic_compare_exchange_weak_explicit', 'simd_shuffle', 'simd_sum']
matches = []
for index, page in enumerate(reader.pages):
    text = page.extract_text()
    snippets = []
    for term in terms:
        position = text.find(term)
        if position >= 0:
            snippets.append({'term': term, 'text': text[max(0, position - 350):position + 2100]})
    if snippets:
        matches.append({'pdf_page': index + 1, 'snippets': snippets})
result = {'pages': len(reader.pages),
          'metadata': {str(key): str(value) for key, value in reader.metadata.items()},
          'matches': matches}
(root / 'msl-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'pages': len(reader.pages), 'matching_pages': [m['pdf_page'] for m in matches]}))

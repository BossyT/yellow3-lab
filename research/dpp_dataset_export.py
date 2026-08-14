#!/usr/bin/env python3
"""
Publish the DPP Supplier Register as a citable dataset.

WHY. The register is the rarest thing yellow3 owns - original measurement of a
market nobody else has counted - and it was published only as a JavaScript
directory. Datasets get cited; applications get bounced. An assistant asked "how
many DPP suppliers are there in the EU" cannot name a source it could not read,
and a journalist cannot check a number they cannot download.

WHAT THIS WRITES, from research/dpp-suppliers.json, which is already the
register's source of truth:

    /research/digital-product-passport/suppliers.csv    every organisation
    /research/digital-product-passport/suppliers.json   the same, plus counts,
                                                        licence and citation

THE LICENCE IS THE POINT. CC BY 4.0 requires attribution, which is exactly what
a register wants: reuse is welcome, and the reuse has to say where it came from.

Fields are published as measured. Blank stays blank - an unknown headquarters
country is published as an empty cell, never as a guess, because the register's
whole claim is that it does not invent what it could not establish.

    python3 research/dpp_dataset_export.py
"""
import csv, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / 'research' / 'dpp-suppliers.json'
OUT_DIR = ROOT / 'research' / 'digital-product-passport'

LICENCE = 'CC BY 4.0'
LICENCE_URL = 'https://creativecommons.org/licenses/by/4.0/'
LANDING = 'https://www.yellow3.io/research/digital-product-passport/suppliers'

# Published in this order: identity first, then where it is, then what it is,
# then how we know. The last three columns are the register's honesty - what the
# claim rests on, when it was checked, and how sure we are.
COLUMNS = [
    'id', 'name', 'website', 'domain', 'hq_country', 'hq_city', 'entity_type',
    'sectors', 'founded_year', 'ownership', 'funding_stage',
    'total_disclosed_funding', 'last_funding_date', 'status',
    'evidence_url', 'source', 'source_date', 'confidence',
]

def main() -> int:
    data = json.loads(SRC.read_text(encoding='utf-8'))
    rows = data['suppliers']
    generated = data.get('generated', '')
    counts = data.get('counts', {})

    citation = (f'yellow3 lab, DPP Supplier Register, {LANDING}, '
                f'data generated {generated}, accessed YYYY-MM-DD')

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUT_DIR / 'suppliers.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({c: (r.get(c) if r.get(c) is not None else '') for c in COLUMNS})

    json_path = OUT_DIR / 'suppliers.json'
    json_path.write_text(json.dumps({
        'name': 'DPP Supplier Register',
        'description': (
            'An independent public register of organisations offering Digital '
            'Product Passport capability. Compiled and maintained by yellow3 lab '
            'from public sources. Suppliers cannot pay to appear, to rank higher, '
            'or to change an assessment.'),
        'publisher': 'yellow3 lab ApS, Copenhagen, Denmark',
        'landing_page': LANDING,
        'licence': LICENCE,
        'licence_url': LICENCE_URL,
        'citation': citation,
        'generated': generated,
        'record_count': len(rows),
        'counts': counts,
        'field_notes': {
            'blank_values': 'Published as measured. A blank cell means the '
                            'register could not establish the value from a '
                            'public source, and is never a guess.',
            'confidence': 'How firmly the record is established by its source.',
            'source_date': 'When the record was last checked against its source.',
        },
        'suppliers': rows,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'\n  {len(rows)} organisations')
    print(f'  {csv_path.relative_to(ROOT)}   {csv_path.stat().st_size // 1024} KB')
    print(f'  {json_path.relative_to(ROOT)}  {json_path.stat().st_size // 1024} KB')
    print(f'  licence: {LICENCE}')
    print(f'  citation: {citation}\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())

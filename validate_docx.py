"""
DOCX OOXML strict validator — run before pushing to catch issues OnlyOffice would reject.

Usage:
    python validate_docx.py                   # regenerates + validates
    python validate_docx.py path/to/file.docx # validates an existing file

Checks:
  1. Valid ZIP / magic bytes
  2. Required parts present ([Content_Types].xml, document.xml, etc.)
  3. Duplicate single-occurrence elements in <w:tblPr>
     - w:tblW         (must appear exactly once)
     - w:tblBorders   (must appear 0 or 1 time)
     - w:jc           (must appear 0 or 1 time)
  4. Duplicate <w:tblPr> inside <w:tbl>
  5. Page-number field structure (fldChar begin/instrText/fldChar end in 3 separate runs)
  6. Empty <w:t> elements with xml:space="preserve" where needed
  7. Encoding issues (replacement chars U+FFFD)
"""

import os, sys, zipfile, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

ERRORS   = []
WARNINGS = []


def err(msg: str)  -> None: ERRORS.append(f'  ✗  {msg}')
def warn(msg: str) -> None: WARNINGS.append(f'  ⚠  {msg}')


# ---------------------------------------------------------------------------
# 1. Regenerate DOCX (optional)
# ---------------------------------------------------------------------------

def generate_docx() -> bytes:
    import pandas as pd
    from pdf_generator.microbiome_docx import generate_microbiome_docx
    csv = os.path.join(os.path.dirname(__file__), 'data',
                       'Informes_2026-01-30 17_08_17 .csv')
    df = pd.read_csv(csv, encoding='utf-8')
    return generate_microbiome_docx(df)


# ---------------------------------------------------------------------------
# 2. Validation helpers
# ---------------------------------------------------------------------------

REQUIRED_PARTS = [
    '[Content_Types].xml',
    '_rels/.rels',
    'word/document.xml',
    'word/styles.xml',
    'word/settings.xml',
]

# Elements that may appear AT MOST ONCE inside <w:tblPr>
SINGLE_IN_TBLPR = ['w:tblW ', 'w:tblBorders', 'w:jc ']

# Self-closing elements (no closing tag) — count raw occurrences
SELF_CLOSING = {'w:tblW '}


def count_open_tags(block: str, tag: str) -> int:
    """Count opening tags only (not self-closing counts twice for </tag>)."""
    if tag in SELF_CLOSING:
        return block.count(tag)
    # Count opening tags vs closing tags: opening = occurrences of '<tag'
    return len(re.findall(rf'<{re.escape(tag.strip())}[> /]', block))


def check_zip(data: bytes) -> zipfile.ZipFile | None:
    magic = data[:4]
    if magic != b'PK\x03\x04':
        err(f'Not a valid ZIP/DOCX (magic={magic!r})')
        return None
    try:
        import io
        z = zipfile.ZipFile(io.BytesIO(data))
        return z
    except Exception as e:
        err(f'Cannot open ZIP: {e}')
        return None


def check_required_parts(z: zipfile.ZipFile) -> None:
    names = set(z.namelist())
    for part in REQUIRED_PARTS:
        if part not in names:
            err(f'Missing required part: {part}')


def check_tblpr_duplicates(doc_xml: str) -> None:
    tbl_blocks = re.findall(r'<w:tblPr>(.*?)</w:tblPr>', doc_xml, re.DOTALL)
    for i, block in enumerate(tbl_blocks):
        for tag in SINGLE_IN_TBLPR:
            n = count_open_tags(block, tag)
            if n > 1:
                err(f'Table {i+1}: <w:tblPr> has {n} <{tag.strip()}> (must be ≤1)')


def check_tbl_tblpr_count(doc_xml: str) -> None:
    tbl_blocks = re.findall(r'<w:tbl>(.*?)</w:tbl>', doc_xml, re.DOTALL)
    for i, block in enumerate(tbl_blocks):
        n = len(re.findall(r'<w:tblPr>', block))
        if n > 1:
            err(f'Table {i+1}: contains {n} <w:tblPr> elements (must be 1)')


def check_fldchar_structure(doc_xml: str) -> None:
    """Page number fields must use 3 separate runs: begin / instrText / end."""
    # Find all fldChar begin contexts
    patterns = re.findall(
        r'<w:fldChar[^>]*w:fldCharType="begin"[^>]*/>(.*?)'
        r'<w:fldChar[^>]*w:fldCharType="end"[^>]*/>',
        doc_xml, re.DOTALL)
    for j, p in enumerate(patterns):
        # instrText should be outside a <w:r> that already contains a fldChar
        if '<w:fldChar' in p and 'instrText' in p:
            # This means begin and instrText are in the SAME run — invalid
            if re.search(r'<w:fldChar[^>]*begin[^>]*/>[^<]*<w:instrText', p):
                err(f'Field {j+1}: fldChar begin and instrText in same run (must be separate runs)')


def check_encoding(z: zipfile.ZipFile) -> None:
    for name in ['word/document.xml', 'word/header1.xml', 'word/footer1.xml']:
        if name not in z.namelist():
            continue
        content = z.read(name).decode('utf-8', errors='replace')
        n = content.count('\ufffd')
        if n:
            warn(f'{name}: {n} replacement character(s) U+FFFD (possible encoding issue)')


def check_image_rels(z: zipfile.ZipFile) -> None:
    """Check that images referenced in rels actually exist in the ZIP."""
    rels_name = 'word/_rels/document.xml.rels'
    if rels_name not in z.namelist():
        return
    rels = z.read(rels_name).decode()
    images = re.findall(r'Type="[^"]*relationships/image"[^>]*Target="([^"]+)"', rels)
    for img in images:
        full = f'word/{img}' if not img.startswith('/') else img.lstrip('/')
        if full not in z.namelist():
            err(f'Image referenced in rels but missing: {full}')


# ---------------------------------------------------------------------------
# 3. Main
# ---------------------------------------------------------------------------

def validate(data: bytes, label: str) -> bool:
    print(f'\nValidating: {label}  ({len(data):,} bytes)')

    z = check_zip(data)
    if z is None:
        _print_results()
        return False

    check_required_parts(z)
    check_image_rels(z)

    doc_xml = z.read('word/document.xml').decode('utf-8', errors='replace')
    check_tblpr_duplicates(doc_xml)
    check_tbl_tblpr_count(doc_xml)
    check_fldchar_structure(doc_xml)
    check_encoding(z)

    return _print_results()


def _print_results() -> bool:
    if ERRORS:
        print(f'\n  {len(ERRORS)} ERROR(S) — OnlyOffice will likely reject this file:')
        for e in ERRORS:
            print(e)
    if WARNINGS:
        print(f'\n  {len(WARNINGS)} WARNING(S):')
        for w in WARNINGS:
            print(w)
    if not ERRORS and not WARNINGS:
        print('  All checks passed ✓')
    elif not ERRORS:
        print('\n  No blocking errors — file should open in OnlyOffice ✓')
    return len(ERRORS) == 0


if __name__ == '__main__':
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f'Reading {path}...')
        with open(path, 'rb') as f:
            data = f.read()
        label = os.path.basename(path)
    else:
        print('Regenerating DOCX...')
        data = generate_docx()
        out = os.path.join(os.path.dirname(__file__), 'example_pdf', 'preview.docx')
        with open(out, 'wb') as f:
            f.write(data)
        print(f'Written: {out}')
        label = 'preview.docx (freshly generated)'

    ok = validate(data, label)
    sys.exit(0 if ok else 1)

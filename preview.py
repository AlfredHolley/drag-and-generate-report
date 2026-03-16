"""
Quick preview helper – run from the project root:

    python preview.py

Reads  data/Informes_2026-01-30 17_08_17 .csv
Writes preview.pdf  (overwrites each time)
Then opens it with the default PDF viewer.
"""

import os
import sys
import pandas as pd

# Make sure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from pdf_generator.microbiome_pdf import MicrobiomePDFGenerator  # noqa: E402

CSV_PATH = os.path.join(os.path.dirname(__file__), 'data',
                        'Informes_2026-01-30 17_08_17 .csv')
OUT_PATH  = os.path.join(os.path.dirname(__file__), 'example_pdf', 'preview.pdf')


def main() -> None:
    print(f"Reading  : {CSV_PATH}")
    df = pd.read_csv(CSV_PATH, encoding='utf-8')

    print("Generating PDF…")
    pdf_bytes = MicrobiomePDFGenerator(df).generate()

    with open(OUT_PATH, 'wb') as fh:
        fh.write(pdf_bytes)

    print(f"Written  : {OUT_PATH}  ({len(pdf_bytes):,} bytes)")



if __name__ == '__main__':
    main()

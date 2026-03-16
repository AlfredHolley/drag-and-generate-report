"""
Analyze PDF structure to understand table layout
"""

import pdfplumber
from pathlib import Path
import json

pdf_path = Path("data/pdfs/InformeResultados_21_01_2026 13_25_54 - 700080.pdf")

with pdfplumber.open(pdf_path) as pdf:
    with open('pdf_structure.txt', 'w', encoding='utf-8') as f:
        for i, page in enumerate(pdf.pages[:5], 1):
            f.write(f"\n{'='*80}\n")
            f.write(f"PAGE {i}\n")
            f.write(f"{'='*80}\n\n")

            # Extract text
            try:
                text = page.extract_text()
                f.write("TEXT CONTENT:\n")
                f.write("-" * 80 + "\n")
                f.write(text if text else "No text extracted")
                f.write("\n\n")
            except Exception as e:
                f.write(f"Error extracting text: {e}\n\n")

            # Extract tables
            try:
                tables = page.extract_tables()
                f.write(f"\nTABLES FOUND: {len(tables)}\n")
                f.write("-" * 80 + "\n")

                for j, table in enumerate(tables, 1):
                    f.write(f"\nTable {j} ({len(table)} rows):\n")
                    for row_idx, row in enumerate(table[:10], 1):  # First 10 rows
                        f.write(f"  Row {row_idx}: {row}\n")
                    if len(table) > 10:
                        f.write(f"  ... ({len(table) - 10} more rows)\n")
                    f.write("\n")

            except Exception as e:
                f.write(f"Error extracting tables: {e}\n\n")

print("Analysis complete! Check pdf_structure.txt")

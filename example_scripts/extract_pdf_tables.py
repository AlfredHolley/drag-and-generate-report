"""
Extract medical test data from PDF reports using table extraction
"""

import pdfplumber
import pandas as pd
import os
from pathlib import Path
import re


def clean_value(value):
    """Clean and standardize cell values"""
    if value is None:
        return None
    value = str(value).strip()
    if value == '' or value == 'None':
        return None
    return value


def extract_numeric(text):
    """Extract numeric value from text"""
    if not text:
        return None

    text = str(text).replace(',', '.').strip()

    # Remove < or > signs
    text = re.sub(r'[<>]', '', text)

    # Extract first number
    match = re.search(r'\d+\.?\d*', text)
    if match:
        try:
            return float(match.group())
        except:
            return None
    return None


def parse_range(range_text):
    """Parse reference range to get min and max"""
    if not range_text:
        return None, None

    range_text = str(range_text).replace(',', '.').strip()

    # Pattern: "min - max" or "min-max"
    match = re.search(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)', range_text)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except:
            pass

    # Pattern: "< value"
    if '<' in range_text:
        val = extract_numeric(range_text)
        return None, val

    # Pattern: "> value"
    if '>' in range_text:
        val = extract_numeric(range_text)
        return val, None

    return None, None


def extract_tables_from_pdf(pdf_path):
    """Extract all tables from PDF and convert to structured data"""
    all_data = []
    current_category = "General"

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Extract all tables from this page
            tables = page.extract_tables()

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Try to identify header row
                header_found = False
                data_start_idx = 0

                for i, row in enumerate(table):
                    if row and any(cell for cell in row if cell):
                        # Check if this looks like a header
                        row_text = ' '.join([str(c) for c in row if c]).upper()
                        if 'PARAMETER' in row_text or 'TEST' in row_text or 'RESULT' in row_text:
                            header_found = True
                            data_start_idx = i + 1
                            break

                if not header_found:
                    data_start_idx = 0

                # Process data rows
                for row in table[data_start_idx:]:
                    if not row or not any(cell for cell in row if cell):
                        continue

                    # Clean row
                    cleaned_row = [clean_value(cell) for cell in row]

                    # Skip empty rows
                    if not any(cleaned_row):
                        continue

                    # Check if this is a category header (e.g., "Haematology", "Biochemistry")
                    first_cell = cleaned_row[0] if cleaned_row else None
                    if first_cell:
                        first_text = first_cell.upper()
                        if any(cat in first_text for cat in ['HAEMATOLOGY', 'BIOCHEMISTRY', 'IMMUNOLOGY',
                                                               'HORMONES', 'URINE', 'GENERAL']):
                            current_category = first_cell
                            continue

                    # Try to extract parameter data
                    # Expected format: Parameter | Value | Unit | Reference Range | ...
                    if len(cleaned_row) >= 3:
                        parameter = cleaned_row[0]

                        # Skip if parameter is empty or looks like a header
                        if not parameter or any(h in parameter.upper() for h in ['PARAMETER', 'TEST', 'UNITS', 'REFERENCE']):
                            continue

                        # Find value and reference columns
                        value_col = None
                        ref_col = None

                        for idx, cell in enumerate(cleaned_row[1:], 1):
                            if cell and extract_numeric(cell) is not None:
                                if value_col is None:
                                    value_col = idx
                                elif '-' in cell or '>' in cell or '<' in cell:
                                    ref_col = idx

                        # Extract value
                        value = None
                        if value_col:
                            value = extract_numeric(cleaned_row[value_col])

                        # Extract reference range
                        range_min, range_max = None, None
                        if ref_col and ref_col < len(cleaned_row):
                            range_min, range_max = parse_range(cleaned_row[ref_col])

                        # Try to find reference range in other columns if not found
                        if range_min is None and range_max is None:
                            for cell in cleaned_row[2:]:
                                if cell and ('-' in cell or '<' in cell or '>' in cell):
                                    range_min, range_max = parse_range(cell)
                                    if range_min is not None or range_max is not None:
                                        break

                        # Add data if we have at least a parameter name and value
                        if parameter and value is not None:
                            all_data.append({
                                'category': current_category,
                                'parameter': parameter,
                                'value': value,
                                'rangeMin': range_min,
                                'rangeMax': range_max
                            })

    return all_data


def process_all_pdfs(pdf_dir, output_dir):
    """Process all PDFs and create CSV files"""
    pdf_dir = Path(pdf_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_dir.glob('*.pdf'))

    total_files = len(pdf_files)
    successful = 0

    for i, pdf_file in enumerate(pdf_files, 1):
        try:
            # Extract data
            data = extract_tables_from_pdf(pdf_file)

            if data:
                # Create DataFrame
                df = pd.DataFrame(data)

                # Create CSV filename
                csv_name = pdf_file.stem + '.csv'
                csv_path = output_dir / csv_name

                # Save to CSV
                df.to_csv(csv_path, index=False, encoding='utf-8')
                successful += 1

        except Exception as e:
            pass

    return successful, total_files


def main():
    """Main function"""
    pdf_directory = "data/pdfs"
    output_directory = "data/csv_extracted"

    successful, total = process_all_pdfs(pdf_directory, output_directory)


if __name__ == "__main__":
    main()

"""
Extract medical test data from PDF reports and create CSV datasets
"""

import pdfplumber
import re
import pandas as pd
import os
from pathlib import Path


def extract_numeric_value(text):
    """Extract numeric value from text, handling ranges and special cases"""
    if not text or text.strip() == '':
        return None

    # Remove commas and convert to float
    text = text.strip().replace(',', '.')

    # Handle ranges (take first value)
    if '-' in text:
        parts = text.split('-')
        text = parts[0].strip()

    # Handle less than / greater than
    text = text.replace('<', '').replace('>', '').strip()

    try:
        return float(text)
    except:
        return None


def parse_reference_range(range_text):
    """Parse reference range to get min and max values"""
    if not range_text or range_text.strip() == '':
        return None, None

    range_text = range_text.strip().replace(',', '.')

    # Pattern: "min - max"
    match = re.search(r'([\d.]+)\s*-\s*([\d.]+)', range_text)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except:
            pass

    # Pattern: "< value" or "> value"
    match = re.search(r'[<>]\s*([\d.]+)', range_text)
    if match:
        try:
            value = float(match.group(1))
            if '<' in range_text:
                return None, value
            else:
                return value, None
        except:
            pass

    return None, None


def extract_data_from_pdf(pdf_path):
    """Extract all test data from a PDF report"""
    data = []
    current_category = "Unknown"
    current_subcategory = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')

            for i, line in enumerate(lines):
                line = line.strip()

                # Skip empty lines
                if not line:
                    continue

                # Detect main categories
                if 'Haematology' in line or 'haematology' in line:
                    current_category = "Haematology"
                    current_subcategory = None
                elif 'Biochemistry' in line or 'biochemistry' in line:
                    current_category = "Biochemistry"
                    current_subcategory = None
                elif 'Immunology' in line or 'immunology' in line:
                    current_category = "Immunology"
                    current_subcategory = None
                elif 'Hormones' in line or 'hormones' in line:
                    current_category = "Hormones"
                    current_subcategory = None
                elif 'Urine' in line or 'urine' in line or 'URINE' in line:
                    current_category = "Urine"
                    current_subcategory = None

                # Detect subcategories
                subcategory_patterns = [
                    'Hydrocarbon metabolism', 'Lipid metabolism', 'Proteins',
                    'Renal function tests', 'Ions', 'Liver function tests',
                    'Iron metabolism', 'Phosphocalcic metabolism', 'Vitamins',
                    'Antibodies', 'Thyroid', 'Sexual hormones', 'Adrenal hormones'
                ]

                for pattern in subcategory_patterns:
                    if pattern.lower() in line.lower():
                        current_subcategory = pattern
                        break

                # Try to extract parameter data
                # Pattern: parameter name, value, unit, reference range
                # Look for lines with numbers and reference ranges
                if re.search(r'\d+[.,]\d+', line) or re.search(r'\d+\s*-\s*\d+', line):
                    # Try to split the line into components
                    parts = re.split(r'\s{2,}', line)  # Split on multiple spaces

                    if len(parts) >= 3:
                        parameter = parts[0].strip()

                        # Skip header lines
                        if any(header in parameter.upper() for header in ['PARAMETER', 'TEST', 'REFERENCE', 'UNITS', 'VALUE']):
                            continue

                        # Try to find value, unit, and reference range
                        value_text = None
                        unit = None
                        range_text = None

                        for j, part in enumerate(parts[1:], 1):
                            # Check if this part contains a reference range (min - max)
                            if re.search(r'\d+[.,]?\d*\s*-\s*\d+[.,]?\d*', part):
                                range_text = part
                            # Check if this part is a numeric value
                            elif re.search(r'^[<>]?\s*\d+[.,]?\d*$', part.strip()):
                                if value_text is None:
                                    value_text = part
                            # Otherwise it might be a unit or part of parameter name
                            elif value_text and not unit and not any(c.isdigit() for c in part):
                                unit = part

                        # Extract numeric value
                        value = extract_numeric_value(value_text) if value_text else None

                        # Extract reference range
                        range_min, range_max = parse_reference_range(range_text) if range_text else (None, None)

                        # Only add if we have at least a value
                        if value is not None or (range_min is not None or range_max is not None):
                            category_full = current_category
                            if current_subcategory:
                                category_full = f"{current_category} - {current_subcategory}"

                            data.append({
                                'category': category_full,
                                'parameter': parameter,
                                'value': value,
                                'unit': unit,
                                'rangeMin': range_min,
                                'rangeMax': range_max
                            })

    return data


def process_all_pdfs(pdf_dir, output_dir):
    """Process all PDFs in a directory and create CSV files"""
    pdf_dir = Path(pdf_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(pdf_dir.glob('*.pdf'))
    print(f"Found {len(pdf_files)} PDF files to process")

    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")

        try:
            # Extract data from PDF
            data = extract_data_from_pdf(pdf_file)

            if data:
                # Create DataFrame
                df = pd.DataFrame(data)

                # Create CSV filename based on PDF name
                csv_name = pdf_file.stem + '.csv'
                csv_path = output_dir / csv_name

                # Save to CSV
                df.to_csv(csv_path, index=False)
                print(f"  [OK] Extracted {len(data)} records -> {csv_name}")
            else:
                print(f"  [WARNING] No data extracted from {pdf_file.name}")

        except Exception as e:
            print(f"  [ERROR] Error processing {pdf_file.name}: {e}")


def main():
    """Main function"""
    pdf_directory = "data/pdfs"
    output_directory = "data/csv_extracted"

    print("=" * 60)
    print("PDF Medical Data Extractor")
    print("=" * 60)

    process_all_pdfs(pdf_directory, output_directory)

    print("\n" + "=" * 60)
    print("Extraction complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

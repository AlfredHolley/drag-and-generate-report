"""
Generate a single PDF report for a given fake_id and patient name.

Usage:
    python generate_single_report.py <fake_id> <patient_name>

Example:
    python generate_single_report.py 831458 "John Smith"
"""

import sys
from pdf_generator import PDFReportGenerator


def main():
    if len(sys.argv) < 3:
        print("Usage: python generate_single_report.py <fake_id> <patient_name>")
        sys.exit(1)

    fake_id = int(sys.argv[1])
    patient_name = sys.argv[2]

    generator = PDFReportGenerator(
        data_path="data/data.csv",
        output_dir="../reports/",
        styles_dir="styles/vistaSansOT",
        blood_data_path="data/blood_data_during_stay.csv",
        clinical_data_path="data/all_clinical_data.csv"
    )

    try:
        path = generator.generate_report(fake_id=fake_id, patient_name=patient_name)
        print(f"Report generated: {path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

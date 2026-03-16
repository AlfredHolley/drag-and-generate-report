"""
Script to generate PDF reports for all patients with interactive name input
"""

from pdf_generator import PDFReportGenerator


def main():
    """Generate PDF reports, prompting for each patient's name"""

    generator = PDFReportGenerator(
        data_path="data/data.csv",
        output_dir="../reports/",
        styles_dir="styles/vistaSansOT",
        blood_data_path="data/blood_data_during_stay.csv"
    )

    fake_ids = generator.df['fake_id'].unique()
    print(f"\n{len(fake_ids)} patients found.\n")

    generated = []

    for fake_id in fake_ids:
        name = input(f"Patient name for ID {fake_id} (Enter to skip): ").strip()

        if not name:
            print(f"  Skipped {fake_id}\n")
            continue

        try:
            path = generator.generate_report(fake_id=fake_id, patient_name=name)
            generated.append(path)
            print(f"  -> {path}\n")
        except Exception as e:
            print(f"  Error for {fake_id}: {e}\n")

    print(f"\n{len(generated)} reports generated.")


if __name__ == "__main__":
    main()

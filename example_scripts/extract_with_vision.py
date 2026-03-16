"""
Extract PDF data by converting to images for manual analysis
"""

from pdf2image import convert_from_path
from pathlib import Path
import os

def convert_pdf_to_images(pdf_path, output_folder):
    """Convert PDF pages to images"""
    pdf_path = Path(pdf_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    # Convert PDF to images
    images = convert_from_path(pdf_path, dpi=200)

    image_paths = []
    for i, image in enumerate(images, 1):
        image_path = output_folder / f"{pdf_path.stem}_page_{i}.png"
        image.save(image_path, 'PNG')
        image_paths.append(image_path)

    return image_paths

def main():
    """Convert first PDF to images for analysis"""
    pdf_dir = Path("data/pdfs")
    output_dir = Path("data/pdf_images")

    # Get first PDF
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if pdf_files:
        first_pdf = pdf_files[0]
        print(f"Converting {first_pdf.name} to images...")

        image_paths = convert_pdf_to_images(first_pdf, output_dir)
        print(f"Created {len(image_paths)} images in {output_dir}")

        for img_path in image_paths[:3]:  # Show first 3
            print(f"  - {img_path}")

if __name__ == "__main__":
    main()

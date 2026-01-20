# Medical Report Generator Portal

A production-grade web portal for processing medical CSV data and generating PDF reports with category-organized tables and parameter explanations.

## Features

- **Drag & Drop CSV Upload**: Simple interface for uploading medical data files
- **Automatic Processing**: Python backend processes CSV files and extracts categories and parameters
- **PDF Generation**: Beautiful PDF reports with category-organized tables
- **Brutal Minimalist Design**: Black and cyan (RGB 22,186,222) aesthetic with clean typography
- **Parameter Explanations**: English explanations grouped logically by category

## Architecture

```
Frontend (Vanilla HTML/CSS/JS)
    ↓ (drag & drop CSV)
Backend API (Flask)
    ↓ (process CSV)
Python Processing Scripts
    ↓ (generate PDF)
PDF Report Download
```

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Ensure the `fonts/` directory exists in the project root with the required font files:
   - VistaSansOT-Reg.ttf
   - VistaSansOT-Book.ttf
   - VistaSansOT-Bold.ttf
   - VistaSansOT-BookItalic.ttf
   - VistaSansOT-Light.ttf
   - VistaSansOT-LightItalic.ttf
   - Calibri.ttf
   - Calibri-Bold.ttf

5. Run the Flask server:
```bash
python app.py
```

The backend will run on `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Open `index.html` in a web browser, or serve it using a local web server:

```bash
# Using Python
python -m http.server 8000

# Using Node.js (if you have http-server installed)
npx http-server -p 8000
```

3. Open `http://localhost:8000` in your browser

## Usage

1. **Upload CSV File**: Drag and drop a CSV file onto the upload zone or click to browse
2. **Processing**: The system will automatically parse the CSV, extract categories and parameters
3. **Download PDF**: Once processing is complete, click the download button to get your PDF report

## CSV Format

The CSV file should follow this structure:
- Row 1: Header information (optional)
- Row 2: Patient name (optional)
- Row 3: Column headers with analysis IDs
- Row 4: Date values for each column
- Row 5+: Category rows (first column contains category name) and parameter rows (first column empty, second column contains parameter name)

Example:
```csv
,Analisis,ID V7169825,ID T2436216,Unidad
,,09/01/2026,15/10/2025,
Hematología y Hemostasia,,,,,
,Hematíes,4.69,4.49,x10⁶/mm³
,Hemoglobina,14.5,13.6,g/dL
```

## Configuration

### Categories

Edit `backend/config/categories.json` to modify category names, ordering, and explanations.

### Parameters

Edit `backend/config/parameters.json` to add parameter mappings, English names, units, and explanations.

## API Endpoints

- `POST /api/upload`: Upload a CSV file
- `POST /api/process`: Process uploaded CSV and generate PDF
- `GET /api/download/<file_id>`: Download generated PDF
- `GET /api/health`: Health check endpoint

## Project Structure

```
report-generator/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── processors/
│   │   ├── csv_parser.py
│   │   └── data_transformer.py
│   ├── pdf_generator/
│   │   ├── pdf_builder.py
│   │   ├── table_generator.py
│   │   └── text_formatter.py
│   └── config/
│       ├── categories.json
│       └── parameters.json
├── fonts/ (existing)
├── logo_bw.svg (existing)
└── README.md
```

## Design Principles

- **Brutal Minimalism**: Maximum contrast with black (#000000) and cyan (RGB 22,186,222)
- **Typography**: VistaSans for display, Calibri for body text
- **Layout**: Generous negative space, asymmetric compositions
- **Animations**: Smooth transitions and micro-interactions

## Error Handling

The application includes comprehensive error handling:
- File validation (type, size, format)
- CSV parsing errors
- PDF generation errors
- Network errors
- User-friendly error messages

## License

This project is for internal use.

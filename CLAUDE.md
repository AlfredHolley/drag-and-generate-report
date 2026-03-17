# Buchinger Medical Report Generator — CLAUDE.md

> **Context file for AI assistants.** Describes the current state of the application, its architecture, data flow, and conventions to follow when making changes.

---

## What the app does

The **Buchinger Medical Report Generator** is a web portal that takes raw microbiome analysis data (`.xlsx`) delivered by the laboratory and converts it into polished, ready-to-share medical reports.

**End-to-end workflow:**

1. The doctor (or clinic staff) drags & drops the laboratory Excel file onto the upload zone.
2. The backend converts the flat XLSX into a structured dataset (CSV → DataFrame).
3. A PDF report is generated automatically — hierarchical tables, subsection descriptions, alarm indicators.
4. The doctor can also download an editable **Word (DOCX)** version to add personal comments or annotations before sharing with the patient.
5. Before downloading, the right-hand panel instantly highlights **all out-of-norm parameters** grouped by section and subsection, so the doctor can review the key findings at a glance without scrolling through the full report.

---

## Key features

| Feature | Description |
|---|---|
| **XLSX upload** | Drag & drop or click-to-browse |
| **PDF generation** | ReportLab — hierarchical tables, subsection titles + descriptions, alarm `!` symbols |
| **DOCX generation** | python-docx — editable Word document mirroring the PDF structure |
| **Out-of-norm summary panel** | Right-hand panel lists alarmed parameters grouped by section → subsection, with result + reference range |
| **PDF preview** | PDF.js canvas renderer — zoom in/out, fit-to-width, fullscreen |
| **Alarm indicators** | `!` in the last column only — no row background colouring |
| **i18n-ready** | All section/subsection text lives in `SUBSECTION_MAP` — swap for `SUBSECTION_MAP_FR` etc. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER                              │
│                                                             │
│  ┌──────────────────┐        ┌───────────────────────────┐  │
│  │   PDF Preview    │        │  Out-of-norm panel        │  │
│  │   (PDF.js)       │◄──────►│  section → subsection     │  │
│  │   zoom / scroll  │        │  param  result  ref  !    │  │
│  └────────┬─────────┘        └───────────────────────────┘  │
│           │  toolbar: ← New file  ↓PDF  ↓DOCX               │
└───────────┼─────────────────────────────────────────────────┘
            │ fetch (FormData)
            ▼
┌───────────────────────────────────────────────────────────────┐
│                    FLASK BACKEND  (app.py)                    │
│                                                               │
│  POST /api/convert            XLSX → CSV (metadata headers)   │
│  POST /api/generate-pdf       XLSX → PDF bytes                │
│  POST /api/generate-docx      XLSX → DOCX bytes               │
│  POST /api/alarmed-parameters XLSX → JSON alarm summary       │
│  POST /api/parameters         XLSX → JSON parameter list      │
│  GET  /fonts/<filename>       Serve font files                │
│  GET  /api/health             Health check                    │
└──────────────┬────────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
MicrobiomePDFGenerator  MicrobiomeDOCXGenerator
(microbiome_pdf.py)     (microbiome_docx.py)
  - SUBSECTION_MAP        - mirrors PDF structure
  - _build_section_table  - python-docx
  - _draw_header_footer   - logo_bw.png on cover
  - alarm detection       - editable in Word
  - ReportLab
```

---

## Technical stack

| Layer | Technology |
|---|---|
| **Frontend** | Vanilla HTML5 / CSS3 / JavaScript (no framework) |
| **PDF preview** | PDF.js 3.11 (CDN, canvas-based, no browser plugin) |
| **Backend** | Python 3.11 · Flask · Gunicorn |
| **Data processing** | pandas · openpyxl |
| **PDF generation** | ReportLab (platypus + canvas) |
| **DOCX generation** | python-docx · pdf2docx |
| **Fonts** | VistaSans OT family (display) · Calibri (body/tables) |
| **Containerisation** | Docker · docker-compose |
| **CI/CD** | GitHub Actions → deploy.yml |

---

## Project structure (actual)

```
report-generator/
├── frontend/
│   ├── index.html          # Single-page app — upload, preview, alarm panel
│   ├── styles.css          # All styles (CSS custom properties, no framework)
│   ├── logo_bw.svg         # SVG logo (header + PDF cover)
│   └── logo_bw.png         # PNG logo (DOCX cover)
├── backend/
│   ├── app.py              # Flask routes + request handling
│   ├── requirements.txt
│   ├── security_config.py  # CORS, rate-limiting, file validation
│   └── pdf_generator/
│       ├── microbiome_pdf.py   # PDF generator (ReportLab)
│       └── microbiome_docx.py  # DOCX generator (python-docx)
├── fonts/                  # VistaSans OT + Calibri .ttf files
├── data/                   # Sample CSV (development only)
├── example_pdf/            # preview.pdf + preview.docx (dev output)
├── preview.py              # CLI script: regenerates example_pdf/preview.pdf
├── docker-compose.yml
├── CLAUDE.md               # ← this file
└── README.md
```

---

## Data flow — XLSX input format

The input is a flat Excel file from the laboratory. Key columns used:

| Column | Description |
|---|---|
| `TipoInforme` | Section name (e.g. "Bacterioma", "Mycobiome") |
| `Ensayo` | Parameter name — may contain `[CODE]` suffixes stripped by `_clean_param()` |
| `Resultado1` | Primary result value |
| `Resultado2` | Secondary / textual result (e.g. "ABSENCE: DNA not detected") |
| `Unidad1` | Unit |
| `VRMinimo` / `VRMaximo` | Reference range min / max |
| `Alarma` | `"Verdadero"` when out of norm |
| `AlarmaDescripcion` | Alarm type code (`ALTO`, `BAJO`, `Asterisco`, `R`, …) |
| `Memo` | Optional note shown below a subsection |

**Rule**: all code must be based on the **structure** of the data, never hard-coded on specific values.

---

## PDF report structure

```
Cover page
  └── Logo · "MICROBIOME ANALYSIS" · patient info band (at 0.38 page height)

For each section (TipoInforme):
  ├── Section header (full-width coloured band)
  ├── Section description text
  └── For each subsection (defined in SUBSECTION_MAP):
        ├── Subsection title + description
        └── Table: Parameter | Result | Unit | Reference Range | !
              (child rows indented, alarm symbol only in last column)

Summary (end of report):
  └── One table per section — only alarmed parameters, hierarchical
```

---

## SUBSECTION_MAP convention

Located in `microbiome_pdf.py`. Structure:

```python
SUBSECTION_MAP = {
    "Section Name": [
        ("Subsection Title", "Explanatory text (English).", ["trigger param 1", "trigger param 2"]),
        ...
    ],
    ...
}
```

- The **trigger** is the cleaned `Ensayo` value of the first parameter of that subsection.
- Multiple triggers per subsection are supported (list) — rows are merged across fragmented positions in the source data.
- To add a new language: create `SUBSECTION_MAP_FR` and pass it at instantiation.

---

## Alarm conventions

- Alarm is detected when `Alarma == "Verdadero"`.
- Display: `!` symbol in the **last column only** — no row background colour, no coloured text.
- If a parameter is also cited in doctor comments (DOCX flow): `✉` symbol is added next to `!`.
- `_clean_param()` strips `[CODE]` suffixes (regex `\s*\[[^\[\]]+\]\s*$`) from parameter names.

---

## Dev commands

```bash
# Regenerate example_pdf/preview.pdf (reads data/Informes_*.csv)
python preview.py

# Run Flask dev server
cd backend && python app.py

# Docker
docker-compose up --build
```

---

## Design language

- **Black** `#000000` and **cyan** `#16BAE0` — primary palette
- **VistaSans Light** for display titles (REPORT GENERATOR heading)
- **Calibri** for all table content and body text
- **Cover page**: white background top half, `#ECEBE5` band below separator (starting at `h × 0.38`)
- Minimalist, high-contrast, no decorative elements

---

## Important rules for AI assistants

1. **Never hard-code parameter names** — all logic must work on any valid XLSX following the structure above.
2. **Do not colour parameter names or result values** with alarm colours — only the `!` symbol in the status column.
3. **`_clean_param()` must always be used** before displaying or comparing `Ensayo` values.
4. **SUBSECTION_MAP drives all hierarchy** — do not infer subsections from parameter names directly.
5. After every change to `microbiome_pdf.py`, run `python preview.py` to validate output.
6. Fonts are served by Flask at `/fonts/<filename>` — do not hardcode absolute paths; use conditional resolution (local vs Docker `/app/fonts/`).

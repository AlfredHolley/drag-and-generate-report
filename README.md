# Buchinger Medical Report Generator

> A clinical web portal that transforms raw laboratory microbiome data (`.xlsx`) into polished, ready-to-share medical reports — downloadable as **PDF** or editable **Word** documents.

---

## ⚠️ Legal & Compliance Notice — Medical Data Hosting (France / EU)

> **This application is not currently compliant for processing non-anonymised patient data.**

Under French law (**Article L.1111-8 of the Code de la Santé Publique**) and EU GDPR (Art. 9 — special categories of personal data), **personal health data must be hosted exclusively by a provider holding HDS certification** (*Hébergement de Données de Santé*).

This obligation applies even when data is **only in transit** — i.e. uploaded, processed, and immediately discarded without being written to disk. The mere fact that identifiable health data passes through a server is sufficient to trigger the HDS requirement.

**The current deployment target (Hostinger VPS) is not HDS-certified.**

### Compliant hosting providers (France)

| Provider | HDS Certification |
|---|---|
| OVHcloud (Healthcare offer) | ✅ Certified |
| Scaleway | ✅ Certified |
| AWS Paris (`eu-west-3`) | ✅ Certified |
| Azure France Central | ✅ Certified |
| Hostinger | ❌ Not certified |

### Recommended options

- **Option A — Anonymise before upload.** Strip all patient identifiers (name, date of birth, ID) from the XLSX before it reaches the server. The application then processes only anonymous microbiome data — HDS no longer applies.

- **Option B — Migrate to an HDS-certified host.** Move the deployment to OVH, Scaleway, or an AWS/Azure region with HDS certification, and formalise a data processing agreement (DPA) with the provider.

- **Option C — Deploy on the clinic's own internal servers (Intranet).** Host the application on a physical server **owned and operated by the healthcare institution** (on-premises). Under Article L.1111-8, the HDS obligation targets *third-party* hosting providers. If the clinic hosts its own data on its own infrastructure, no external "hébergeur" is involved — **HDS certification is not required**, even for non-anonymised data.

  > Practical setup: a dedicated Linux machine (or a Docker-capable NAS/server) on the clinic's local network, accessible only from within the premises or via the institution's VPN. No internet exposure, no third-party data processor, no HDS constraint.

  | Constraint | On-premises Intranet |
  |---|---|
  | HDS required? | ❌ No (institution hosts its own data) |
  | GDPR applies? | ✅ Yes — standard data controller obligations |
  | Internet exposure | ❌ None (LAN / VPN only) |
  | Cost | Low — existing clinic hardware |
  | Maintenance | IT team of the institution |

---

## Overview

```
Laboratory XLSX
      │
      ▼
┌─────────────────────────────────────────────┐
│            Web Portal (browser)             │
│                                             │
│  ┌───────────────────┐  ┌────────────────┐  │
│  │   PDF Preview     │  │  Out-of-norm   │  │
│  │   (zoom / scroll) │  │  parameters    │  │
│  └───────────────────┘  │  at a glance   │  │
│                          └────────────────┘  │
│   toolbar:  ↓ PDF    ↓ DOCX (editable)      │
└─────────────────────────────────────────────┘
      │                    │
      ▼                    ▼
 PDF Report           Word Document
 (immediate           (doctor adds
  download)            comments)
```

The doctor uploads a single Excel file from the lab. Within seconds they get:

- A **structured PDF report** — sections, subsections with explanatory text, tables with alarm indicators
- An **editable Word document** — same structure, ready to annotate in Microsoft Word before sharing with the patient
- A **live summary panel** — all out-of-norm parameters listed hierarchically (section → subsection → parameter), with result and reference range visible at a glance

---

## Features

| Feature | Details |
|---|---|
| **Drag & drop upload** | `.xlsx` / `.xls` — validated client-side and server-side |
| **PDF report** | ReportLab — hierarchical tables, subsection descriptions, `!` alarm markers |
| **DOCX report** | python-docx — editable in Word, logo on cover, same structure as PDF |
| **Out-of-norm panel** | Instant summary of alarmed parameters grouped by section/subsection |
| **PDF preview** | PDF.js (canvas) — zoom in/out, fit-to-width, fullscreen, no browser plugin needed |
| **Alarm indicators** | `!` in the last table column only — no coloured text, no row backgrounds |
| **i18n-ready** | All section/subsection text in a single `SUBSECTION_MAP` dict |
| **Containerised** | Docker + docker-compose for one-command deployment |

---

## Technical Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5 · CSS3 · Vanilla JavaScript |
| **PDF preview** | [PDF.js](https://mozilla.github.io/pdf.js/) 3.11 (CDN) |
| **Backend** | Python 3.11 · [Flask](https://flask.palletsprojects.com/) · Gunicorn |
| **Data processing** | [pandas](https://pandas.pydata.org/) · openpyxl |
| **PDF generation** | [ReportLab](https://www.reportlab.com/) (Platypus + canvas) |
| **DOCX generation** | [python-docx](https://python-docx.readthedocs.io/) · pdf2docx |
| **Fonts** | VistaSans OT (display) · Calibri (tables/body) |
| **Containerisation** | Docker · docker-compose |
| **CI/CD** | GitHub Actions (`deploy.yml`) |

---

## Architecture

```
BROWSER
┌─────────────────────────────────────────────────────────────────┐
│  Drop zone → Generate button                                    │
│  ┌──────────────────────────┐  ┌────────────────────────────┐  │
│  │  PDF Preview (PDF.js)    │  │  Out-of-norm parameters    │  │
│  │  canvas render per page  │  │  ┌─ Bacterioma ───────┐   │  │
│  │  zoom / fullscreen       │  │  │  • Shannon Index !  │   │  │
│  └──────────────────────────┘  │  └────────────────────┘   │  │
│   toolbar: New file ↓PDF ↓DOCX └────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP (FormData)
                       ▼
FLASK  (backend/app.py)
┌─────────────────────────────────────────────────────────────────┐
│  POST /api/convert             XLSX → CSV                       │
│  POST /api/generate-pdf        XLSX → PDF bytes                 │
│  POST /api/generate-docx       XLSX → DOCX bytes                │
│  POST /api/alarmed-parameters  XLSX → JSON alarm summary        │
│  GET  /fonts/<filename>        Serve font files                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
  MicrobiomePDFGenerator   MicrobiomeDOCXGenerator
  (ReportLab)              (python-docx)
  microbiome_pdf.py        microbiome_docx.py
```

---

## Project Structure

```
report-generator/
├── frontend/
│   ├── index.html              # Single-page app
│   ├── styles.css              # All styles
│   ├── logo_bw.svg             # Logo for SVG contexts (web, PDF)
│   └── logo_bw.png             # Logo for DOCX cover page
│
├── backend/
│   ├── app.py                  # Flask routes
│   ├── requirements.txt
│   ├── security_config.py      # CORS, rate-limiting, file validation
│   └── pdf_generator/
│       ├── microbiome_pdf.py   # PDF generator (ReportLab)
│       └── microbiome_docx.py  # DOCX generator (python-docx)
│
├── fonts/                      # VistaSans OT + Calibri .ttf
├── data/                       # Sample CSV (development only)
├── example_pdf/                # Dev output: preview.pdf / preview.docx
├── preview.py                  # CLI: regenerate preview.pdf from sample data
├── docker-compose.yml
├── CLAUDE.md                   # AI assistant context file
└── README.md                   # ← this file
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Font files in `fonts/` (VistaSans OT family + Calibri — not included for licensing reasons)

### Local development

```bash
# 1. Install Python dependencies
cd backend
pip install -r requirements.txt

# 2. Run the Flask server
python app.py
# → http://localhost:5000
```

Open `http://localhost:5000` in your browser — the Flask server serves both the API and the frontend.

### Docker

```bash
docker-compose up --build
# → http://localhost:5000
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/convert` | XLSX → CSV (returns metadata headers) |
| `POST` | `/api/generate-pdf` | XLSX → PDF binary response |
| `POST` | `/api/generate-docx` | XLSX → DOCX binary response |
| `POST` | `/api/alarmed-parameters` | XLSX → JSON list of out-of-norm params |
| `POST` | `/api/parameters` | XLSX → JSON list of all parameter names |
| `GET` | `/fonts/<filename>` | Serve font files |
| `GET` | `/api/health` | Health check |

---

## Input Data Format

The application expects an `.xlsx` file with the following key columns:

| Column | Description |
|---|---|
| `TipoInforme` | Section (e.g. `"Bacterioma"`, `"Mycobiome"`) |
| `Ensayo` | Parameter name (may include `[CODE]` suffix — stripped automatically) |
| `Resultado1` | Primary result value |
| `Resultado2` | Secondary/textual result |
| `Unidad1` | Unit |
| `VRMinimo` / `VRMaximo` | Reference range |
| `Alarma` | `"Verdadero"` = out of norm |
| `AlarmaDescripcion` | Alarm type (`ALTO`, `BAJO`, `Asterisco`, `R`, …) |
| `Memo` | Optional note displayed below a subsection |

> All processing logic is structure-based — the application works with any valid file following this schema, regardless of the specific parameters it contains.

---

## Report Structure

```
┌─ Cover page ────────────────────────────────────┐
│  Logo  ·  MICROBIOME ANALYSIS                   │
│  ─────────────────────────────                  │
│  Patient  ·  Collection date  ·  Report N°      │
│  Sections included: …                           │
└─────────────────────────────────────────────────┘

For each section:
  ┌─ Section header ──────────────────────────────┐
  │  Section title + description                  │
  │                                               │
  │  ┌─ Subsection ──────────────────────────┐    │
  │  │  Subsection title + explanatory text  │    │
  │  │  ┌───────────────────────────────────┐│    │
  │  │  │ Parameter │Result│Unit│Ref Range│!││    │
  │  │  │  - child  │      │    │         │!││    │
  │  │  └───────────────────────────────────┘│    │
  │  └────────────────────────────────────────┘    │
  └───────────────────────────────────────────────┘

Summary (end of report):
  One table per section — alarmed parameters only
```

---

## Design

- **Palette**: Black `#000000` · Cyan `#16BAE0` · Off-white `#ECEBE5`
- **Fonts**: VistaSans Light (titles) · Calibri (body, tables)
- **Principle**: high contrast, minimal decoration, generous whitespace

---

## License

Internal use — Buchinger Wilhelmi clinic.

"""
Microbiome PDF Report Generator
Generates a polished A4 medical PDF from microbiome XLSX/CSV analysis data.

Supported CSV columns:
  NumInforme, Cliente, Indentificacion, DescripcionMuestra, DNI,
  FechaMuestra, Validacion, TipoInforme, Ensayo, Resultado1, Unidad1,
  Alarma, AlarmaDescripcion, VRMaximo, VRMinimo, Resultado2, Unidad2, Memo
"""

import io
import os
import re

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

# Optional SVG logo support (requires svglib + pycairo)
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF as svgRenderPDF
    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False


# ── Colour palette ─────────────────────────────────────────────────────────────

CYAN         = colors.HexColor('#16BADE')
BLACK        = colors.black
WHITE        = colors.white
DARK_GRAY    = colors.HexColor('#333333')
MID_GRAY     = colors.HexColor('#888888')
LIGHT_GRAY   = colors.HexColor('#FAFAFA')   # parent-row background
TABLE_HDR_BG = colors.HexColor('#F3F3F3')   # table header row
TABLE_SEP    = colors.HexColor('#E5E5E5')   # subtle row separator

# Alarm colours: text + optional row background
ALM_HI_TXT   = colors.HexColor('#CC5500')   # ↑  above normal   – orange
ALM_HI_BG    = colors.HexColor('#FFF3E0')
ALM_VHI_TXT  = colors.HexColor('#B71C1C')   # ↑↑↑ critical high  – red
ALM_VHI_BG   = colors.HexColor('#FFEBEE')
ALM_LO_TXT   = colors.HexColor('#1565C0')   # ↓  below normal   – blue
ALM_LO_BG    = colors.HexColor('#E3F2FD')
ALM_VLO_TXT  = colors.HexColor('#1A237E')   # ↓↓↓ critical low   – deep blue
ALM_VLO_BG   = colors.HexColor('#E8EAF6')
ALM_NOTE_TXT = colors.HexColor('#E65100')   # ★  note/asterisk  – deep orange
ALM_PRES_TXT = colors.HexColor('#B71C1C')   # ⚠  presence       – red
ALM_PRES_BG  = colors.HexColor('#FFEBEE')
BAL_GREEN    = colors.HexColor('#2E7D32')   # "Balanced" result – dark green

# AlarmaDescripcion → (symbol, text_color | None, bg_color | None)
# Range-based alarms (A/B) use the eye symbol ⊙ with no background colour.
# Presence (R) and notes (Asterisco, +/-) keep their own visual treatment.
ALARM_MAP: dict = {
    '_':         ('',    None,      None),
    'Asterisco': ('!',   DARK_GRAY, None),
    'A':         ('!',   DARK_GRAY, None),
    'AA':        ('!',   DARK_GRAY, None),
    'AAAA':      ('!',   DARK_GRAY, None),
    'B':         ('!',   DARK_GRAY, None),
    'BB':        ('!',   DARK_GRAY, None),
    'BBBB':      ('!',   DARK_GRAY, None),
    '+/-':       ('!',   DARK_GRAY, None),
    'R':         ('!',   DARK_GRAY, None),
}

# Section descriptions – keyed by TipoInforme value.
# Add / modify descriptions here without touching any other code.
SECTION_DESCRIPTIONS: dict = {
    "Intestinal Dysbiosis by NGS": (
        "This panel assesses intestinal dysbiosis through next-generation sequencing (NGS), evaluating the "
        "overall balance and diversity of the gut microbial community. It identifies deviations from a healthy "
        "microbiome composition, highlighting potential imbalances associated with gastrointestinal disorders, "
        "inflammation, or impaired nutrient absorption."
    ),
    "Bacterioma by NGS": (
        "The bacterioma analysis uses next-generation sequencing (NGS) to identify and quantify the bacterial "
        "communities present in the gut microbiome. This comprehensive profiling reveals the diversity, "
        "abundance, and relative proportions of bacterial species, providing insights into digestive health, "
        "metabolic function, and potential dysbiosis patterns."
    ),
    "Archaeoma by NGS": (
        "The archaeoma analysis uses next-generation sequencing (NGS) to characterise the archaeal populations "
        "within the gut. Archaea, particularly methanogens, play a key role in gut gas metabolism and interact "
        "closely with bacterial communities. Their assessment provides valuable information about the balance "
        "and metabolic activity of the intestinal ecosystem."
    ),
    "Mycobiome by NGS": (
        "The mycobiome analysis profiles the fungal communities residing in the gut using next-generation "
        "sequencing (NGS). Fungi, though present in smaller quantities than bacteria, can significantly "
        "influence gut health and immune responses. This panel detects pathogenic or opportunistic fungal "
        "species and evaluates overall fungal diversity."
    ),
    "Virome by NGS": (
        "The virome analysis characterises the viral communities present in the gut using NGS. The intestinal "
        "virome, largely composed of bacteriophages, plays a crucial role in shaping bacterial populations "
        "and modulating immune responses. This panel provides insights into the viral landscape and its "
        "potential impact on gut ecosystem stability."
    ),
    "Parasitome by NGS": (
        "The parasitome analysis detects and identifies parasitic organisms within the gastrointestinal "
        "tract using highly sensitive molecular sequencing. This approach can reveal infections that may be "
        "missed by conventional microscopy, including protozoa and helminths that can affect digestive "
        "function and overall health."
    ),
    "Stool Sample": (
        "The stool sample analysis evaluates various biochemical properties of the stool, providing "
        "information about digestive function, intestinal inflammation, and gut barrier integrity. "
        "These markers help identify malabsorption, inflammatory conditions, and other gastrointestinal "
        "disorders that may affect overall health."
    ),
}


# ── Invisible flowable – updates running section name in page header ───────────

class SectionMarker(Flowable):
    """Zero-size flowable that writes the current section name onto the canvas."""

    def __init__(self, section_name: str):
        Flowable.__init__(self)
        self.section_name = section_name
        self.width = self.height = 0

    def draw(self):
        self.canv._current_section = self.section_name  # type: ignore[attr-defined]


# ── Main generator ─────────────────────────────────────────────────────────────

class MicrobiomePDFGenerator:
    """
    Build a polished A4 medical PDF from a microbiome analysis DataFrame.

    Usage:
        pdf_bytes = MicrobiomePDFGenerator(df).generate()
    """

    PAGE_W, PAGE_H = A4
    L_MARGIN = 45
    R_MARGIN = 45
    T_MARGIN = 72   # room for running header
    B_MARGIN = 52   # room for footer

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

        # Resolve asset paths relative to this file
        _base = os.path.dirname(os.path.abspath(__file__))
        self._fonts_dir = os.path.normpath(os.path.join(_base, '..', '..', 'fonts'))
        self._logo_path = os.path.normpath(
            os.path.join(_base, '..', '..', 'frontend', 'logo_bw.svg'))

        self._extract_patient_info()
        self._register_fonts()
        self._setup_styles()

    # ── Initialisation helpers ─────────────────────────────────────────────────

    def _extract_patient_info(self) -> None:
        r = self.df.iloc[0]

        def g(col: str, default: str = '') -> str:
            v = r.get(col, default)
            return '' if pd.isna(v) else str(v).strip()

        self.patient_name  = g('DescripcionMuestra', 'Unknown patient')
        self.patient_id    = g('DNI')
        self.client        = g('Cliente')
        self.report_number = g('NumInforme')
        self.sample_date   = self._fmt_date(g('FechaMuestra'))
        self.valid_date    = self._fmt_date(g('Validacion'))

    @staticmethod
    def _fmt_date(s: str) -> str:
        if not s:
            return ''
        try:
            return pd.to_datetime(s, dayfirst=True).strftime('%d/%m/%Y')
        except Exception:
            return s

    def _register_fonts(self) -> None:
        vista_map = {
            'VistaSans':       'VistaSansOT-Reg.ttf',
            'VistaSans-Bold':  'VistaSansOT-Bold.ttf',
            'VistaSans-Light': 'VistaSansOT-Light.ttf',
            'VistaSans-Book':  'VistaSansOT-Book.ttf',
        }
        calibri_map = {
            'Calibri':      'Calibri.ttf',
            'Calibri-Bold': 'Calibri-Bold.ttf',
        }
        for name, fname in {**vista_map, **calibri_map}.items():
            path = os.path.join(self._fonts_dir, fname)
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception:
                    pass

    def _f(self, preferred: str, fallback: str = 'Helvetica') -> str:
        """Return *preferred* font name if registered, else *fallback*."""
        return (preferred
                if preferred in pdfmetrics.getRegisteredFontNames()
                else fallback)

    def _setup_styles(self) -> None:
        self.styles = getSampleStyleSheet()
        fb = self._f('VistaSans-Book')
        fl = self._f('VistaSans-Light')
        entries = [
            ('SecTitle', dict(fontName=fb, fontSize=20, textColor=CYAN,
                              spaceAfter=6, spaceBefore=0, leading=24)),
            ('SecDesc',  dict(fontName=fl, fontSize=9,  textColor=DARK_GRAY,
                              spaceAfter=8, leading=13, alignment=TA_JUSTIFY)),
            ('NoteItem', dict(fontName=fl, fontSize=8,  textColor=MID_GRAY,
                              spaceAfter=3, leading=11, leftIndent=10)),
        ]
        for name, kw in entries:
            if name not in self.styles:
                self.styles.add(
                    ParagraphStyle(name=name, parent=self.styles['Normal'], **kw))

    # ── Page-level drawing callbacks ───────────────────────────────────────────

    def _draw_cover(self, canvas, doc) -> None:  # noqa: ANN001
        """
        Clean white cover page:
          – Optional logo centred in the upper third
          – Title + subtitle in dark/cyan text
          – Cyan rule separating identity block from report info
          – Two-column patient info grid
          – Sections list
        """
        canvas.saveState()
        w, h = A4

        # ── Optional SVG logo ──────────────────────────────────────────────────
        logo_drawn = False
        if SVG_AVAILABLE and os.path.exists(self._logo_path):
            try:
                drw = svg2rlg(self._logo_path)
                if drw:
                    scale = 1.9
                    drw.width  *= scale
                    drw.height *= scale
                    drw.transform = (scale, 0, 0, scale, 0, 0)
                    x_logo = (w - drw.width) / 2
                    y_logo = h * 0.76
                    svgRenderPDF.draw(drw, canvas, x_logo, y_logo)
                    logo_drawn = True
            except Exception:
                pass

        # ── Report title ───────────────────────────────────────────────────────
        title_y = h * 0.64 if logo_drawn else h * 0.72
        canvas.setFont(self._f('VistaSans-Book'), 22)
        canvas.setFillColor(BLACK)
        canvas.drawCentredString(w / 2, title_y, "MICROBIOME ANALYSIS")

        sections = self.df['TipoInforme'].unique().tolist()

        # ── Cyan separator rule ────────────────────────────────────────────────
        rule_y = h * 0.38   # fixed at 38 % from the bottom

        # Coloured background only below the separator line
        canvas.setFillColor(colors.HexColor('#ECEBE5'))
        canvas.rect(0, 0, w, rule_y, stroke=0, fill=1)

        # canvas.setStrokeColor(CYAN)
        # canvas.setLineWidth(1)
        # canvas.line(self.L_MARGIN, rule_y, w - self.R_MARGIN, rule_y)

        # ── Patient info grid ──────────────────────────────────────────────────
        lx  = self.L_MARGIN + 10
        rx  = w / 2 + 15
        iy  = rule_y - 28
        lbl = 84

        def info_row(x: float, y: float, label: str, value: str) -> None:
            canvas.setFont(self._f('VistaSans-Book'), 9.5)
            canvas.setFillColor(DARK_GRAY)
            canvas.drawString(x, y, label)
            canvas.setFont(self._f('Calibri'), 9.5)
            canvas.setFillColor(BLACK)
            canvas.drawString(x + lbl, y, value)

        info_row(lx, iy,       'Patient',    self.patient_name)
        info_row(lx, iy - 17,  'ID',         self.patient_id)
        info_row(lx, iy - 34,  'Clinic',     self.client)
        info_row(rx, iy,       'Collection', self.sample_date)
        info_row(rx, iy - 17,  'Validation', self.valid_date)
        info_row(rx, iy - 34,  'Report N°',  self.report_number)

        # ── Light separator ────────────────────────────────────────────────────
        sep_y = iy - 52
        canvas.setStrokeColor(colors.HexColor('#DDDDDD'))
        canvas.setLineWidth(0.5)
        canvas.line(self.L_MARGIN, sep_y, w - self.R_MARGIN, sep_y)

        # ── Sections included ──────────────────────────────────────────────────
        canvas.setFont(self._f('VistaSans-Book'), 9)
        canvas.setFillColor(DARK_GRAY)
        canvas.drawString(lx, sep_y - 14, 'Sections included:')
        canvas.setFont(self._f('VistaSans'), 9)
        canvas.setFillColor(colors.HexColor('#555555'))
        sy = sep_y - 26
        for sec in sections:
            canvas.drawString(lx + 12, sy, f'• {sec}')
            sy -= 12

        canvas.restoreState()

    def _draw_header_footer(self, canvas, doc) -> None:  # noqa: ANN001
        canvas.saveState()
        w, h = A4
        section = getattr(canvas, '_current_section', '')

        # Cyan horizontal rule
        canvas.setStrokeColor(CYAN)
        canvas.setLineWidth(1.2)
        canvas.line(self.L_MARGIN, h - 46, w - self.R_MARGIN, h - 46)

        # Section name — left, above the rule
        if section:
            canvas.setFont(self._f('VistaSans-Book'), 8.5)
            canvas.setFillColor(DARK_GRAY)
            canvas.drawString(self.L_MARGIN, h - 38, section)

        # Patient name — right
        canvas.setFont(self._f('VistaSans'), 8.5)
        canvas.setFillColor(DARK_GRAY)
        canvas.drawRightString(w - self.R_MARGIN, h - 30, self.patient_name)

        # Report number — right, smaller
        canvas.setFont(self._f('Calibri'), 7.5)
        canvas.setFillColor(MID_GRAY)
        canvas.drawRightString(w - self.R_MARGIN, h - 42,
                               f'Report N° {self.report_number}')

        # Footer
        canvas.setFont(self._f('VistaSans-Light'), 7.5)
        canvas.setFillColor(MID_GRAY)
        canvas.drawString(self.L_MARGIN, 22, self.client)
        canvas.drawRightString(w - self.R_MARGIN, 22, str(doc.page))

        canvas.restoreState()

    # ── Data helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _strip_html(text) -> str:  # noqa: ANN001
        if not text or str(text).strip() in ('', 'nan', 'None'):
            return ''
        t = re.sub(r'<[^>]+>', ' ', str(text))
        return re.sub(r'\s+', ' ', t).strip()

    @staticmethod
    def _clean(val) -> str:  # noqa: ANN001
        s = str(val).strip()
        return '' if s in ('', 'nan', 'None') else s

    @staticmethod
    def _clean_param(val) -> str:  # noqa: ANN001
        """Clean parameter name and strip trailing bracketed codes like [FUNG]."""
        s = str(val).strip()
        if s in ('', 'nan', 'None'):
            return ''
        # Remove any trailing [CODE] identifiers (e.g. [FUNG], [BAC], etc.)
        s = re.sub(r'\s*\[[A-Z0-9_]+\]\s*$', '', s).strip()
        return s

    def _result(self, row) -> str:  # noqa: ANN001
        r1 = self._clean(row.get('Resultado1', ''))
        r2 = self._clean(row.get('Resultado2', ''))
        if r1:
            return r1
        if r2:
            return r2[:35] + ('…' if len(r2) > 35 else '')
        return '—'

    def _ref_range(self, row) -> str:  # noqa: ANN001
        vmax = self._clean(row.get('VRMaximo', '')).replace(',', '.')
        vmin = self._clean(row.get('VRMinimo', '')).replace(',', '.')
        if vmin and vmax:
            return f'{vmin} – {vmax}'
        if vmax:
            return f'< {vmax}'
        if vmin:
            return f'> {vmin}'
        return '—'

    def _alarm(self, row):  # noqa: ANN001
        """Return (symbol, text_color | None, bg_color | None)."""
        if str(row.get('Alarma', 'Falso')).strip() != 'Verdadero':
            return '', None, None
        code = str(row.get('AlarmaDescripcion', '_')).strip()
        return ALARM_MAP.get(code, ('!', ALM_NOTE_TXT, None))

    # ── Table builder ──────────────────────────────────────────────────────────

    def _build_section_table(self, sec_df: pd.DataFrame):
        """
        Build a hierarchical ReportLab Table for one TipoInforme section.

        Hierarchy rules:
          • Rows where Ensayo does NOT start with '- ' → parent row
              – Bold parameter name, LIGHT_GRAY background (unless alarm colour)
          • Rows where Ensayo starts with '- '         → child row
              – Normal weight, indented, white background (unless alarm colour)

        Returns (Table, [note_str, ...]).
        """
        avail = self.PAGE_W - self.L_MARGIN - self.R_MARGIN
        col_w = [
            avail * 0.40,   # Parameter
            avail * 0.12,   # Result
            avail * 0.12,   # Unit
            avail * 0.22,   # Reference Range
            avail * 0.08,   # Status symbol (alarms)
        ]

        fb = self._f('VistaSans-Book')
        fr = self._f('VistaSans')
        fl = self._f('VistaSans-Light')

        hdr_l = ParagraphStyle('_hl', fontName=fb, fontSize=8.5,
                               leading=11, textColor=DARK_GRAY)
        hdr_c = ParagraphStyle('_hc', fontName=fb, fontSize=8.5,
                               leading=11, textColor=DARK_GRAY,
                               alignment=TA_CENTER)

        # ── Table header ──────────────────────────────────────────────────────
        tdata = [[
            Paragraph('Parameter',       hdr_l),
            Paragraph('Result',          hdr_c),
            Paragraph('Unit',            hdr_c),
            Paragraph('Reference Range', hdr_c),
            Paragraph('',               hdr_c),
        ]]

        bg_cmds: list = []
        notes:   list = []

        for i, (_, row) in enumerate(sec_df.iterrows()):
            ridx     = i + 1                        # 1-based row index in table
            param    = self._clean_param(row.get('Ensayo', ''))
            is_child = param.startswith('- ')

            result = self._result(row)
            unit   = self._clean(row.get('Unidad1', ''))
            ref    = self._ref_range(row)
            sym, tc, bgc = self._alarm(row)

            # Collect HTML memos for note section below table
            memo = self._strip_html(row.get('Memo', ''))
            if memo:
                notes.append(f'[{param}]  {memo}')

            # ── Parameter cell ────────────────────────────────────────────────
            indent      = 14 if is_child else 3
            param_color = DARK_GRAY if is_child else BLACK   # never coloured by alarm
            param_ps    = ParagraphStyle(
                f'_pp{i}',
                fontName=fb if not is_child else fr,
                fontSize=8.5, leading=11,
                textColor=param_color, leftIndent=indent)

            # ── Result cell ───────────────────────────────────────────────────
            val_ps = ParagraphStyle(
                f'_vp{i}', fontName=self._f('Calibri'), fontSize=8.5,
                leading=11, textColor=BLACK, alignment=TA_CENTER)

            # ── Unit / ref range cells ────────────────────────────────────────
            ctr_ps = ParagraphStyle(
                f'_cp{i}', fontName=fl, fontSize=8.5,
                leading=11, textColor=DARK_GRAY, alignment=TA_CENTER)

            # ── Status symbol cell ────────────────────────────────────────────
            sym_ps = ParagraphStyle(
                f'_sp{i}', fontName=fr, fontSize=9,
                leading=11, textColor=tc if tc else DARK_GRAY,
                alignment=TA_CENTER)

            tdata.append([
                Paragraph(param,  param_ps),
                Paragraph(result, val_ps),
                Paragraph(unit,   ctr_ps),
                Paragraph(ref,    ctr_ps),
                Paragraph(sym,    sym_ps),
            ])

            # ── Row background ────────────────────────────────────────────────
            if bgc:
                # Alarm colour takes priority
                bg_cmds.append(('BACKGROUND', (0, ridx), (-1, ridx), bgc))
            elif not is_child:
                # Parent rows get a very light gray tint
                bg_cmds.append(('BACKGROUND', (0, ridx), (-1, ridx), LIGHT_GRAY))
            # Child rows remain white by default

        # ── Assemble TableStyle ───────────────────────────────────────────────
        tbl = Table(tdata, colWidths=col_w, repeatRows=1)
        style = TableStyle([
            # Header row
            ('BACKGROUND',    (0, 0), (-1, 0), WHITE),
            ('LINEBELOW',     (0, 0), (-1, 0), 0.8, DARK_GRAY),
            ('TOPPADDING',    (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            # Data rows
            ('TOPPADDING',    (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 7),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',         (0, 0), (0, -1),  'LEFT'),
            ('ALIGN',         (1, 0), (-1, -1), 'CENTER'),
            # Subtle row separator
            ('LINEBELOW',     (0, 1), (-1, -1), 0.05, TABLE_SEP),
        ])
        for cmd in bg_cmds:
            style.add(*cmd)
        tbl.setStyle(style)
        return tbl, notes

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate(self) -> bytes:
        """Build the full PDF and return it as raw bytes."""
        buf = io.BytesIO()

        doc = BaseDocTemplate(
            buf, pagesize=A4,
            leftMargin=self.L_MARGIN,
            rightMargin=self.R_MARGIN,
            topMargin=self.T_MARGIN,
            bottomMargin=self.B_MARGIN,
        )

        frame       = Frame(doc.leftMargin, doc.bottomMargin,
                            doc.width, doc.height, id='normal')
        cover_frame = Frame(doc.leftMargin, doc.bottomMargin,
                            doc.width, doc.height, id='cover')

        doc.addPageTemplates([
            PageTemplate(id='cover', frames=[cover_frame],
                         onPageEnd=self._draw_cover),
            PageTemplate(id='main',  frames=[frame],
                         onPageEnd=self._draw_header_footer),
        ])

        story = []

        # ── Cover page ────────────────────────────────────────────────────────
        # A single Spacer keeps the frame alive; actual drawing happens in the
        # onPageEnd callback (_draw_cover).
        story.append(Spacer(1, 1))
        story.append(NextPageTemplate('main'))
        story.append(PageBreak())

        # ── Section pages ─────────────────────────────────────────────────────
        sections = list(self.df['TipoInforme'].unique())

        for idx, section in enumerate(sections):
            sec_df = self.df[self.df['TipoInforme'] == section]

            # Mark section for the running page header
            story.append(SectionMarker(section))

            # Section title (cyan, large)
            story.append(Paragraph(section, self.styles['SecTitle']))
            story.append(Spacer(1, 2))

            # Optional introductory description paragraph
            desc = SECTION_DESCRIPTIONS.get(section, '')
            if desc:
                story.append(Paragraph(desc, self.styles['SecDesc']))
                story.append(Spacer(1, 6))

            # Hierarchical results table
            tbl, notes = self._build_section_table(sec_df)
            story.append(tbl)

            # Memo notes below the table
            if notes:
                story.append(Spacer(1, 8))
                for note in notes:
                    story.append(Paragraph(note, self.styles['NoteItem']))

            story.append(Spacer(1, 12))

            # Page break between sections (not after the last one)
            if idx < len(sections) - 1:
                story.append(PageBreak())

        doc.build(story)
        return buf.getvalue()


# ── Convenience wrapper ────────────────────────────────────────────────────────

def generate_microbiome_pdf(df: pd.DataFrame) -> bytes:
    """Generate a microbiome PDF from *df* and return the raw PDF bytes."""
    return MicrobiomePDFGenerator(df).generate()

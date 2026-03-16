"""
PDF Report Generator for Medical Test Results
Generates professional, corporate-style PDF reports in English
"""

import pandas as pd
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, BaseDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether, Image, Frame, PageTemplate, Flowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
import os
import re
from svglib.svglib import svg2rlg
from parameter_descriptions import get_parameter_description
from parameter_subgroups import PARAMETER_SUBGROUPS
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import numpy as np


class SectionMarker(Flowable):
    """Invisible flowable that marks the current section for page headers"""
    def __init__(self, section_name, report_number=None, sample_info=None, super_category=None):
        Flowable.__init__(self)
        self.section_name = section_name
        self.report_number = report_number
        self.sample_info = sample_info
        self.super_category = super_category
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv._current_section = self.section_name
        self.canv._current_super_category = self.super_category
        if self.report_number is not None:
            self.canv._current_report_number = self.report_number
        # Always update sample_info (including clearing it with None for Laboratory Analysis)
        self.canv._blood_sample_info = self.sample_info


class PDFReportGenerator:
    """Generate professional medical PDF reports"""

    def __init__(self, data_path, output_dir="reports", styles_dir="styles/vistaSansOT", blood_data_path=None, clinical_data_path=None):
        """
        Initialize the PDF report generator

        Args:
            data_path: Path to the CSV data file
            output_dir: Directory to save generated reports
            styles_dir: Directory containing Vista Sans OT fonts
            blood_data_path: Path to blood_data_during_stay.csv (Chapter 1 data)
            clinical_data_path: Path to all_clinical_data.csv (Chapter 3 data)
        """
        self.data_path = data_path
        self.output_dir = output_dir
        self.styles_dir = styles_dir

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Load data
        self.df = pd.read_csv(data_path)

        # Load blood data if provided
        self.blood_df = None
        if blood_data_path and os.path.exists(blood_data_path):
            self.blood_df = pd.read_csv(blood_data_path)
            # Translate Spanish values to English
            VALUE_TRANSLATIONS = {'Negativo': 'Negative', 'Indicio': 'Trace'}
            self.blood_df['value'] = self.blood_df['value'].replace(VALUE_TRANSLATIONS)
            # Remove duplicate URIC ACID (mcmol/L) — already covered by mg/dL and µmol/L
            self.blood_df = self.blood_df[self.blood_df['parameter'] != 'URIC ACID (mcmol/L)']
            print(f"Blood data loaded: {len(self.blood_df)} rows")

        # Load clinical data if provided
        self.clinical_df = None
        if clinical_data_path and os.path.exists(clinical_data_path):
            self.clinical_df = pd.read_csv(clinical_data_path)
            self.clinical_df['datetime'] = pd.to_datetime(self.clinical_df['datetime'])
            # Filter to year 2026 only
            self.clinical_df = self.clinical_df[self.clinical_df['datetime'].dt.year == 2026]
            print(f"Clinical data loaded: {len(self.clinical_df)} rows (2026 only)")

        # Brand colors - must be set before styles
        self.PRIMARY_COLOR = colors.HexColor('#28b3d3')  # Cyan blue
        self.SECONDARY_COLOR = colors.HexColor('#F5F5F5')  # Light gray
        self.TEXT_COLOR = colors.HexColor('#000000')  # Black
        self.DARK_GRAY = colors.HexColor('#333333')  # Dark gray
        self.ALARM_COLOR = colors.HexColor('#333333')  # Dark gray for alarms

        # Register custom fonts
        self._register_fonts()

        # Setup styles
        self._setup_styles()

    def _register_fonts(self):
        """Register Vista Sans OT fonts"""
        try:
            font_variants = {
                'VistaSans-Regular': 'VistaSansOT-Reg.ttf',
                'VistaSans-Bold': 'VistaSansOT-Bold.ttf',
                'VistaSans-Light': 'VistaSansOT-Light.ttf',
                'VistaSans-Book': 'VistaSansOT-Book.ttf',
                'VistaSans-Medium': 'VistaSansOT-Medium.ttf',
            }

            for font_name, font_file in font_variants.items():
                font_path = os.path.join(self.styles_dir, font_file)
                if os.path.exists(font_path):
                    pdfmetrics.registerFont(TTFont(font_name, font_path))

            print("Vista Sans OT fonts registered successfully")
        except Exception as e:
            print(f"Warning: Could not register custom fonts: {e}")
            print("Using default fonts instead")

    def _setup_styles(self):
        """Setup paragraph styles"""
        self.styles = getSampleStyleSheet()

        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontName='VistaSans-Medium',
            fontSize=24,
            textColor=self.PRIMARY_COLOR,
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        # Section header style (e.g. "Archaeoma by NGS")
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontName='VistaSans-Book',
            fontSize=20,
            textColor=self.PRIMARY_COLOR,
            spaceAfter=12,
            spaceBefore=24,
            alignment=TA_LEFT
        ))

        # Body text style (Vista Sans for paragraphs)
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontName='VistaSans-Book',
            fontSize=10,
            textColor=self.TEXT_COLOR,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
            leading=14
        ))

        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Normal'],
            fontName='VistaSans-Light',
            fontSize=14,
            textColor=self.TEXT_COLOR,
            alignment=TA_CENTER,
            spaceAfter=20
        ))

        # Parameter description style
        self.styles.add(ParagraphStyle(
            name='ParamDescription',
            parent=self.styles['Normal'],
            fontName='VistaSans-Book',
            fontSize=9,
            textColor=self.DARK_GRAY,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            leading=12,
            leftIndent=10,
            rightIndent=10
        ))

        # Sub-group header style (e.g. "Overview & Diversity")
        self.styles.add(ParagraphStyle(
            name='SubGroupHeader',
            parent=self.styles['Normal'],
            fontName='VistaSans-Book',
            fontSize=15,
            textColor=self.DARK_GRAY,
            spaceAfter=10,
            spaceBefore=16,
            alignment=TA_LEFT
        ))

        # Super category title style (for "During your stay", "Laboratory Analysis")
        self.styles.add(ParagraphStyle(
            name='SuperCategoryTitle',
            parent=self.styles['Heading1'],
            fontName='VistaSans-Book',
            fontSize=26,
            textColor=self.PRIMARY_COLOR,
            spaceAfter=20,
            spaceBefore=10,
            alignment=TA_LEFT
        ))

        # Chapter title style (kept for backward compatibility)
        self.styles.add(ParagraphStyle(
            name='ChapterTitle',
            parent=self.styles['Heading1'],
            fontName='VistaSans-Book',
            fontSize=22,
            textColor=self.PRIMARY_COLOR,
            spaceAfter=20,
            spaceBefore=10,
            alignment=TA_LEFT
        ))

    def _create_header_footer(self, canvas, doc, patient_name, fake_id, report_date, validation_date=''):
        """Create header and footer for each page"""
        canvas.saveState()

        # Header - show super_category • section_name
        section_name = getattr(canvas, '_current_section', '')
        super_category = getattr(canvas, '_current_super_category', None)
        if section_name or super_category:
            canvas.setFont('Helvetica', 12)
            if super_category:
                # Draw super_category in dark gray
                canvas.setFillColor(self.DARK_GRAY)
                canvas.drawString(50, letter[1] - 40, super_category)

                # Only show bullet and section_name if section_name is not empty
                if section_name:
                    # Calculate width of super_category to position the bullet and section
                    super_width = canvas.stringWidth(super_category, 'Helvetica', 12)

                    # Draw bullet and section_name in lighter gray
                    canvas.setFillColor(colors.HexColor('#999999'))
                    canvas.drawString(50 + super_width, letter[1] - 40, f"   •   {section_name}")
            else:
                # Just section name, dark gray
                canvas.setFillColor(self.DARK_GRAY)
                canvas.drawString(50, letter[1] - 40, section_name)

        # Patient info in top right (using Helvetica for metadata, not Vista Sans)
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(self.TEXT_COLOR)
        canvas.drawRightString(letter[0] - 50, letter[1] - 30, f"Patient: {patient_name}")

        # Report ID info (different format for "During your stay" vs "Laboratory Analysis")
        sample_info = getattr(canvas, '_blood_sample_info', None)
        if sample_info:
            # During your stay: show blood sample IDs
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(self.DARK_GRAY)
            y_position = letter[1] - 43
            for date, sid in sample_info:
                canvas.drawRightString(letter[0] - 50, y_position, f"Report ID: {date} - {sid}")
                y_position -= 12  # Move down for next line
        else:
            # Laboratory Analysis: show report number
            report_number = getattr(canvas, '_current_report_number', '')
            if report_number:
                canvas.setFont('Helvetica', 8)
                canvas.setFillColor(self.DARK_GRAY)
                canvas.drawRightString(letter[0] - 50, letter[1] - 43, f"Report ID: {report_number}")

        # Header line
        canvas.setStrokeColor(self.PRIMARY_COLOR)
        canvas.setLineWidth(0.5)
        canvas.line(50, letter[1] - 70, letter[0] - 50, letter[1] - 70)

        # Footer
        canvas.setFont('VistaSans-Book', 10)
        canvas.setFillColor(self.DARK_GRAY)
        canvas.drawRightString(letter[0] - 50, 30, f"{doc.page}")

        # Footer line
        # canvas.setStrokeColor(self.PRIMARY_COLOR)
        # canvas.setLineWidth(1)
        # canvas.line(50, 50, letter[0] - 50, 50)

        canvas.restoreState()

    def _draw_cover_page(self, canvas, doc, patient_name='', report_groups=None, blood_cover_info=None):
        """Draw cover page background with golden ratio split and patient info"""
        canvas.saveState()
        page_width, page_height = letter

        # Background #ecebe5 on the bottom 38.2% (1 - 0.618)
        bg_height = page_height * 0.382
        canvas.setFillColor(colors.HexColor('#ecebe5'))
        canvas.rect(0, 0, page_width, bg_height, stroke=0, fill=1)

        # Patient name at top of colored zone
        y = bg_height - 40
        canvas.setFont('VistaSans-Book', 13)
        canvas.setFillColor(self.DARK_GRAY)
        canvas.drawString(60, y, f"Patient: {patient_name}")
        y -= 10
        canvas.setStrokeColor(colors.HexColor('#d0cfcb'))
        canvas.setLineWidth(0.3)
        canvas.line(60, y, page_width - 60, y)
        y -= 20

        # Two fixed columns
        col1_left = 60
        col2_left = page_width / 2 + 10

        # === COLUMN 1: During your stay ===
        col_y = y
        canvas.setFont('VistaSans-Book', 11)
        canvas.setFillColor(self.DARK_GRAY)
        canvas.drawString(col1_left, col_y, "During your stay")
        col_y -= 8
        canvas.setStrokeColor(colors.HexColor('#d0cfcb'))
        canvas.setLineWidth(0.3)
        canvas.line(col1_left, col_y, col2_left - 20, col_y)
        col_y -= 14

        if blood_cover_info:
            # Split blood groups into sub-columns within "During your stay"
            sub_col_width = (col2_left - 20 - col1_left) / len(blood_cover_info)
            for i, group in enumerate(blood_cover_info):
                sub_left = col1_left + sub_col_width * i
                sub_y = col_y

                # Report ID and Collection date
                canvas.setFont('VistaSans-Book', 8)
                canvas.setFillColor(self.DARK_GRAY)
                canvas.drawString(sub_left, sub_y, f"Report ID: {group['report_number']}")
                sub_y -= 11
                canvas.drawString(sub_left, sub_y, f"Collection: {group['sample_date']}")
                sub_y -= 14

                # Categories as a list
                for cat in group['categories']:
                    canvas.drawString(sub_left + 10, sub_y, f"- {cat}")
                    sub_y -= 11

                # Validation date
                sub_y -= 3
                canvas.drawString(sub_left, sub_y, f"Validation: {group['validation_date']}")

        # === COLUMN 2: Supplementary analyses ===
        col_y = y
        canvas.setFont('VistaSans-Book', 11)
        canvas.setFillColor(self.DARK_GRAY)
        canvas.drawString(col2_left, col_y, "Supplementary analyses")
        col_y -= 8
        canvas.setStrokeColor(colors.HexColor('#d0cfcb'))
        canvas.setLineWidth(0.3)
        canvas.line(col2_left, col_y, page_width - 60, col_y)
        col_y -= 14

        if report_groups:
            for group in report_groups:
                # Report ID and Collection date
                canvas.setFont('VistaSans-Book', 8)
                canvas.setFillColor(self.DARK_GRAY)
                canvas.drawString(col2_left, col_y, f"Report ID: {group['report_number']}")
                col_y -= 11
                canvas.drawString(col2_left, col_y, f"Collection: {group['sample_date']}")
                col_y -= 14

                # Categories as a list
                for cat in group['categories']:
                    canvas.drawString(col2_left + 10, col_y, f"- {cat}")
                    col_y -= 11

                # Validation date
                col_y -= 3
                canvas.drawString(col2_left, col_y, f"Validation: {group['validation_date']}")
                col_y -= 16

        canvas.restoreState()

    def _deduplicate_data(self, category_data):
        """
        Deduplicate data by keeping one row per Test.
        For tests with multiple Result variables (Result1, Result2, etc.),
        prioritizes Result1. Within each (Test, variable) combination,
        keeps the row with most complete unit information.
        """
        # First, group by Test and variable, pick best row for each combination
        temp_deduplicated = []

        for (test_name, variable), group in category_data.groupby(['Test', 'variable']):
            if len(group) == 1:
                temp_deduplicated.append(group.iloc[0])
            else:
                # Multiple rows for same test and variable - pick the most complete one
                best_row = None
                for _, row in group.iterrows():
                    has_unit1 = pd.notna(row['Unit1']) and row['Unit1']
                    has_unit2 = pd.notna(row['Unit2']) and row['Unit2']

                    if best_row is None:
                        best_row = row
                    elif has_unit1 and has_unit2:
                        best_row = row
                        break
                    elif has_unit2 and not (pd.notna(best_row['Unit2']) and best_row['Unit2']):
                        best_row = row

                temp_deduplicated.append(best_row)

        temp_df = pd.DataFrame(temp_deduplicated)

        # Now, for each Test, keep only one row (prioritize Result1 over Result2, etc.)
        final_deduplicated = []

        for test_name, group in temp_df.groupby('Test'):
            if len(group) == 1:
                final_deduplicated.append(group.iloc[0])
            else:
                # Multiple variables (Result1, Result2, etc.) - prioritize Result1
                result1_rows = group[group['variable'] == 'Result1']
                if not result1_rows.empty:
                    final_deduplicated.append(result1_rows.iloc[0])
                else:
                    # No Result1, take the first one
                    final_deduplicated.append(group.iloc[0])

        return pd.DataFrame(final_deduplicated)

    # Categories that use flat plain-white style instead of parent/child hierarchy
    FLAT_CATEGORIES = {'Hemogram', 'Immune Status', 'Stress and Biorhythm in Saliva'}

    def _build_single_table(self, rows_df, hierarchical=True, collection_date=None):
        """Build a styled table from a DataFrame of rows"""
        # Use formatted collection date as column header instead of "Result"
        result_header = 'Result'
        if collection_date:
            try:
                dt = pd.to_datetime(collection_date, dayfirst=True)
                result_header = dt.strftime('%d/%m/%y')
            except Exception:
                result_header = 'Result'
        table_data = [['Parameter', result_header, 'Unit', 'Reference Range', '']]

        # Track which rows are parents vs children for styling
        is_child_row = []

        for _, row in rows_df.iterrows():
            param_name = row['Test']
            is_child = param_name.startswith('- ')

            if hierarchical and is_child:
                display_name = '     ' + param_name
            else:
                display_name = param_name

            is_child_row.append(is_child)

            result_value = str(row['value'])

            units = []
            if pd.notna(row['Unit1']) and row['Unit1']:
                units.append(str(row['Unit1']))
            if pd.notna(row['Unit2']) and row['Unit2']:
                units.append(str(row['Unit2']))
            unit_str = ' / '.join(units) if units else '-'

            min_ref = str(row['MinReferenceValue']) if pd.notna(row['MinReferenceValue']) else '-'
            max_ref = str(row['MaxReferenceValue']) if pd.notna(row['MaxReferenceValue']) else '-'
            ref_range = f"{min_ref} - {max_ref}" if min_ref != '-' or max_ref != '-' else '-'

            alarm = row['Alarm']
            status = '!' if (alarm == 'Verdadero' or alarm is True or alarm == 'True') else ''

            table_data.append([display_name, result_value, unit_str, ref_range, status])

        table = Table(table_data, colWidths=[2.8*inch, 1.2*inch, 1.2*inch, 1.4*inch, 0.6*inch])

        light_border = colors.HexColor('#E0E0E0')
        table_style = TableStyle([
            # ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EAF6FB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#00000')),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), self.TEXT_COLOR),
            ('LINEBELOW', (0, 0), (-1, 0), 0.1, colors.HexColor('#00000')),
        ])

        has_children = any(is_child_row)
        if hierarchical and has_children:
            # Parent/child mode: background + bold on parents, indent on children
            for i, is_child in enumerate(is_child_row):
                row_idx = i + 1
                if not is_child:
                    table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), self.SECONDARY_COLOR)
                else:
                    table_style.add('LEFTPADDING', (0, row_idx), (0, row_idx), 24)

        for i, row in enumerate(rows_df.itertuples(), start=1):
            if row.Alarm == 'Verdadero' or row.Alarm is True or row.Alarm == 'True':
                table_style.add('TEXTCOLOR', (4, i), (4, i), self.ALARM_COLOR)

        table.setStyle(table_style)
        return table

    def _create_results_table(self, category_data, category_name, report_number=None, super_category=None, sample_date=None):
        """Create formatted tables for test results, grouped by sub-category"""
        elements = []

        CATEGORY_DESCRIPTIONS = {
            "Hemogram": (
                "The hemogram, or complete blood count (CBC), provides a comprehensive overview of the cellular "
                "components of blood, including red blood cells, white blood cells, and platelets. It is a fundamental "
                "diagnostic tool used to assess overall health, detect infections, monitor chronic conditions, and "
                "evaluate the blood's oxygen-carrying capacity and clotting potential."
            ),
            "Immune Status": (
                "The immune status panel evaluates the composition and balance of the body's immune cells, including "
                "various lymphocyte subsets such as T cells, B cells, and natural killer (NK) cells. This analysis helps "
                "assess immunocompetence, detect immune deficiencies or dysregulations, and monitor the body's defense "
                "mechanisms against infections and disease."
            ),
            "Bacterioma by NGS": (
                "The bacterioma analysis uses next-generation sequencing (NGS) to identify and quantify the bacterial "
                "communities present in the gut microbiome. This comprehensive profiling reveals the diversity, "
                "abundance, and relative proportions of bacterial species, providing insights into digestive health, "
                "metabolic function, and potential dysbiosis patterns."
            ),
            "Archaeoma by NGS": (
                "The archaeoma analysis uses next-generation sequencing (NGS) to characterize the archaeal populations "
                "within the gut. Archaea, particularly methanogens, play a key role in gut gas metabolism and interact "
                "closely with bacterial communities. Their assessment provides valuable information about the balance "
                "and metabolic activity of the intestinal ecosystem."
            ),
            "Intestinal Dysbiosis by NGS": (
                "This panel assesses intestinal dysbiosis through next-generation sequencing (NGS), evaluating the "
                "overall balance and diversity of the gut microbial community. It identifies deviations from a healthy "
                "microbiome composition, highlighting potential imbalances that may be associated with gastrointestinal "
                "disorders, inflammation, or impaired nutrient absorption."
            ),
            "Mycobiome by NGS": (
                "The mycobiome analysis uses next-generation sequencing (NGS) to profile the fungal communities "
                "residing in the gut. Fungi, though present in smaller quantities than bacteria, can significantly "
                "influence gut health and immune responses. This panel detects pathogenic or opportunistic fungal "
                "species and evaluates overall fungal diversity."
            ),
            "Parasitome by NGS": (
                "The parasitome analysis employs next-generation sequencing (NGS) to detect and identify parasitic "
                "organisms within the gastrointestinal tract. This highly sensitive molecular approach can reveal "
                "parasitic infections that may be missed by conventional microscopy, including protozoa and helminths "
                "that can affect digestive function and overall health."
            ),
            "Virome by NGS": (
                "The virome analysis uses next-generation sequencing (NGS) to characterize the viral communities "
                "present in the gut. The intestinal virome, largely composed of bacteriophages, plays a crucial role "
                "in shaping bacterial populations and modulating immune responses. This panel provides insights into "
                "the viral landscape and its potential impact on gut ecosystem stability."
            ),
            "Stress and Biorhythm in Saliva": (
                "This panel evaluates key biomarkers in saliva to assess the body's stress response and circadian "
                "rhythm regulation. Cortisol and DHEA reflect adrenal function and the hypothalamic-pituitary-adrenal "
                "(HPA) axis activity, while melatonin indicates sleep-wake cycle regulation. Alpha-amylase serves as "
                "a marker of sympathetic nervous system activation, providing a comprehensive view of the body's "
                "neuroendocrine stress adaptation."
            ),
            "Stool Sample": (
                "The stool sample analysis evaluates various physical and biochemical properties of the stool, "
                "providing information about digestive function, intestinal inflammation, and gut barrier integrity. "
                "These markers help identify malabsorption, inflammatory conditions, and other gastrointestinal "
                "disorders that may affect overall health."
            ),
        }

        # Mark current section for page header
        elements.append(SectionMarker(category_name, report_number=report_number, super_category=super_category))

        # Add section header
        elements.append(Paragraph(f"{category_name}", self.styles['SectionHeader']))
        elements.append(Spacer(1, 6))

        # Add category description
        description = CATEGORY_DESCRIPTIONS.get(category_name)
        if description:
            elements.append(Paragraph(description, self.styles['ParamDescription']))
            elements.append(Spacer(1, 10))

        # Deduplicate data first
        category_data = self._deduplicate_data(category_data)

        # Determine table style: flat for certain categories, hierarchical for others
        is_hierarchical = category_name not in self.FLAT_CATEGORIES

        # Check if sub-groups are defined for this category
        subgroups = PARAMETER_SUBGROUPS.get(category_name)

        if subgroups:
            placed_tests = set()

            for subgroup_name, test_names in subgroups:
                # Filter rows for this sub-group (preserve defined order)
                subgroup_rows = []
                for test_name in test_names:
                    matching = category_data[category_data['Test'] == test_name]
                    if not matching.empty:
                        subgroup_rows.append(matching.iloc[0])
                        placed_tests.add(test_name)

                if not subgroup_rows:
                    continue

                subgroup_df = pd.DataFrame(subgroup_rows)

                # Sub-group header + table kept together
                elements.append(KeepTogether([
                    Paragraph(f"&gt;   {subgroup_name}", self.styles['SubGroupHeader']),
                    Spacer(1, 3),
                    self._build_single_table(subgroup_df, hierarchical=is_hierarchical, collection_date=sample_date),
                ]))
                elements.append(Spacer(1, 8))

            # Any remaining tests not in a defined sub-group
            remaining = category_data[~category_data['Test'].isin(placed_tests)]
            if not remaining.empty:
                elements.append(KeepTogether([
                    Paragraph("&gt;   Other", self.styles['SubGroupHeader']),
                    Spacer(1, 3),
                    self._build_single_table(remaining, hierarchical=is_hierarchical, collection_date=sample_date),
                ]))
                elements.append(Spacer(1, 8))
        else:
            # No sub-groups defined: single table
            elements.append(self._build_single_table(category_data, hierarchical=is_hierarchical, collection_date=sample_date))
            elements.append(Spacer(1, 15))

        return elements

    # Unit mapping for blood parameters (extracted from source lab PDFs)
    BLOOD_PARAMETER_UNITS = {
        # Haematology - Red series
        "RED BLOOD CELL COUNT": "x10<super>6</super>/mm\u00b3",
        "HAEMOGLOBIN": "g/dL",
        "HCT": "%",
        "MCV": "fL",
        "MCH": "pg",
        "MCHC": "g/dL",
        "RDW": "%",
        # Haematology - White series
        "LEUCOCYTES": "x10\u00b3/mm\u00b3",
        "NEUTROPHIL%": "%",
        "LYMPHOCYTE%": "%",
        "MONOCYTE%": "%",
        "EOSINOPHILS%": "%",
        "BASOPHILES%": "%",
        "GRANULOCYTES ABS": "x10\u00b3/mm\u00b3",
        "LYMPHOCYTES ABS": "x10\u00b3/mm\u00b3",
        "MONOCYTES ABS": "x10\u00b3/mm\u00b3",
        "EOSINOPHILS ABS": "x10\u00b3/mm\u00b3",
        "BASOPHILS ABS": "x10\u00b3/mm\u00b3",
        # Haematology - Platelet series
        "PLATELETS": "x10\u00b3/mm\u00b3",
        "MEAN PLATELET VOLUME": "fL",
        # Erythrocyte sedimentation
        "SEDIMENTATION RATE (1st HOUR)": "mm",
        # Biochemistry - Hydrocarbon metabolism
        "GLUCOSE (mg/dL)": "mg/dL",
        "GLUCOSE (mmol/L)": "mmol/L",
        "HAEMOGLOBIN A1C (%)": "%",
        "HAEMOGLOBIN A1C (IFCC)": "mmol/mol",
        # Biochemistry - Lipid metabolism
        "TOTAL CHOLESTEROL (mg/dL)": "mg/dL",
        "TOTAL CHOLESTEROL (mmol/L)": "mmol/L",
        "HDL CHOLESTEROL (mg/dL)": "mg/dL",
        "HDL CHOLESTEROL (mmol/L)": "mmol/L",
        "LDL CHOLESTEROL (mg/dL)": "mg/dL",
        "LDL CHOLESTEROL (mmol/L)": "mmol/L",
        "TRIGLYCERIDES (mg/dL)": "mg/dL",
        "TRIGLYCERIDES (mmol/L)": "mmol/L",
        "LDL oxidada": "ng/mL",
        "LIPOPROTEIN a-LP (a)": "mg/dL",
        "APOLIPOPROTEIN A1": "mg/dL",
        "APOLIPOPROTEIN B": "mg/dL",
        # Biochemistry - Proteins
        "Prealb\u00famina": "mg/dL",
        "ALBUMIN": "g/L",
        "CRP (C-REACTIVE PROTEIN)": "mg/L",
        "C-REACTIVE PROTEIN (ULTRASENSITIVE)": "mg/L",
        # Biochemistry - Renal function tests
        "URIC ACID (mg/dL)": "mg/dL",
        "URIC ACID (\u00b5mol/L)": "\u00b5mol/L",
        "CREATININE (mg/dL)": "mg/dL",
        "CREATININE (mcmol/L)": "mcmol/L",
        "UREA (mg/dL)": "mg/dL",
        "UREA (mmol/L)": "mmol/L",
        # Biochemistry - Ions
        "SODIUM": "mEq/L",
        "POTASSIUM": "mEq/L",
        "MAGNESIUM (mg/dL)": "mg/dL",
        "MAGNESIUM (mmol/L)": "mmol/L",
        # Biochemistry - Liver function tests
        "TOTAL BILIRRUBIN (mg/dL)": "mg/dL",
        "TOTAL BILIRRUBIN (mcmol/L)": "mcmol/L",
        "DIRECT BILIRRUBIN": "mg/dL",
        "GPT/ALT": "U/L",
        "GOT/AST": "U/L",
        "GAMMA-GT": "U/L",
        "ALKALINE PHOSPHATE": "U/L",
        # Biochemistry - Iron metabolism
        "IRON (\u00b5g/dL)": "\u00b5g/dL",
        "IRON (mcmol/L)": "mcmol/L",
        "FERRITINE": "ng/mL",
        "TRANSFERRIN": "mg/dL",
        "TRANSFERRIN SATURATION INDEX": "%",
        # Biochemistry - Phosphocalcic metabolism
        "CALCIUM (mg/dL)": "mg/dL",
        "CALCIUM (mmol/L)": "mmol/L",
        # Biochemistry - Vitamins
        "VITAMIN B12": "pg/mL",
        "HOMOCYSTEIN": "\u00b5mol/L",
        "25-HYDROXYVITAMIN D": "ng/mL",
        # Biochemistry - Pancreatic function tests
        "AMYLASE": "U/L",
        "LIPASE": "U/L",
        # Immunology - Antibodies
        "THYROGLOBULIN ANTIBODY (anti-TG)": "UI/mL",
        "MICROSOMAL ANTIBODY (anti-TPO)": "UI/mL",
        # Endocrinology - Thyroid hormones
        "TSH (Tirotropin)": "mU/L",
        "THYROXINE (T4)": "\u00b5g/dL",
        "FREE THYROXINE": "ng/dL",
        "TOTAL T3 (Triyodotironine)": "\u00b5g/L",
        "T3 - FREE": "pg/mL",
        "T3 reverse": "ng/dL",
        # Endocrinology - Sex hormones
        "17 - BETA ESTRADIOL": "pg/mL",
        "PROGESTERONE": "\u00b5g/L",
        "TOTAL TESTOSTERONE": "ng/mL",
        "FREE TESTOSTERONE": "pg/mL",
        "% Free Testosterone A": "%",
        "Estimated free testosterone": "ng/dL",
        "Bioavailable testosterone": "ng/mL",
        "DHEA (DEHYDROEPIANDROSTERONE) ng/mL": "ng/mL",
        "DHEA (DEHYDROEPIANDROSTERONE) nmol/L": "nmol/L",
        "Androstenedione delta 4": "ng/mL",
        "Pregnenolona": "ng/dL",
        # Endocrinology - Adrenal hormones
        "BASAL CORTISOL (HYDROCORTISONE)": "\u00b5g/dL",
        "DEHYDROEPIANDROSTERONE-S": "\u00b5mol/L",
        # Endocrinology - Pituitary Hormones
        "SEX HORMON BINDING GLOBULIN (SHBG)": "nmol/L",
        "HUMAN GROWTH HORMONE (HGH)": "ng/mL",
        "LEUTENISING HORMONE (LH)": "mUI/mL",
        "FSH - FOLICLE STIMULATING HORMONE": "mUI/mL",
        "PROLACTIN": "ng/mL",
        # Endocrinology - Other
        "SOMATOMEDINE C (IgF1)": "ng/mL",
        "BASAL INSULIN (IRI)": "mU/L",
        "C PEPTIDE": "ng/mL",
        "C PEPTIDE (pmol/L)": "pmol/L",
        "\u00cdndice HOMA (resistencia a la insulina)": "",
        # Tumor Markers
        "TOTAL PSA": "ng/mL",
        "FREE PSA": "ng/mL",
        "FREE PSA/TOTAL PSA INDEX": "",
        # Serology
        "HEPATITIS C ANTIBODIES": "S/CO",
        # Urine testing
        "pH": "",
        "SPECIFIC GRAVITY": "",
        "GLUCOSE - URINE": "mg/dL",
        "TOTAL PROTEINS - URINE": "",
        "UROBILIGEN": "mg/dL",
        "KETONES": "",
        "NITRITES": "",
        "RED BLOOD CELL COUNT": "/\u00b5L",
        "WHITE CELL COUNT": "/\u00b5L",
        "URINE MICROSCOPE EXAM": "",
    }

    # Translation map for non-English parameter names
    PARAMETER_TRANSLATIONS = {
        "Prealb\u00famina": "Prealbumin",
        "LDL oxidada": "Oxidized LDL",
        "Pregnenolona": "Pregnenolone",
        "\u00cdndice HOMA (resistencia a la insulina)": "HOMA Index",
    }

    # Known unit strings that appear in parentheses at end of parameter names
    _KNOWN_UNIT_SUFFIXES = {
        'mg/dL', 'mmol/L', '\u00b5mol/L', 'mcmol/L', '%', 'IFCC',
        'pmol/L', 'nmol/L', 'ng/mL', 'pg/mL', '\u00b5g/dL',
    }

    # White series hierarchy
    WHITE_SERIES_PARENTS = {"LEUCOCYTES"}
    WHITE_SERIES_CHILDREN = {
        "NEUTROPHIL%", "LYMPHOCYTE%", "MONOCYTE%", "EOSINOPHILS%", "BASOPHILES%",
    }

    def _get_blood_unit(self, parameter_name, category):
        """Get unit for a blood parameter, using category to disambiguate."""
        # Disambiguate parameters that appear in multiple categories
        if parameter_name in ("RED BLOOD CELL COUNT", "WHITE CELL COUNT"):
            if 'Urine' in category or 'urine' in category:
                return "/\u00b5L"
            else:
                return "x10<super>6</super>/mm\u00b3" if parameter_name == "RED BLOOD CELL COUNT" else "x10\u00b3/mm\u00b3"
        # Direct match from dictionary
        unit = self.BLOOD_PARAMETER_UNITS.get(parameter_name)
        if unit is not None:
            return unit
        return "-"

    def _get_display_name(self, param_name):
        """Get clean display name: translate and strip unit suffixes from param names."""
        name = self.PARAMETER_TRANSLATIONS.get(param_name, param_name)

        # Strip trailing (unit) pattern when parens contain a known unit
        match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', name)
        if match:
            base, paren = match.group(1).strip(), match.group(2).strip()
            if paren in self._KNOWN_UNIT_SUFFIXES:
                return base

        # Strip trailing unit after parens: e.g. "DHEA (DEHYDROEPIANDROSTERONE) ng/mL"
        name = re.sub(r'\s+(ng/mL|nmol/L)\s*$', '', name)

        return name

    def _build_blood_table(self, category_data, dates, category_name="",
                           is_microscope=False, parent_params=None, child_params=None):
        """Build a table for blood data with date-based columns + Unit + Status.

        Columns: Parameter | date1 [| date2] | Unit | Reference Range | Status
        Microscope exam: Parameter | Date | Result  (double-index rows)

        Args:
            parent_params: set of parameter names styled as parent rows (gray bg)
            child_params: set of parameter names styled as child rows (indented)
        """
        if parent_params is None:
            parent_params = set()
        if child_params is None:
            child_params = set()

        parameters = category_data['parameter'].drop_duplicates().tolist()

        # Build lookup: parameter -> {date -> value}
        value_map = {}
        for _, row in category_data.iterrows():
            param = row['parameter']
            date = row['reception_date']
            if param not in value_map:
                value_map[param] = {}
            value_map[param][date] = row

        sorted_dates = sorted(dates, key=lambda d: pd.to_datetime(d, dayfirst=True))

        # Shorten year in display: "16/01/2026" -> "16/01/26"
        display_dates = [re.sub(r'/(\d{4})$', lambda m: '/' + m.group(1)[2:], d) for d in sorted_dates]

        # --- Paragraph styles (matching Chapter 2 table look) ---
        sty_param = ParagraphStyle(
            name='_bp', fontName='Helvetica', fontSize=9, leading=11,
            textColor=self.TEXT_COLOR)
        sty_param_child = ParagraphStyle(
            name='_bpc', fontName='Helvetica', fontSize=9, leading=11,
            textColor=self.TEXT_COLOR, leftIndent=16)
        sty_param_parent = ParagraphStyle(
            name='_bpp', fontName='Helvetica', fontSize=9, leading=11,
            textColor=self.TEXT_COLOR)
        sty_val = ParagraphStyle(
            name='_bv', fontName='Helvetica', fontSize=9, leading=11,
            alignment=TA_CENTER, textColor=self.TEXT_COLOR)
        sty_val_alarm = ParagraphStyle(
            name='_bva', fontName='Helvetica-Bold', fontSize=9, leading=11,
            alignment=TA_CENTER, textColor=self.ALARM_COLOR)
        sty_micro = ParagraphStyle(
            name='_bm', fontName='Helvetica', fontSize=8, leading=10,
            alignment=TA_LEFT, textColor=self.TEXT_COLOR)
        sty_hdr = ParagraphStyle(
            name='_bh', fontName='Helvetica', fontSize=10, leading=12,
            alignment=TA_CENTER)
        sty_hdr_l = ParagraphStyle(
            name='_bhl', fontName='Helvetica', fontSize=10, leading=12)

        # =====================================================================
        # Microscope exam: separate table layout (Parameter | Date | Result)
        # =====================================================================
        if is_microscope:
            col_widths = [2.0*inch, 0.8*inch, 4.4*inch]
            header = [
                Paragraph('Parameter', sty_hdr_l),
                Paragraph('Date', sty_hdr),
                Paragraph('Result', sty_hdr),
            ]
            table_data = [header]

            for param in parameters:
                row_entries = value_map.get(param, {})
                if not row_entries:
                    continue

                display_name = self._get_display_name(param)
                first_row = True

                for date, disp_date in zip(sorted_dates, display_dates):
                    if date not in row_entries:
                        continue
                    result_val = str(row_entries[date]['value'])

                    if first_row:
                        name_para = Paragraph(display_name, sty_param)
                        first_row = False
                    else:
                        name_para = ''

                    table_data.append([
                        name_para,
                        Paragraph(disp_date, sty_val),
                        Paragraph(result_val, sty_micro),
                    ])

            table = Table(table_data, colWidths=col_widths)
            table_style = TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, 0), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('LINEBELOW', (0, 0), (-1, 0), 0.1, colors.HexColor('#000000')),
            ])
            table.setStyle(table_style)
            return table

        # =====================================================================
        # Normal table layout (Parameter | date1 [| date2] | Unit | Ref | Status)
        # =====================================================================

        # Build header row (total width = 7.2 inches, matching Chapter 2)
        if len(sorted_dates) >= 2:
            header = [
                Paragraph('Parameter', sty_hdr_l),
                Paragraph(display_dates[0], sty_hdr),
                Paragraph(display_dates[1], sty_hdr),
                Paragraph('Unit', sty_hdr),
                Paragraph('Reference Range', sty_hdr),
                Paragraph('', sty_hdr),
            ]
            col_widths = [2.8*inch, 0.9*inch, 0.9*inch, 0.8*inch, 1.4*inch, 0.4*inch]
        else:
            header = [
                Paragraph('Parameter', sty_hdr_l),
                Paragraph(display_dates[0], sty_hdr),
                Paragraph('Unit', sty_hdr),
                Paragraph('Reference Range', sty_hdr),
                Paragraph('', sty_hdr),
            ]
            col_widths = [2.8*inch, 1.2*inch, 1.2*inch, 1.4*inch, 0.6*inch]

        table_data = [header]
        parent_row_indices = []
        prev_display_name = None

        for param in parameters:
            row_entries = value_map.get(param, {})
            any_row = next(iter(row_entries.values()), None)
            if any_row is None:
                continue

            # --- Reference range: use < / > when only one bound exists ---
            min_ref = str(any_row['rangeMin']).strip() if pd.notna(any_row['rangeMin']) and str(any_row['rangeMin']).strip() else ''
            max_ref = str(any_row['rangeMax']).strip() if pd.notna(any_row['rangeMax']) and str(any_row['rangeMax']).strip() else ''

            if min_ref and max_ref:
                ref_range = f"{min_ref} - {max_ref}"
            elif max_ref and not min_ref:
                ref_range = f"&lt; {max_ref}"
            elif min_ref and not max_ref:
                ref_range = f"&gt; {min_ref}"
            else:
                ref_range = '-'

            # --- Pre-compute alarm status ---
            is_alarm = False
            for date in sorted_dates:
                if date in row_entries:
                    try:
                        numeric_val = float(str(row_entries[date]['value']))
                        if min_ref:
                            if numeric_val < float(min_ref):
                                is_alarm = True
                        if max_ref:
                            if numeric_val > float(max_ref):
                                is_alarm = True
                    except (ValueError, TypeError):
                        pass

            unit = self._get_blood_unit(param, category_name)

            # --- Display name: strip unit suffix, translate, blank duplicates ---
            display_name = self._get_display_name(param)
            if display_name == prev_display_name:
                show_name = ''
            else:
                show_name = display_name
            prev_display_name = display_name

            # --- Choose paragraph style for parameter name ---
            is_parent = param in parent_params
            is_child = param in child_params
            if is_parent:
                name_para = Paragraph(show_name, sty_param_parent) if show_name else ''
            elif is_child:
                name_para = Paragraph(show_name, sty_param_child) if show_name else ''
            else:
                name_para = Paragraph(show_name, sty_param) if show_name else ''

            # --- Value and status style (bold for alarms) ---
            v_sty = sty_val_alarm if is_alarm else sty_val
            status_text = '!' if is_alarm else ''

            row = [name_para]

            for date in sorted_dates:
                if date in row_entries:
                    row.append(Paragraph(str(row_entries[date]['value']), v_sty))
                else:
                    row.append(Paragraph('-', v_sty))
            row.extend([
                Paragraph(unit, sty_val),
                Paragraph(ref_range, sty_val),
                Paragraph(status_text, v_sty),
            ])

            if is_parent:
                parent_row_indices.append(len(table_data))
            table_data.append(row)

        table = Table(table_data, colWidths=col_widths)

        table_style = TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, 0), 0.1, colors.HexColor('#000000')),
        ])

        # Parent row styling (gray background, matching Chapter 2)
        for row_idx in parent_row_indices:
            table_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), self.SECONDARY_COLOR)

        table.setStyle(table_style)
        return table

    def _create_blood_results_section(self, patient_blood_data, super_category=None, sample_info=None):
        """Create Blood Analysis sections with hierarchical category grouping."""
        elements = []

        dates = sorted(
            patient_blood_data['reception_date'].unique().tolist(),
            key=lambda d: pd.to_datetime(d, dayfirst=True)
        )

        # Define category display order (flat list used to determine ordering)
        BLOOD_CATEGORY_ORDER = [
            "Haematology - Red series",
            "Haematology - White series",
            "Haematology - Platelet series",
            "Haematology - Erythrocyte sedimentation",
            "Biochemistry - Hydrocarbon metabolism",
            "Biochemistry - Lipid metabolism",
            "Biochemistry - Proteins",
            "Biochemistry - Renal function tests",
            "Biochemistry - Ions",
            "Biochemistry - Liver function tests",
            "Biochemistry - Iron metabolism",
            "Biochemistry - Phosphocalcic metabolism",
            "Biochemistry - Vitamins",
            "Biochemistry - Pancreatic function tests",
            "Immunology - Antibodies",
            "Endocrinology - Thyroid hormones",
            "Endocrinology - Sex hormones",
            "Endocrinology - Adrenal hormones",
            "Endocrinology - Pituitary Hormones",
            "Endocrinology - Other",
            "Tumor Markers",
            "Serology",
            "Urine testing - Chemical analysis",
            "Urine testing - Microscope exam",
        ]

        available_cats = patient_blood_data['category'].unique()
        categories = [c for c in BLOOD_CATEGORY_ORDER if c in available_cats]
        categories += [c for c in available_cats if c not in BLOOD_CATEGORY_ORDER]

        # Group categories by parent (e.g. "Biochemistry - Vitamins" -> parent "Biochemistry", sub "Vitamins")
        BLOOD_PARENT_DISPLAY = {'Haematology': 'Hemogram'}
        from collections import OrderedDict
        grouped = OrderedDict()
        for cat in categories:
            if ' - ' in cat:
                parent, sub = cat.split(' - ', 1)
            else:
                parent, sub = cat, None
            if parent not in grouped:
                grouped[parent] = []
            grouped[parent].append((cat, sub))

        for parent, subcats in grouped.items():
            # Section header for the parent category (with display name mapping)
            display_parent = BLOOD_PARENT_DISPLAY.get(parent, parent)
            elements.append(SectionMarker(display_parent, super_category=super_category, sample_info=sample_info))
            elements.append(Paragraph(display_parent, self.styles['SectionHeader']))
            elements.append(Spacer(1, 6))

            for full_cat, sub_name in subcats:
                cat_data = patient_blood_data[patient_blood_data['category'] == full_cat]

                # Determine special table options per category
                tbl_kwargs = dict(category_name=full_cat)
                if 'White series' in full_cat:
                    tbl_kwargs['parent_params'] = self.WHITE_SERIES_PARENTS
                    tbl_kwargs['child_params'] = self.WHITE_SERIES_CHILDREN
                if 'Microscope exam' in full_cat:
                    tbl_kwargs['is_microscope'] = True

                table = self._build_blood_table(cat_data, dates, **tbl_kwargs)

                # Sub-group header + table kept together
                if sub_name:
                    elements.append(KeepTogether([
                        Paragraph(f"&gt;   {sub_name}", self.styles['SubGroupHeader']),
                        Spacer(1, 3),
                        table,
                    ]))
                else:
                    elements.append(table)
                elements.append(Spacer(1, 12))

            elements.append(Spacer(1, 5))

        return elements

    def _add_parameter_descriptions(self, category_data):
        """Add brief descriptions for each parameter"""
        elements = []

        # Get unique parameters
        unique_params = category_data['Test'].unique()

        for param in unique_params[:5]:  # Limit to first 5 to avoid overly long reports
            description = get_parameter_description(param)
            if description:
                param_text = f"{param}: {description}"
                elements.append(Paragraph(param_text, self.styles['ParamDescription']))

        if len(unique_params) > 5:
            elements.append(Spacer(1, 5))

        return elements

    def _add_memo_section(self, category_data):
        """Add memo/comments section if available"""
        elements = []

        # Check if there are any memos
        memos = category_data[category_data['Memo'].notna() & (category_data['Memo'] != '')]

        if not memos.empty:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph("Additional Notes:", self.styles['CustomBody']))

            for _, row in memos.iterrows():
                memo_text = str(row['Memo'])
                # Clean HTML tags if any
                if '<p>' in memo_text:
                    memo_text = memo_text.replace('<p>', '').replace('</p>', '').replace('<br>', ' ')
                elements.append(Paragraph(memo_text, self.styles['ParamDescription']))

        return elements

    def _create_clinical_chart(self, patient_clinical_data, parameter, ylabel, title, fasting_start, fasting_end, unit="", show_dual_axis=False, param2=None, ylabel2=None):
        """Create a matplotlib chart matching FastForward style (cyan fasting, black non-fasting)."""
        param_data = patient_clinical_data[patient_clinical_data['parameter'] == parameter].copy()
        param_data = param_data.sort_values('datetime')

        if param_data.empty:
            return None

        # Split data into fasting and non-fasting periods
        fasting_mask = (param_data['datetime'] >= fasting_start) & (param_data['datetime'] <= fasting_end)
        fasting_data = param_data[fasting_mask]
        non_fasting_data = param_data[~fasting_mask]

        fig, ax1 = plt.subplots(figsize=(7, 2.6))

        # Plot connecting dotted line (very light)
        ax1.plot(param_data['datetime'], param_data['value'],
                linestyle='--', linewidth=0.8, color='#CCCCCC', alpha=0.4, zorder=1)

        # Plot non-fasting points (BLACK) with value labels
        if not non_fasting_data.empty:
            ax1.plot(non_fasting_data['datetime'], non_fasting_data['value'],
                    marker='o', linewidth=0, markersize=6, color='#000000', markeredgewidth=0, zorder=3)
            for _, row in non_fasting_data.iterrows():
                val = row['value']
                if pd.notna(val):
                    label = f"{val:.1f}" if val != round(val) else f"{int(val)}"
                    ax1.annotate(label, (row['datetime'], val), textcoords="offset points",
                               xytext=(0, 8), ha='center', fontsize=8, color='#555555', zorder=4)

        # Plot fasting points (CYAN) with value labels
        if not fasting_data.empty:
            ax1.plot(fasting_data['datetime'], fasting_data['value'],
                    marker='o', linewidth=0, markersize=6, color='#00BCD4', label='Fasting', markeredgewidth=0, zorder=3)
            for _, row in fasting_data.iterrows():
                val = row['value']
                if pd.notna(val):
                    label = f"{val:.1f}" if val != round(val) else f"{int(val)}"
                    ax1.annotate(label, (row['datetime'], val), textcoords="offset points",
                               xytext=(0, 8), ha='center', fontsize=8, color='#555555', zorder=4)

        # Styling
        ax1.set_xlabel('', fontsize=10, color='#333333')
        ax1.set_ylabel("", fontsize=10, color='#333333')
        ax1.tick_params(axis='both', labelcolor='#333333', labelsize=9)
        ax1.grid(True, alpha=0.2, linestyle='-', linewidth=0.5, color='#CCCCCC', zorder=0)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['left'].set_color('#CCCCCC')
        ax1.spines['bottom'].set_color('#CCCCCC')

        # Dual parameter (e.g., SBP/DBP on same chart)
        if show_dual_axis and param2:
            param2_data = patient_clinical_data[patient_clinical_data['parameter'] == param2].copy()
            param2_data = param2_data.sort_values('datetime')
            if not param2_data.empty:
                # Plot connecting dotted line for param2
                ax1.plot(param2_data['datetime'], param2_data['value'],
                        linestyle='--', linewidth=0.9, color='#CCCCCC', alpha=0.6, zorder=1)

                fasting_mask2 = (param2_data['datetime'] >= fasting_start) & (param2_data['datetime'] <= fasting_end)
                fasting_data2 = param2_data[fasting_mask2]
                non_fasting_data2 = param2_data[~fasting_mask2]

                # Plot non-fasting points (BLACK, square marker)
                if not non_fasting_data2.empty:
                    ax1.plot(non_fasting_data2['datetime'], non_fasting_data2['value'],
                            marker='s', linewidth=0, markersize=5, color='#000000', markeredgewidth=0, zorder=3)

                # Plot fasting points (CYAN, square marker)
                if not fasting_data2.empty:
                    ax1.plot(fasting_data2['datetime'], fasting_data2['value'],
                            marker='s', linewidth=0, markersize=5, color='#00BCD4', markeredgewidth=0, zorder=3)

        # Format x-axis: show date under each data point
        unique_dates = sorted(param_data['datetime'].unique())
        ax1.set_xticks(unique_dates)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.xticks(rotation=0, ha='center', fontsize=7)

        # Legend outside the chart area
        if not fasting_data.empty:
            # Place the legend a bit higher above the plot, but only for this legend call
            ax1.legend(loc='lower right', fontsize=8, frameon=False,
                       bbox_to_anchor=(1.0, 1.07))

        plt.tight_layout()

        # Save to BytesIO
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=500, bbox_inches='tight', facecolor='white')
        img_buffer.seek(0)
        plt.close(fig)

        return img_buffer

    def _calculate_clinical_stats(self, patient_clinical_data, parameter, fasting_start, fasting_end):
        """Calculate baseline, fasting, and post-fasting statistics for a clinical parameter."""
        param_data = patient_clinical_data[patient_clinical_data['parameter'] == parameter].copy()

        if param_data.empty:
            return None

        # Split data into periods
        baseline_data = param_data[param_data['datetime'] < fasting_start]
        fasting_data = param_data[(param_data['datetime'] >= fasting_start) & (param_data['datetime'] <= fasting_end)]
        post_data = param_data[param_data['datetime'] > fasting_end]

        stats = {
            'parameter': parameter,
            'baseline_mean': baseline_data['value'].mean() if not baseline_data.empty else None,
            'baseline_last': baseline_data.iloc[-1]['value'] if not baseline_data.empty else None,
            'fasting_mean': fasting_data['value'].mean() if not fasting_data.empty else None,
            'fasting_min': fasting_data['value'].min() if not fasting_data.empty else None,
            'fasting_max': fasting_data['value'].max() if not fasting_data.empty else None,
            'post_mean': post_data['value'].mean() if not post_data.empty else None,
            'post_first': post_data.iloc[0]['value'] if not post_data.empty else None,
        }

        # Calculate delta (baseline to fasting mean)
        if stats['baseline_last'] is not None and stats['fasting_mean'] is not None:
            stats['delta'] = stats['fasting_mean'] - stats['baseline_last']
            stats['delta_pct'] = (stats['delta'] / stats['baseline_last']) * 100 if stats['baseline_last'] != 0 else 0
        else:
            stats['delta'] = None
            stats['delta_pct'] = None

        return stats

    def _create_clinical_monitoring_section(self, patient_clinical_data):
        """Create Clinical Monitoring section with charts and summary table."""
        elements = []

        # Fasting period definition
        fasting_start = pd.to_datetime('2026-01-16')
        fasting_end = pd.to_datetime('2026-01-23')

        # Chart parameters: (parameter_name, ylabel, display_name, unit_label)
        chart_params = [
            ('Weight (kg)', 'kg', 'Weight', 'kg'),
            ('BMI', 'kg/m²', 'BMI', 'kg/m²'),
            ('SBP (mmHg)', 'mmHg', 'Systolic Blood Pressure', 'mmHg'),
            ('DBP (mmHg)', 'mmHg', 'Diastolic Blood Pressure', 'mmHg'),
            ('Pulse (bpm)', 'bpm', 'Pulse', 'bpm'),
        ]

        chart_height = 2.6 * inch

        for param_name, ylabel, display_name, unit_label in chart_params:
            # Skip if no data for this parameter
            param_data = patient_clinical_data[patient_clinical_data['parameter'] == param_name]
            if param_data.empty:
                continue

            chart_buf = self._create_clinical_chart(
                patient_clinical_data,
                param_name,
                ylabel,
                display_name,
                fasting_start,
                fasting_end
            )
            if chart_buf:
                # Sub-category title: "Name  •  unit" with unit in dark gray
                # Ajout d'espacement à droite et à gauche du bullet (&bull;) avec un &nbsp; insécable
                title_text = f'{display_name} <font color="#b5b5b5">&nbsp;&nbsp;&nbsp;&bull;&nbsp;&nbsp;&nbsp;{unit_label}</font>'
                title_paragraph = Paragraph(title_text, self.styles['SubGroupHeader'])
                # "Spacer(1, 4)" means a vertical space of 4 points (the second argument) and a horizontal width of 1 unit (the first argument) will be added between elements.
                spacer = Spacer(1, 0)
                img = Image(chart_buf, width=6.5*inch, height=chart_height)
                elements.append(KeepTogether([title_paragraph, spacer, img]))
                elements.append(Spacer(1, 15))


        return elements

    def generate_report(self, fake_id, patient_name=None):
        """
        Generate a PDF report for a specific patient

        Args:
            fake_id: Patient ID from the dataset
            patient_name: Optional patient name (defaults to fake_id)

        Returns:
            Path to the generated PDF file
        """
        # Filter data for this patient
        patient_data = self.df[self.df['fake_id'] == fake_id].copy()

        if patient_data.empty:
            raise ValueError(f"No data found for fake_id: {fake_id}")

        # Use fake_id as patient name if not provided
        if patient_name is None:
            patient_name = f"Patient {fake_id}"

        # Build report groups per ReportNumber
        report_groups = []
        for rn in patient_data['ReportNumber'].unique():
            rn_data = patient_data[patient_data['ReportNumber'] == rn]
            sample_date = rn_data['SampleDate'].iloc[0] if pd.notna(rn_data['SampleDate'].iloc[0]) else ''
            validation_date = rn_data['ValidationDate'].iloc[0] if 'ValidationDate' in rn_data.columns and pd.notna(rn_data['ValidationDate'].iloc[0]) else ''
            categories = list(rn_data['ReportType'].unique())
            report_groups.append({
                'report_number': rn,
                'sample_date': sample_date,
                'validation_date': validation_date,
                'categories': categories,
            })

        # Use first group dates for header
        report_date = report_groups[0]['sample_date'] if report_groups else ''
        validation_date = report_groups[0]['validation_date'] if report_groups else ''

        # Build blood cover info for "During your stay" column on cover page
        # Structured as groups per sample (same format as report_groups for Supplementary analyses)
        blood_cover_info = None
        if self.blood_df is not None:
            patient_blood = self.blood_df[self.blood_df['patient_id'] == fake_id].copy()
            if not patient_blood.empty:
                BLOOD_PARENT_DISPLAY = {'Haematology': 'Hemogram'}
                blood_dates = sorted(
                    patient_blood['reception_date'].unique().tolist(),
                    key=lambda d: pd.to_datetime(d, dayfirst=True)
                )
                blood_groups = []
                for bd in blood_dates:
                    bd_data = patient_blood[patient_blood['reception_date'] == bd]
                    sid = str(bd_data['sample_id'].iloc[0])
                    vd = bd_data['validation_date'].iloc[0] if pd.notna(bd_data['validation_date'].iloc[0]) else ''
                    # Parent categories for this specific sample
                    sample_cats = bd_data['category'].unique()
                    parent_cats = []
                    for cat in sample_cats:
                        parent = cat.split(' - ', 1)[0] if ' - ' in cat else cat
                        parent = BLOOD_PARENT_DISPLAY.get(parent, parent)
                        if parent not in parent_cats:
                            parent_cats.append(parent)
                    blood_groups.append({
                        'report_number': sid,
                        'sample_date': bd,
                        'validation_date': vd,
                        'categories': parent_cats,
                    })
                blood_cover_info = blood_groups

        # Create PDF
        output_path = os.path.join(self.output_dir, f"Report_{fake_id}.pdf")
        doc = BaseDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=100,
            bottomMargin=70
        )

        # Page templates
        header_footer_cb = lambda c, d: self._create_header_footer(c, d, patient_name, fake_id, report_date, validation_date)
        cover_cb = lambda c, d: self._draw_cover_page(c, d, patient_name, report_groups, blood_cover_info)
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        cover_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='cover')
        doc.addPageTemplates([
            PageTemplate(id='cover', frames=[cover_frame], onPageEnd=cover_cb),
            PageTemplate(id='main', frames=[frame], onPageEnd=header_footer_cb),
        ])

        # Build document content
        story = []
        from reportlab.platypus import NextPageTemplate

        # Cover page - logo in the upper white zone
        logo_path = os.path.join(self.styles_dir, '..', 'logo_bw.svg')
        logo_drawing = svg2rlg(logo_path)
        if logo_drawing:
            scale_factor = 2.0
            logo_drawing.width *= scale_factor
            logo_drawing.height *= scale_factor
            logo_drawing.transform = (scale_factor, 0, 0, scale_factor, 0, 0)
        story.append(Spacer(1, 1.5*inch))
        if logo_drawing:
            logo_table = Table([[logo_drawing]], colWidths=[doc.width])
            logo_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
            story.append(logo_table)
        story.append(Spacer(1, 0.4*inch))
        story.append(Paragraph("Your Results", self.styles['Subtitle']))
        story.append(Spacer(1, 0.15*inch))

        # Patient info is drawn by _draw_cover_page in the colored zone
        story.append(NextPageTemplate('main'))
        story.append(PageBreak())

        # Track chapter number
        chapter_num = 1

        # === CHAPTER 1: During your stay ===
        # Check for both clinical and blood data
        patient_clinical_data = None
        if self.clinical_df is not None:
            patient_clinical_data = self.clinical_df[self.clinical_df['name'].str.strip() == str(fake_id).strip()].copy()
            if patient_clinical_data.empty:
                patient_clinical_data = None

        patient_blood_data = None
        if self.blood_df is not None:
            patient_blood_data = self.blood_df[self.blood_df['patient_id'] == fake_id].copy()
            if patient_blood_data.empty:
                patient_blood_data = None

        # Create Chapter 1 if we have any data (clinical or blood)
        if patient_clinical_data is not None or patient_blood_data is not None:
            # Extract sample_id + date pairs for page header display (from blood data if available)
            blood_sample_info = []
            if patient_blood_data is not None:
                blood_dates = sorted(
                    patient_blood_data['reception_date'].unique().tolist(),
                    key=lambda d: pd.to_datetime(d, dayfirst=True)
                )
                for bd in blood_dates:
                    bd_data = patient_blood_data[patient_blood_data['reception_date'] == bd]
                    sid = str(bd_data['sample_id'].iloc[0])
                    blood_sample_info.append((bd, sid))

            # Super-category title (no section marker - this is the top level)
            story.append(Paragraph("During your stay", self.styles['SuperCategoryTitle']))
            story.append(Spacer(1, 10))

            # First section: Clinical Monitoring (if available)
            if patient_clinical_data is not None:
                story.append(SectionMarker("Clinical Measurements", sample_info=blood_sample_info, super_category="During your stay"))
                story.append(Paragraph("Clinical Measurements", self.styles['SectionHeader']))
                story.append(Spacer(1, 8))
                clinical_elements = self._create_clinical_monitoring_section(patient_clinical_data)
                story.extend(clinical_elements)
                story.append(Spacer(1, 20))

            # Subsequent sections: Blood Analysis (if available)
            if patient_blood_data is not None:
                blood_elements = self._create_blood_results_section(patient_blood_data, super_category="During your stay", sample_info=blood_sample_info)
                story.extend(blood_elements)

            story.append(PageBreak())
            chapter_num += 1

        # === CHAPTER 2: Laboratory Analysis ===
        story.append(Paragraph("Supplementary analyses", self.styles['SuperCategoryTitle']))
        story.append(Spacer(1, 10))

        # Reset canvas variables for Laboratory Analysis (clear blood_sample_info)
        story.append(SectionMarker("", super_category="Supplementary analyses", sample_info=None))

        # Group data by ReportType (category) in logical order
        CATEGORY_ORDER = [
            "Hemogram",
            "Immune Status",
            "Stress and Biorhythm in Saliva",
            "Bacterioma by NGS",
            "Archaeoma by NGS",
            "Intestinal Dysbiosis by NGS",
            "Mycobiome by NGS",
            "Parasitome by NGS",
            "Virome by NGS",
            "Stool Sample",
        ]
        available = patient_data['ReportType'].unique()
        categories = [c for c in CATEGORY_ORDER if c in available]
        # Append any categories not in the predefined order
        categories += [c for c in available if c not in CATEGORY_ORDER]

        # Categories that appear as a small appendix without page break
        APPENDIX_CATEGORIES = {"Stool Sample"}

        # Build category -> report_number and category -> sample_date mappings
        cat_report_map = {}
        cat_sample_date_map = {}
        for group in report_groups:
            for cat in group['categories']:
                cat_report_map[cat] = group['report_number']
                cat_sample_date_map[cat] = group['sample_date']

        for category in categories:
            category_data = patient_data[patient_data['ReportType'] == category]
            report_number = cat_report_map.get(category)
            sample_date = cat_sample_date_map.get(category)

            # Create table for this category
            category_elements = self._create_results_table(category_data, category, report_number=report_number, super_category="Supplementary analyses", sample_date=sample_date)

            story.extend(category_elements)
            if category not in APPENDIX_CATEGORIES:
                story.append(PageBreak())

        # Build PDF
        doc.build(story)

        print(f"Report generated: {output_path}")
        return output_path

    def generate_all_reports(self):
        """Generate reports for all unique fake_ids in the dataset"""
        fake_ids = self.df['fake_id'].unique()
        generated_reports = []

        print(f"Generating reports for {len(fake_ids)} patients...")

        for fake_id in fake_ids:
            try:
                report_path = self.generate_report(fake_id)
                generated_reports.append(report_path)
            except Exception as e:
                print(f"Error generating report for {fake_id}: {e}")

        print(f"\nSuccessfully generated {len(generated_reports)} reports")
        return generated_reports


if __name__ == "__main__":
    generator = PDFReportGenerator(
        "data/data.csv",
        output_dir="outputs/PDF",
        blood_data_path="data/blood_data_during_stay.csv",
        clinical_data_path="data/all_clinical_data.csv"
    )
    generator.generate_all_reports()

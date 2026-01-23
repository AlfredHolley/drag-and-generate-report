class TableGenerator:
    """Generate category-organized tables for PDF"""
    
    def __init__(self, pdf, patient_metadata=None):
        self.pdf = pdf
        self.patient_metadata = patient_metadata or {}
        self.blue_accent = [22, 186, 222]
        self.black = [0, 0, 0]
        self.light_gray = [248, 252, 252]
        self.white = [255, 255, 255]
        self.gray = [135, 135, 135]
        
        # Initialize reference lookup if metadata available
        self.reference_lookup = None
        if self.patient_metadata:
            try:
                from processors.reference_lookup import ReferenceLookup
                self.reference_lookup = ReferenceLookup()
            except ImportError:
                pass
        
        # Initialize value translator
        try:
            from processors.value_translator import translate_value
            self.translate_value = translate_value
        except ImportError:
            self.translate_value = lambda x: x  # Fallback: no translation
    
    def _calculate_age_at_analysis(self, birthdate: str, analysis_date: str) -> int:
        """Calculate patient age at time of analysis"""
        try:
            from datetime import datetime
            
            # Parse dates (format: YYYY-MM-DD or DD/MM/YYYY)
            if '/' in birthdate:
                birth = datetime.strptime(birthdate, '%d/%m/%Y')
            else:
                birth = datetime.strptime(birthdate, '%Y-%m-%d')
            
            if '/' in analysis_date:
                analysis = datetime.strptime(analysis_date, '%d/%m/%Y')
            else:
                analysis = datetime.strptime(analysis_date, '%Y-%m-%d')
            
            age = analysis.year - birth.year
            if (analysis.month, analysis.day) < (birth.month, birth.day):
                age -= 1
            
            return age
        except Exception:
            return None
    
    def _get_converted_reference_range(self, param_name: str, unit: str) -> str:
        """
        Get the correct reference range for parameters that have multiple units.
        
        Some parameters in the PDF only have reference ranges for one unit (usually mg/dL),
        and the same reference is incorrectly shown for the converted unit (mmol/L, µmol/L).
        This method provides the correct converted reference ranges.
        
        Conversion factors:
        - Cholesterol (Total, LDL, HDL): mg/dL to mmol/L → divide by 38.67
        - Triglycerides: mg/dL to mmol/L → divide by 88.57
        - Bilirubin: mg/dL to µmol/L → multiply by 17.1
        - Glucose: mg/dL to mmol/L → divide by 18.02
        - Urea: mg/dL to mmol/L → divide by 6.006 (as BUN/urea)
        - Uric Acid: mg/dL to µmol/L → multiply by 59.48
        - Creatinine: mg/dL to µmol/L → multiply by 88.4
        """
        param_upper = param_name.upper()
        unit_upper = unit.upper().strip()
        
        # LDL Cholesterol
        if 'LDL' in param_upper and 'CHOLESTEROL' in param_upper:
            if 'MMOL' in unit_upper:
                return '< 3.0'  # < 116 mg/dL → < 3.0 mmol/L
        
        # HDL Cholesterol  
        if 'HDL' in param_upper and 'CHOLESTEROL' in param_upper:
            if 'MMOL' in unit_upper:
                return '> 1.03'  # > 40 mg/dL → > 1.03 mmol/L
        
        # Total Cholesterol
        if 'TOTAL' in param_upper and 'CHOLESTEROL' in param_upper:
            if 'MMOL' in unit_upper:
                return '< 5.17'  # < 200 mg/dL → < 5.17 mmol/L
        
        # Triglycerides
        if 'TRIGLYCERID' in param_upper:
            if 'MMOL' in unit_upper:
                return '< 1.69'  # < 150 mg/dL → < 1.69 mmol/L
        
        # Total Bilirubin
        if 'TOTAL' in param_upper and 'BILIRRUBIN' in param_upper:
            if 'MCMOL' in unit_upper or 'ΜMOL' in unit_upper or 'µMOL' in unit_upper:
                return '< 20.5'  # < 1.2 mg/dL → < 20.5 µmol/L
        
        # Direct Bilirubin (if needed)
        if 'DIRECT' in param_upper and 'BILIRRUBIN' in param_upper:
            if 'MCMOL' in unit_upper or 'ΜMOL' in unit_upper or 'µMOL' in unit_upper:
                return '< 5.1'  # < 0.3 mg/dL → < 5.1 µmol/L
        
        # Glucose
        if 'GLUCOSE' in param_upper and 'HAEMOGLOBIN' not in param_upper:
            if 'MMOL' in unit_upper:
                return '3.9 - 5.5'  # 70-100 mg/dL → 3.9-5.5 mmol/L (fasting)
        
        # Urea
        if param_upper == 'UREA' or param_upper == 'UREA':
            if 'MMOL' in unit_upper:
                return '2.83 - 8.16'  # 17-49 mg/dL → 2.83-8.16 mmol/L
        
        # Uric Acid
        if 'URIC' in param_upper and 'ACID' in param_upper:
            if 'MCMOL' in unit_upper or 'ΜMOL' in unit_upper or 'µMOL' in unit_upper:
                return '154.65 - 404.46'  # 2.6-6.8 mg/dL → 154.65-404.46 µmol/L
        
        # Creatinine
        if 'CREATININE' in param_upper:
            if 'MCMOL' in unit_upper or 'ΜMOL' in unit_upper or 'µMOL' in unit_upper:
                return '45.08 - 83.98'  # 0.51-0.95 mg/dL → 45.08-83.98 µmol/L
        
        return None  # No conversion needed or unknown parameter
    
    def _get_igf1_reference_range(self) -> str:
        """
        Get IGF-1 reference range based on patient age and sex.
        
        Reference ranges:
        - 0-5 years: Men: 11 - 233, Women: 8 - 251
        - 12-15 years: Men: 49 - 520, Women: 90 - 596
        - 16-20 years: Men: 119 - 511, Women: 109 - 524
        - 21-24 years: Men: 105 - 364, Women: 102 - 351
        - 25-29 years: Men: 84 - 283, Women: 91 - 311
        - 30-39 years: Men: 82 - 246, Women: 78 - 290
        - 40-49 years: Men: 69 - 237, Women: 59 - 271
        - 50-59 years: Men: 55 - 225, Women: 44 - 240
        - >60 years: Men: 17 - 206, Women: 17 - 241
        """
        birthdate = self.patient_metadata.get('birthdate')
        sample_date = self.patient_metadata.get('sample_date')
        sex = self.patient_metadata.get('sex', '').upper()
        
        if not birthdate or not sample_date:
            return ''
        
        age = self._calculate_age_at_analysis(birthdate, sample_date)
        if age is None:
            return ''
        
        # Define reference ranges by age group
        if age <= 5:
            return '11 - 233' if sex == 'M' else '8 - 251'
        elif 6 <= age <= 11:
            # Ages 6-11: use closest range (0-5)
            return '11 - 233' if sex == 'M' else '8 - 251'
        elif 12 <= age <= 15:
            return '49 - 520' if sex == 'M' else '90 - 596'
        elif 16 <= age <= 20:
            return '119 - 511' if sex == 'M' else '109 - 524'
        elif 21 <= age <= 24:
            return '105 - 364' if sex == 'M' else '102 - 351'
        elif 25 <= age <= 29:
            return '84 - 283' if sex == 'M' else '91 - 311'
        elif 30 <= age <= 39:
            return '82 - 246' if sex == 'M' else '78 - 290'
        elif 40 <= age <= 49:
            return '69 - 237' if sex == 'M' else '59 - 271'
        elif 50 <= age <= 59:
            return '55 - 225' if sex == 'M' else '44 - 240'
        elif age >= 60:
            return '17 - 206' if sex == 'M' else '17 - 241'
        
        return ''
    
    def _get_androstenedione_reference_range(self) -> str:
        """
        Get Androstenedione delta 4 reference range based on patient age and sex.
        
        Reference ranges:
        - Adults - Males: 0.5 - 3.5 ng/mL
        - Adults - Pre-menopausal women: 0.4 - 3.4 ng/mL
        - Adults - Post-menopausal women (>50 years): < 2.1 ng/mL
        - Young Adults (17-21 years) - Males: 0.44 - 2.65 ng/mL
        - Young Adults (17-21 years) - Females: 0.70 - 4.31 ng/mL
        """
        birthdate = self.patient_metadata.get('birthdate')
        sample_date = self.patient_metadata.get('sample_date')
        sex = self.patient_metadata.get('sex', '').upper()
        
        if not birthdate or not sample_date:
            return ''
        
        age = self._calculate_age_at_analysis(birthdate, sample_date)
        if age is None:
            return ''
        
        if sex == 'M':
            # Males
            if 17 <= age <= 21:
                return '0.44 - 2.65'  # Young adult males
            else:
                return '0.5 - 3.5'  # Adult males
        else:
            # Females
            if 17 <= age <= 21:
                return '0.70 - 4.31'  # Young adult females
            elif age > 50:
                return '< 2.1'  # Post-menopausal women
            else:
                return '0.4 - 3.4'  # Pre-menopausal women
        
        return ''
    
    def _get_dhea_s_reference_range(self) -> str:
        """
        Get DEHYDROEPIANDROSTERONE-S reference range based on patient age and sex.
        
        Reference ranges (in µmol/L):
        - 16-19 years: Men: 3.36 - 18.20, Women: 3.96 - 15.50
        - 20-24 years: Men: 6.50 - 14.60, Women: 3.60 - 11.10
        - 25-34 years: Men: 4.60 - 16.10, Women: 2.60 - 13.90
        - 35-44 years: Men: 3.80 - 13.10, Women: 2.00 - 11.10
        - 45-54 years: Men: 3.70 - 12.10, Women: 1.50 - 7.70
        - 55-64 years: Men: 1.30 - 9.80, Women: 0.80 - 4.90
        - 65-70 years: Men: 1.20 - 7.00, Women: 0.70 - 3.80
        - >70 years: Men: 0.70 - 5.50, Women: 0.50 - 2.50
        """
        birthdate = self.patient_metadata.get('birthdate')
        sample_date = self.patient_metadata.get('sample_date')
        sex = self.patient_metadata.get('sex', '').upper()
        
        if not birthdate or not sample_date:
            return ''
        
        age = self._calculate_age_at_analysis(birthdate, sample_date)
        if age is None:
            return ''
        
        # Define reference ranges by age group
        # Note: Values match pdf_builder.py reference table (Women, Men order in source)
        if 16 <= age <= 19:
            return '3.36 - 18.20' if sex == 'M' else '3.96 - 15.50'
        elif 20 <= age <= 24:
            return '6.50 - 14.60' if sex == 'M' else '3.60 - 11.10'
        elif 25 <= age <= 34:
            return '4.60 - 16.10' if sex == 'M' else '2.60 - 13.90'
        elif 35 <= age <= 44:
            return '3.80 - 13.10' if sex == 'M' else '2.00 - 11.10'
        elif 45 <= age <= 54:
            return '3.70 - 12.10' if sex == 'M' else '1.50 - 7.70'
        elif 55 <= age <= 64:
            return '1.30 - 9.80' if sex == 'M' else '0.80 - 4.90'
        elif 65 <= age <= 70:
            return '1.20 - 7.00' if sex == 'M' else '0.70 - 3.80'
        elif age > 70:
            return '0.70 - 5.50' if sex == 'M' else '0.50 - 2.50'
        else:
            # For ages below 16, use the 16-19 range as closest approximation
            if age < 16:
                return '3.36 - 18.20' if sex == 'M' else '3.96 - 15.50'
        
        return ''
    
    def _sort_carbohydrate_metabolism_params(self, parameters):
        """
        Sort parameters for Carbohydrate Metabolism category in specific order:
        1. GLUCOSE (both units)
        2. HAEMOGLOBIN A1C
        3. HAEMOGLOBIN A1C (IFCC)
        4. BASAL INSULIN (IRI)
        5. HOMA-IR (Insulin Resistance Index)
        """
        # Define the order for Carbohydrate Metabolism parameters
        carb_order = {
            'GLUCOSE': 1,
            'GLUCOSA': 1,
            'HAEMOGLOBIN A1C': 2,
            'HEMOGLOBIN A1C': 2,
            'HBA1C': 2,
            'HAEMOGLOBIN A1C (IFCC)': 3,
            'HEMOGLOBIN A1C (IFCC)': 3,
            'HBA1C (IFCC)': 3,
            'BASAL INSULIN': 4,
            'INSULIN': 4,
            'INSULINA': 4,
            'HOMA-IR': 5,
            'HOMA': 5,
        }
        
        def get_order(param):
            name = param.get('english_name', '').upper()
            spanish_name = param.get('spanish_name', '').upper()
            
            # Check for specific matches first
            if 'IFCC' in name or 'IFCC' in spanish_name:
                return 3
            if 'HOMA' in name or 'HOMA' in spanish_name:
                return 5
            if 'INSULIN' in name or 'INSULINA' in spanish_name:
                return 4
            if 'HBA1C' in name or 'A1C' in name or 'HEMOGLOBIN A1C' in name or 'HAEMOGLOBIN A1C' in name:
                return 2
            if 'GLUCOSE' in name or 'GLUCOSA' in spanish_name:
                return 1
            
            # Default: keep at the end
            return 999
        
        return sorted(parameters, key=get_order)
    
    def generate_category_table(self, category, dates):
        """Generate table for a category"""
        parameters = category['parameters']
        
        if not parameters:
            return
        
        # Apply specific sorting for Carbohydrate Metabolism category
        category_name = category.get('name', '').upper()
        if 'CARBOHYDRATE' in category_name or 'GLUCIDIQUE' in category_name:
            parameters = self._sort_carbohydrate_metabolism_params(parameters)
        
        # Determine number of date columns
        n_dates = len(dates)
        
        # If more than 5 dates, use pivoted table format
        if n_dates > 5:
            self.generate_pivoted_table(category, dates)
            return
        
        # Column widths based on number of dates (with reference range column)
        # Available width: ~180mm (210mm page - 15mm margins each side)
        if n_dates == 1:
            col_widths = {
                'param': 60,
                'date': 30,  # Increased for longer qualitative values like "Not detected"
                'reference': 40,
                'unit': 20
            }
            headers = ["PARAMETER", dates[0] if dates else "VALUE", "REFERENCE", "UNIT"]
        elif n_dates == 2:
            col_widths = {
                'param': 50,  # Slightly reduced to make room for date columns
                'date': 27,  # Increased by 2mm to accommodate longer dates (e.g., "16/01/2026 - 1")
                'reference': 35,
                'unit': 18
            }
            # Use actual dates instead of "BASELINE" and "FOLLOW-UP"
            # Allow 14 characters to display dates like "16/01/2026 - 1" (14 chars)
            date_headers = [d[:14] for d in dates] if dates and len(dates) >= 2 else ["BASELINE", "FOLLOW-UP"]
            headers = ["PARAMETER"] + date_headers + ["REFERENCE", "UNIT"]
        else:
            # For 3+ dates, calculate dynamic widths to fit all dates
            # Available width: ~180mm (210mm page - 15mm margins each side)
            fixed_cols_width = 50 + 30 + 15  # param + reference + unit (minimum widths)
            date_cols_width = 180 - fixed_cols_width
            
            # Calculate date column width (minimum 12mm, maximum 20mm per date)
            date_width = max(12, min(20, date_cols_width / n_dates))
            
            # Adjust other columns if needed
            param_width = max(40, 50 - max(0, (n_dates - 5) * 1))  # Reduce param width if many dates
            ref_width = max(25, 30 - max(0, (n_dates - 5) * 0.5))  # Reduce ref width slightly
            unit_width = max(12, 15 - max(0, (n_dates - 5) * 0.3))  # Reduce unit width slightly
            
            col_widths = {
                'param': param_width,
                'date': date_width,
                'reference': ref_width,
                'unit': unit_width
            }
            # Use all dates, truncate display names if needed (max 10 chars)
            headers = ["PARAMETER"] + [d[:10] for d in dates] + ["REFERENCE", "UNIT"]
        
        # Store headers and col_widths for potential page breaks
        self._current_headers = headers
        self._current_col_widths = col_widths
        self._current_n_dates = n_dates
        
        # Check if we need a new page before starting table
        # Header (8) + spacing (1) + at least one row (6.5) + bottom margin (20)
        # Ensure we respect top margin (25mm) for header space
        if self.pdf.get_y() + 8 + 1 + 6.5 > self.pdf.h - 20:
            self.pdf.add_page()
            # Ensure we start below the header
            self.pdf.set_y(self.pdf.t_margin)
        
        # Table header
        self._draw_table_header(headers, col_widths, n_dates)
        
        # Table rows with page break handling
        fill = False
        last_param_name = None  # Track last parameter name to detect duplicates
        last_param_fill = None  # Track last fill state for parameter column
        for param in parameters:
            # Check if we need a new page before drawing this row
            # Row height (6.5) + spacing (0.5) + bottom margin (20)
            if self.pdf.get_y() + 6.5 + 0.5 > self.pdf.h - 20:
                self.pdf.add_page()
                # Ensure we start below the header
                self.pdf.set_y(self.pdf.t_margin)
                # Redraw header on new page
                self._draw_table_header(headers, col_widths, n_dates)
                # Reset tracking on new page
                last_param_name = None
                last_param_fill = None
            
            # Check if this parameter has the same name as the previous one
            current_param_name = param.get('english_name', '').upper()
            hide_param_name = (last_param_name is not None and current_param_name == last_param_name)
            
            fill = not fill
            # For parameter column: use same fill as previous if name is hidden, otherwise use current fill
            param_fill = last_param_fill if hide_param_name else fill
            
            self._draw_table_row(param, dates, col_widths, n_dates, fill, hide_param_name, param_fill)
            
            # Update tracking
            if not hide_param_name:
                last_param_name = current_param_name
                last_param_fill = fill
        
        # Add margin after table
        self.pdf.ln(2)
    
    def _draw_table_header(self, headers, col_widths, n_dates):
        """Draw table header"""
        # Ensure we're not too close to header - always start at least at margin
        if self.pdf.get_y() < self.pdf.t_margin:
            self.pdf.set_y(self.pdf.t_margin)
        
        self.pdf.set_font("Calibri", "B", 9)
        self.pdf.set_text_color(*self.black)
        self.pdf.set_fill_color(*self.light_gray)
        
        y_start = self.pdf.get_y()
        
        # Parameter column
        self.pdf.set_xy(15, y_start)
        self.pdf.cell(col_widths['param'], 8, headers[0], 0, 0, "L", True)
        
        x_pos = 15 + col_widths['param']
        
        # Date columns (right-aligned)
        for i, header in enumerate(headers[1:-2]):  # Skip first (param), reference, and last (unit)
            if i < n_dates:
                self.pdf.set_xy(x_pos, y_start)
                # Truncate date header to fit column (14 chars for dates like "16/01/2026 - 1")
                self.pdf.cell(col_widths['date'], 8, header[:14], 0, 0, "R", True)  # Changed "L" to "R"
                x_pos += col_widths['date']
        
        # Reference range column (center-aligned)
        ref_header_idx = len(headers) - 2  # Second to last
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['reference'], 8, headers[ref_header_idx][:12], 0, 0, "C", True)  # Changed "L" to "C"
        x_pos += col_widths['reference']
        
        # Unit column (center-aligned)
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['unit'], 8, headers[-1], 0, 1, "C", True)  # Changed "L" to "C"
        
        self.pdf.ln(1)
    
    def _draw_table_row(self, param, dates, col_widths, n_dates, fill, hide_param_name=False, param_fill=None):
        """Draw a table row for a parameter
        
        Args:
            param: Parameter data
            dates: List of dates
            col_widths: Column widths dictionary
            n_dates: Number of date columns
            fill: Fill state for the row (except parameter column)
            hide_param_name: If True, don't display parameter name
            param_fill: Fill state for parameter column (if None, uses fill)
        """
        fill_color = self.light_gray if fill else self.white
        self.pdf.set_fill_color(*fill_color)
        
        # Parameter column fill (use param_fill if provided, otherwise use fill)
        if param_fill is None:
            param_fill = fill
        param_fill_color = self.light_gray if param_fill else self.white
        
        y_start = self.pdf.get_y()
        
        # Parameter name - handle long names with multi-line
        self.pdf.set_font("Calibri", "", 9)
        self.pdf.set_text_color(*self.black)
        param_name = param['english_name'] if not hide_param_name else ""  # Empty if hidden
        
        # Check if this is a sub-parameter that needs indentation
        # Sub-parameters of TOTAL TESTOSTERONE
        testosterone_sub_params = ['% FREE TESTOSTERONE', 'ESTIMATED FREE TESTOSTERONE', 'BIOAVAILABLE TESTOSTERONE', 
                      'FREE TESTOSTERONE', 'FREE TESTOSTERONE A']
        # Sub-parameters of LEUCOCYTES (white blood cell differential) - only percentages, NOT absolute counts
        leukocyte_sub_params = ['NEUTROPHIL%', 'LYMPHOCYTE%', 'MONOCYTE%', 'EOSINOPHIL%', 'EOSINOPHILS%', 'BASOPHIL%', 'BASOPHILES%']
        is_testosterone_sub = any(sub in param_name.upper() for sub in testosterone_sub_params)
        is_leukocyte_sub = any(sub in param_name.upper() for sub in leukocyte_sub_params) and 'LEUCOCYTES' not in param_name.upper()
        indent = 5 if (is_testosterone_sub or is_leukocyte_sub) else 0  # 5mm indent for sub-parameters
        x_start = 15 + indent
        col_width_adjusted = col_widths['param'] - indent
        
        # Add visual indicator for sub-parameters
        if is_testosterone_sub or is_leukocyte_sub:
            param_name = "  " + param_name  # Add small indent in text too
        
        # Draw parameter column with appropriate fill color
        if hide_param_name:
            # Hidden name - just draw background, no text
            self.pdf.set_fill_color(*param_fill_color)
            self.pdf.rect(15, y_start, col_widths['param'], 6, 'F')
            param_height = 6
        elif len(param_name) > 33:
            # Calculate approximate number of lines needed
            # Estimate: approximately 33 characters per line for column width
            estimated_lines = max(2, (len(param_name) + 32) // 33)  # Round up division
            line_height = 3.5  # Height per line in mm for font size 9
            param_height = estimated_lines * line_height
            
            # Draw filled rectangle for the parameter column first with param_fill_color
            self.pdf.set_fill_color(*param_fill_color)
            self.pdf.rect(15, y_start, col_widths['param'], param_height, 'F')
            
            # Use multi_cell for wrapping text
            self.pdf.set_xy(x_start, y_start)
            # Save current Y position before multi_cell
            y_before = self.pdf.get_y()
            self.pdf.multi_cell(col_width_adjusted, line_height, param_name, 0, "L", False)
            # Get actual height used
            y_after = self.pdf.get_y()
            actual_height = y_after - y_before
            if actual_height > 0:
                param_height = actual_height
            else:
                # Fallback: use estimated height
                param_height = estimated_lines * line_height
        else:
            # Short name - single line
            # Draw filled rectangle for full column width first with param_fill_color
            self.pdf.set_fill_color(*param_fill_color)
            self.pdf.rect(15, y_start, col_widths['param'], 6, 'F')
            self.pdf.set_xy(x_start, y_start)
            self.pdf.cell(col_width_adjusted, 6, param_name, 0, 0, "L", False)
            param_height = 6
        
        # Restore fill color for other columns
        self.pdf.set_fill_color(*fill_color)
        
        x_pos = 15 + col_widths['param']
        
        # Check if this is URINE MICROSCOPE EXAM and needs special handling
        param_name_upper = param.get('english_name', '').upper()
        is_urine_microscope = 'URINE MICROSCOPE' in param_name_upper or 'MICROSCOPE EXAM' in param_name_upper
        
        # Pre-calculate value heights for URINE MICROSCOPE EXAM if needed
        urine_microscope_value_heights = {}
        max_urine_microscope_height = 6
        if is_urine_microscope:
            for i, date in enumerate(dates):
                value = ""
                for val_obj in param['values']:
                    if val_obj['date'] == date:
                        value = val_obj['value'] or ""
                        break
                
                # Translate Spanish values to English
                if value:
                    value = self.translate_value(str(value))
                
                # If value is longer than 8 characters, calculate height needed for wrapping
                if value and len(str(value)) > 8:
                    # Use actual wrapping to calculate exact height needed
                    available_width = col_widths['date'] - 0.5
                    wrapped_lines = self.pdf._wrap_text(str(value), col_widths['date'] - 2)
                    if not wrapped_lines:
                        wrapped_lines = [str(value)]
                    line_height = 3.5  # Height per line in mm
                    value_height = len(wrapped_lines) * line_height
                    urine_microscope_value_heights[date] = value_height
                    # Track maximum height needed
                    max_urine_microscope_height = max(max_urine_microscope_height, value_height)
        
        # Calculate row height based on parameter name height and URINE MICROSCOPE EXAM heights
        row_height = max(param_height, max_urine_microscope_height, 6)
        
        # Date values (right-aligned) - vertically centered if row is taller
        # Use all dates, not limited to n_dates
        for i, date in enumerate(dates):
            value = ""
            for val_obj in param['values']:
                if val_obj['date'] == date:
                    value = val_obj['value'] or ""
                    break
            
            # Translate Spanish values to English
            if value:
                value = self.translate_value(str(value))
            
            # Special handling for URINE MICROSCOPE EXAM - display full text if > 8 chars
            if is_urine_microscope:
                if value and len(str(value)) > 8:
                    # Use multi_cell to display full text with wrapping
                    # Draw filled rectangle for date column with calculated height
                    self.pdf.rect(x_pos, y_start, col_widths['date'], row_height, 'F')
                    self.pdf.set_text_color(*self.black)
                    
                    # Wrap text manually for right alignment
                    # Use _wrap_text method from PDFBuilder with full column width
                    # Use almost full width (small padding for right alignment)
                    available_width = col_widths['date'] - 0.5  # Small padding for right alignment
                    wrapped_lines = self.pdf._wrap_text(str(value), available_width)
                    if not wrapped_lines:
                        wrapped_lines = [str(value)]
                    
                    # Draw each line right-aligned
                    line_height = 3.5
                    total_text_height = len(wrapped_lines) * line_height
                    y_current = y_start + (row_height - total_text_height) / 2  # Center vertically
                    
                    for line in wrapped_lines:
                        # Calculate text width for this line
                        text_width = self.pdf.get_string_width(line)
                        # Calculate x position for right alignment (small padding from right edge)
                        x_right = x_pos + col_widths['date'] - text_width - 1
                        # Ensure we don't go before column start
                        x_display = max(x_pos + 0.2, x_right)  # Small left padding as minimum
                        self.pdf.set_xy(x_display, y_current)
                        # Draw text - use text_width + small buffer to ensure full text is visible
                        # Don't use cell with full column width as it might clip, use actual text width
                        self.pdf.cell(text_width + 0.5, line_height, line, 0, 0, "L", False)
                        y_current += line_height
                    
                    # Reset position for next column
                    self.pdf.set_xy(x_pos + col_widths['date'], y_start)
                    x_pos += col_widths['date']
                    continue
            
            # Center vertically if row is taller than 6mm
            y_offset = (row_height - 6) / 2 if row_height > 6 else 0
            # Draw filled rectangle for date column
            self.pdf.rect(x_pos, y_start, col_widths['date'], row_height, 'F')
            self.pdf.set_xy(x_pos, y_start + y_offset)
            self.pdf.set_text_color(*self.black)
            # Truncate long numeric values but allow full qualitative values (up to 15 chars)
            display_value = str(value)
            if len(display_value) > 15:
                display_value = display_value[:15]
            self.pdf.cell(col_widths['date'], 6, display_value, 0, 0, "R", True)
            x_pos += col_widths['date']
        
        # Reference range - first check if parameter has reference_range from PDF
        ref_range = param.get('reference_range', '')
        
        # Special handling for DHEA (DHYDROEPIANDROSTERONE) with ng/mL unit
        # Use sex-based reference ranges from patient metadata
        param_name = param.get('english_name', '').upper()
        param_unit = param.get('unit', '').upper()
        if ('DHEA' in param_name or 'DEHYDROEPIANDROSTERONE' in param_name) and 'NG/ML' in param_unit:
            patient_sex = self.patient_metadata.get('sex', '').upper()
            if patient_sex == 'M':
                ref_range = '1.87 - 15.01'
            elif patient_sex == 'F':
                ref_range = '1.65 - 13.50'
            else:
                # Default to men's range if sex unknown
                ref_range = '1.87 - 15.01'
        
        # Special handling for DEHYDROEPIANDROSTERONE-S with µmol/L unit
        # Use age and sex-based reference ranges from patient metadata
        # Get original unit before uppercase conversion for exact match
        param_unit_original = param.get('unit', '')
        param_unit_stripped = param_unit_original.strip()
        if ('DHEA-S' in param_name or 'DEHYDROEPIANDROSTERONE-S' in param_name):
            # Check for µmol/L unit in various formats
            if (param_unit_stripped == "µmol/L" or 
                'µMOL/L' in param_unit or 'MCMOL/L' in param_unit or 'UMOL/L' in param_unit or
                'µMOL' in param_unit or 'MCMOL' in param_unit or 'UMOL' in param_unit or
                'µmol' in param_unit_stripped.lower() or 'mcmol' in param_unit_stripped.lower()):
                calculated_range = self._get_dhea_s_reference_range()
                if calculated_range:
                    ref_range = calculated_range
        
        # Special handling for SOMATOMEDIN C (IGF-1) - age and sex dependent
        if ('SOMATOMEDIN' in param_name or 'IGF-1' in param_name or 'IGF1' in param_name) and 'NG/ML' in param_unit:
            ref_range = self._get_igf1_reference_range()
        
        # Special handling for FSH and LH - display "*" instead of reference range
        if ('FSH' in param_name or 'FOLLICLE-STIMULATING HORMONE' in param_name or
            'LH' in param_name or 'LUTEINIZING HORMONE' in param_name or 'LEUTENISING HORMONE' in param_name):
            ref_range = '*'
        
        # Special handling for 17-BETA ESTRADIOL - display "*" instead of reference range
        if ('ESTRADIOL' in param_name or '17-BETA' in param_name or '17 BETA' in param_name or
            'BETA ESTRADIOL' in param_name):
            ref_range = '*'
        
        # Special handling for PROGESTERONE - display "*" instead of reference range
        if 'PROGESTERONE' in param_name:
            ref_range = '*'
        
        # Special handling for TOTAL TESTOSTERONE - use sex-based reference ranges
        if 'TOTAL TESTOSTERONE' in param_name or (param_name == 'TESTOSTERONE' and 'FREE' not in param_name and 'BIOAVAILABLE' not in param_name and 'ESTIMATED' not in param_name):
            patient_sex = self.patient_metadata.get('sex', '').upper()
            if patient_sex == 'M':
                ref_range = '2.4 - 8.7'
            elif patient_sex == 'F':
                ref_range = '0.10 - 0.40'
            else:
                # Default to male range if sex unknown
                ref_range = '2.4 - 8.7'
        
        # Special handling for ANDROSTENEDIONE DELTA 4 - use age and sex-based reference ranges
        if 'ANDROSTENEDIONE' in param_name or 'DELTA 4' in param_name or 'DELTA-4' in param_name:
            calculated_range = self._get_androstenedione_reference_range()
            if calculated_range:
                ref_range = calculated_range
        
        # Special handling for T3 REVERSE (rT3) - always use adult reference range
        if 'T3 REVERSE' in param_name or 'REVERSE T3' in param_name or 'RT3' in param_name:
            ref_range = '0.17 - 0.44'
        
        # Check if the reference range needs unit conversion
        # This handles parameters that appear in multiple units but PDF only provides
        # reference for the primary unit (e.g., mg/dL instead of mmol/L)
        param_unit_for_conversion = param.get('unit', '')
        converted_ref = self._get_converted_reference_range(param_name, param_unit_for_conversion)
        if converted_ref:
            ref_range = converted_ref
        
        # If no reference from PDF or special handling, try ReferenceLookup (for CSV files)
        if not ref_range and self.reference_lookup:
            param_name = param.get('spanish_name') or param.get('english_name', '')
            ref_range = self.reference_lookup.get_reference_range(
                parameter_name=param_name,
                sex=self.patient_metadata.get('sex', 'M'),
                birthdate=self.patient_metadata.get('birthdate'),
                age=self.patient_metadata.get('age'),
                menstrual_phase=self.patient_metadata.get('menstrual_phase'),
                bmi=self.patient_metadata.get('bmi')
            ) or ""
        
        # Format reference range for display (truncate if too long for column)
        if ref_range:
            # For multi-phase ranges, show all phases but truncate if necessary
            max_length = 30  # Adjust based on column width
            if len(ref_range) > max_length:
                # Try to show first phase or truncate
                if ',' in ref_range:
                    parts = ref_range.split(',')
                    if len(parts) > 1:
                        # Show first phase and indicate more
                        ref_range = parts[0] + '...'
                ref_range = ref_range[:max_length]
        
        # Center vertically if row is taller
        y_offset = (row_height - 6) / 2 if row_height > 6 else 0
        # Draw filled rectangle for reference column
        self.pdf.rect(x_pos, y_start, col_widths['reference'], row_height, 'F')
        self.pdf.set_xy(x_pos, y_start + y_offset)
        # Use same font and color as other columns (not gray, not small)
        self.pdf.set_text_color(*self.black)
        self.pdf.set_font("Calibri", "", 9)
        self.pdf.cell(col_widths['reference'], 6, ref_range[:25], 0, 0, "C", True)
        x_pos += col_widths['reference']
        
        # Unit - center vertically if row is taller
        y_offset = (row_height - 6) / 2 if row_height > 6 else 0
        # Draw filled rectangle for unit column
        self.pdf.rect(x_pos, y_start, col_widths['unit'], row_height, 'F')
        self.pdf.set_xy(x_pos, y_start + y_offset)
        self.pdf.set_text_color(*self.black)
        self.pdf.set_font("Calibri", "", 9)
        # Allow longer units like "ml/min/1,73m²" (up to 20 chars)
        unit = param.get('unit', '')
        if len(unit) > 20:
            unit = unit[:20]
        self.pdf.cell(col_widths['unit'], 6, unit, 0, 1, "C", True)
        
        # Adjust position for next row based on actual row height
        self.pdf.set_y(y_start + row_height)
        # No line spacing to avoid hachured background effect
    
    def generate_pivoted_table(self, category, dates):
        """Generate pivoted table format when there are more than 5 dates"""
        parameters = category['parameters']
        
        if not parameters:
            return
        
        # Apply specific sorting for Carbohydrate Metabolism category
        category_name = category.get('name', '').upper()
        if 'CARBOHYDRATE' in category_name or 'GLUCIDIQUE' in category_name:
            parameters = self._sort_carbohydrate_metabolism_params(parameters)
        
        # Column widths for pivoted format
        col_widths = {
            'param': 70,  # Increased to accommodate longer parameter names
            'date': 22,
            'result': 22,
            'unit': 15,
            'reference': 30
        }
        headers = ["PARAMETER", "DATE", "RESULT", "UNIT", "REFERENCE"]
        
        # Check if we need a new page before starting table
        if self.pdf.get_y() + 8 + 1 + 6.5 > self.pdf.h - 20:
            self.pdf.add_page()
            self.pdf.set_y(self.pdf.t_margin)
        
        # Draw table header
        self._draw_pivoted_table_header(headers, col_widths)
        
        # Generate rows: for each parameter, for each date with a value
        fill = False
        for param in parameters:
            # Get reference range - first from parameter (PDF), then from ReferenceLookup (CSV)
            ref_range = param.get('reference_range', '')
            
            # Special handling for DHEA (DHYDROEPIANDROSTERONE) with ng/mL unit
            # Use sex-based reference ranges from patient metadata
            param_name = param.get('english_name', '').upper()
            param_unit = param.get('unit', '').upper()
            if ('DHEA' in param_name or 'DEHYDROEPIANDROSTERONE' in param_name) and 'NG/ML' in param_unit:
                patient_sex = self.patient_metadata.get('sex', '').upper()
                if patient_sex == 'M':
                    ref_range = '1.87 - 15.01'
                elif patient_sex == 'F':
                    ref_range = '1.65 - 13.50'
                else:
                    # Default to men's range if sex unknown
                    ref_range = '1.87 - 15.01'
            
            # Special handling for DEHYDROEPIANDROSTERONE-S with µmol/L unit
            # Use age and sex-based reference ranges from patient metadata
            # Get original unit before uppercase conversion for exact match
            param_unit_original = param.get('unit', '')
            param_unit_stripped = param_unit_original.strip()
            if ('DHEA-S' in param_name or 'DEHYDROEPIANDROSTERONE-S' in param_name):
                # Check for µmol/L unit in various formats
                if (param_unit_stripped == "µmol/L" or 
                    'µMOL/L' in param_unit or 'MCMOL/L' in param_unit or 'UMOL/L' in param_unit or
                    'µMOL' in param_unit or 'MCMOL' in param_unit or 'UMOL' in param_unit or
                    'µmol' in param_unit_stripped.lower() or 'mcmol' in param_unit_stripped.lower()):
                    calculated_range = self._get_dhea_s_reference_range()
                    if calculated_range:
                        ref_range = calculated_range
            
            # Special handling for SOMATOMEDIN C (IGF-1) - age and sex dependent
            if ('SOMATOMEDIN' in param_name or 'IGF-1' in param_name or 'IGF1' in param_name) and 'NG/ML' in param_unit:
                ref_range = self._get_igf1_reference_range()
            
            # Special handling for FSH and LH - display "*" instead of reference range
            if ('FSH' in param_name or 'FOLLICLE-STIMULATING HORMONE' in param_name or
                'LH' in param_name or 'LUTEINIZING HORMONE' in param_name or 'LEUTENISING HORMONE' in param_name):
                ref_range = '*'
            
            # Special handling for 17-BETA ESTRADIOL - display "*" instead of reference range
            if ('ESTRADIOL' in param_name or '17-BETA' in param_name or '17 BETA' in param_name or
                'BETA ESTRADIOL' in param_name):
                ref_range = '*'
            
            # Special handling for PROGESTERONE - display "*" instead of reference range
            if 'PROGESTERONE' in param_name:
                ref_range = '*'
            
            # Special handling for TOTAL TESTOSTERONE - use sex-based reference ranges
            if 'TOTAL TESTOSTERONE' in param_name or (param_name == 'TESTOSTERONE' and 'FREE' not in param_name and 'BIOAVAILABLE' not in param_name and 'ESTIMATED' not in param_name):
                patient_sex = self.patient_metadata.get('sex', '').upper()
                if patient_sex == 'M':
                    ref_range = '2.4 - 8.7'
                elif patient_sex == 'F':
                    ref_range = '0.10 - 0.40'
                else:
                    # Default to male range if sex unknown
                    ref_range = '2.4 - 8.7'
            
            # Special handling for ANDROSTENEDIONE DELTA 4 - use age and sex-based reference ranges
            if 'ANDROSTENEDIONE' in param_name or 'DELTA 4' in param_name or 'DELTA-4' in param_name:
                calculated_range = self._get_androstenedione_reference_range()
                if calculated_range:
                    ref_range = calculated_range
            
            # Special handling for T3 REVERSE (rT3) - always use adult reference range
            if 'T3 REVERSE' in param_name or 'REVERSE T3' in param_name or 'RT3' in param_name:
                ref_range = '0.17 - 0.44'
            
            # Check if the reference range needs unit conversion
            # This handles parameters that appear in multiple units but PDF only provides
            # reference for the primary unit (e.g., mg/dL instead of mmol/L)
            param_unit_for_conversion = param.get('unit', '')
            converted_ref = self._get_converted_reference_range(param_name, param_unit_for_conversion)
            if converted_ref:
                ref_range = converted_ref
            
            if not ref_range and self.reference_lookup:
                param_name = param.get('spanish_name') or param.get('english_name', '')
                ref_range = self.reference_lookup.get_reference_range(
                    parameter_name=param_name,
                    sex=self.patient_metadata.get('sex', 'M'),
                    birthdate=self.patient_metadata.get('birthdate'),
                    age=self.patient_metadata.get('age'),
                    menstrual_phase=self.patient_metadata.get('menstrual_phase'),
                    bmi=self.patient_metadata.get('bmi')
                ) or ""
            
            # Format reference range for display
            if ref_range:
                max_length = 25
                if len(ref_range) > max_length:
                    if ',' in ref_range:
                        parts = ref_range.split(',')
                        if len(parts) > 1:
                            ref_range = parts[0] + '...'
                    ref_range = ref_range[:max_length]
            
            # Collect all dates with values for this parameter directly from param['values']
            # This ensures we get all dates that actually have values, regardless of the dates list
            param_dates_with_values = []
            seen_combinations = set()  # Track (date, value) combinations we've already added
            
            # Special case: "Blood group" should only be shown once (take the first/last value)
            is_blood_group = param.get('english_name', '').lower() == 'blood group'
            
            # Iterate directly over param['values'] to get all dates that have values
            for val_obj in param['values']:
                date = val_obj['date']
                value = val_obj['value']
                
                # Skip rows with empty values
                if not value or str(value).strip() == '' or str(value).strip().lower() == 'nan':
                    continue
                
                # Create a unique key for this date-value combination
                combination_key = (date, str(value).strip())
                
                # Skip if we've already added this exact combination
                if combination_key in seen_combinations:
                    continue
                
                # Add to seen combinations and to the list
                seen_combinations.add(combination_key)
                param_dates_with_values.append((date, value))
                
                # For Blood group, only take the first value found
                if is_blood_group:
                    break
            
            # Sort param_dates_with_values chronologically by date
            from datetime import datetime
            def parse_date_for_sort(date_str):
                """Parse date string for sorting - prioritize full year format"""
                date_str = str(date_str).strip()
                # Try full year formats first (4 digits), then 2-digit year formats
                formats = [
                    '%d/%m/%Y',  # 12/08/2020 - full year first
                    '%d-%m-%Y',  # 12-08-2020
                    '%d.%m.%Y',  # 12.08.2020
                    '%Y-%m-%d',  # 2020-08-12
                    '%m/%d/%Y',  # 08/12/2020
                    '%d/%m/%y',  # 12/08/20 - 2-digit year (interprets 00-68 as 2000-2068, 69-99 as 1969-1999)
                    '%d-%m-%y',  # 12-08-20
                    '%d.%m.%y',  # 12.08.20
                    '%m/%d/%y',  # 08/12/20
                ]
                for fmt in formats:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        # For 2-digit years, adjust if needed (but strptime handles this automatically)
                        return parsed
                    except:
                        continue
                return None
            
            # Sort by parsed date
            param_dates_with_values.sort(key=lambda x: (
                parse_date_for_sort(x[0]) or datetime.min,
                x[0]  # Fallback to string comparison if parsing fails
            ))
            
            # Store the fill state for the first row of this parameter (for PARAMETER column)
            param_fill = fill
            
            # Draw rows for this parameter
            for idx, (date, value) in enumerate(param_dates_with_values):
                # Check if we need a new page before drawing this row
                if self.pdf.get_y() + 6.5 + 0.5 > self.pdf.h - 20:
                    self.pdf.add_page()
                    self.pdf.set_y(self.pdf.t_margin)
                    # Redraw header on new page
                    self._draw_pivoted_table_header(headers, col_widths)
                
                # Show parameter name only on first row of each parameter group
                show_param_name = (idx == 0)
                
                # Draw the row: PARAMETER column uses param_fill (fixed for all rows of this param),
                # other columns use fill (alternating)
                self._draw_pivoted_table_row(param, date, value, param.get('unit', ''), ref_range, col_widths, fill, param_fill, show_param_name)
                fill = not fill
        
        # Add margin after table
        self.pdf.ln(4)
    
    def _draw_pivoted_table_header(self, headers, col_widths):
        """Draw header for pivoted table format"""
        # Ensure we're not too close to header
        if self.pdf.get_y() < self.pdf.t_margin:
            self.pdf.set_y(self.pdf.t_margin)
        
        self.pdf.set_font("Calibri", "B", 9)
        self.pdf.set_text_color(*self.black)
        self.pdf.set_fill_color(*self.light_gray)
        
        y_start = self.pdf.get_y()
        x_pos = 15
        
        # PARAMETER column (left-aligned)
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['param'], 8, headers[0], 0, 0, "L", True)
        x_pos += col_widths['param']
        
        # DATE column (center-aligned)
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['date'], 8, headers[1], 0, 0, "C", True)
        x_pos += col_widths['date']
        
        # RESULT column (right-aligned)
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['result'], 8, headers[2], 0, 0, "R", True)
        x_pos += col_widths['result']
        
        # UNIT column (center-aligned)
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['unit'], 8, headers[3], 0, 0, "C", True)
        x_pos += col_widths['unit']
        
        # REFERENCE column (center-aligned)
        self.pdf.set_xy(x_pos, y_start)
        self.pdf.cell(col_widths['reference'], 8, headers[4], 0, 1, "C", True)
        
        self.pdf.ln(1)
    
    def _draw_pivoted_table_row(self, param, date, value, unit, ref_range, col_widths, fill, param_fill, show_param_name=True):
        """Draw a single row in pivoted table format
        
        Args:
            fill: Background fill for DATE, RESULT, UNIT, REFERENCE columns (alternating)
            param_fill: Background fill for PARAMETER column (fixed for all rows of same parameter)
        """
        y_start = self.pdf.get_y()
        x_pos = 15
        
        # Translate Spanish values to English
        if value:
            value = self.translate_value(str(value))
        else:
            value = ""
        
        # Special handling for URINE MICROSCOPE EXAM - display full text if > 8 chars
        param_name_upper = param.get('english_name', '').upper()
        is_urine_microscope = 'URINE MICROSCOPE' in param_name_upper or 'MICROSCOPE EXAM' in param_name_upper
        
        # Pre-calculate value height for URINE MICROSCOPE EXAM if needed
        urine_microscope_value_height = 6
        if is_urine_microscope and value and len(str(value)) > 8:
            # Calculate approximate number of lines needed
            chars_per_line = max(12, int(col_widths['result'] / 2.5))
            estimated_lines = max(1, (len(str(value)) + chars_per_line - 1) // chars_per_line)
            line_height = 3.5  # Height per line in mm
            urine_microscope_value_height = estimated_lines * line_height
        
        # Calculate row height first (needed for all columns)
        param_name = param['english_name'] if show_param_name else ""
        max_chars_per_line = int(col_widths['param'] / 2.5)
        line_height = 3.5  # Height per line in mm
        
        if show_param_name and len(param_name) > max_chars_per_line:
            # Multi-line parameter name
            estimated_lines = max(2, (len(param_name) + max_chars_per_line - 1) // max_chars_per_line)
            param_height = estimated_lines * line_height
            row_height = max(param_height, urine_microscope_value_height, 6)
        else:
            param_height = 6
            row_height = max(urine_microscope_value_height, 6)
        
        # PARAMETER column (left-aligned) - uses param_fill (fixed for all rows of same parameter)
        param_fill_color = self.light_gray if param_fill else self.white
        self.pdf.set_fill_color(*param_fill_color)
        self.pdf.set_font("Calibri", "", 9)
        self.pdf.set_text_color(*self.black)
        
        # Check if this is a sub-parameter that needs indentation
        testosterone_sub_params = ['% FREE TESTOSTERONE', 'ESTIMATED FREE TESTOSTERONE', 'BIOAVAILABLE TESTOSTERONE', 
                      'FREE TESTOSTERONE', 'FREE TESTOSTERONE A']
        # Sub-parameters of LEUCOCYTES (white blood cell differential) - only percentages, NOT absolute counts
        leukocyte_sub_params = ['NEUTROPHIL%', 'LYMPHOCYTE%', 'MONOCYTE%', 'EOSINOPHIL%', 'EOSINOPHILS%', 'BASOPHIL%', 'BASOPHILES%']
        is_testosterone_sub = any(sub in param_name.upper() for sub in testosterone_sub_params) if param_name else False
        is_leukocyte_sub = (any(sub in param_name.upper() for sub in leukocyte_sub_params) and 'LEUCOCYTES' not in param_name.upper()) if param_name else False
        indent = 5 if (is_testosterone_sub or is_leukocyte_sub) else 0  # 5mm indent for sub-parameters
        x_start_param = x_pos + indent
        col_width_adjusted = col_widths['param'] - indent
        
        # Add visual indicator for sub-parameters
        is_sub_param = is_testosterone_sub or is_leukocyte_sub
        display_name = ("  " + param_name) if is_sub_param and param_name else param_name
        
        self.pdf.set_xy(x_pos, y_start)
        
        if show_param_name:
            if len(param_name) > max_chars_per_line:
                # Multi-line: draw filled rectangle first
                self.pdf.rect(x_pos, y_start, col_widths['param'], param_height, 'F')
                # Use multi_cell for wrapping text
                self.pdf.set_xy(x_start_param, y_start)
                y_before = self.pdf.get_y()
                self.pdf.multi_cell(col_width_adjusted, line_height, display_name, 0, "L", False)
                y_after = self.pdf.get_y()
                actual_height = y_after - y_before
                if actual_height > 0:
                    param_height = actual_height
                    row_height = max(param_height, 6)
            else:
                # Single line - draw rectangle for full column, then text with indent
                self.pdf.rect(x_pos, y_start, col_widths['param'], 6, 'F')
                self.pdf.set_xy(x_start_param, y_start)
                self.pdf.cell(col_width_adjusted, 6, display_name, 0, 0, "L", False)
        else:
            # Empty cell for subsequent rows - still use param_fill
            self.pdf.rect(x_pos, y_start, col_widths['param'], 6, 'F')
            self.pdf.cell(col_widths['param'], 6, "", 0, 0, "L", False)
        x_pos += col_widths['param']
        
        # DATE column (center-aligned) - uses fill (alternating)
        fill_color = self.light_gray if fill else self.white
        self.pdf.set_fill_color(*fill_color)
        y_offset = (row_height - 6) / 2 if row_height > 6 else 0
        self.pdf.rect(x_pos, y_start, col_widths['date'], row_height, 'F')
        self.pdf.set_xy(x_pos, y_start + y_offset)
        
        # Format date for display: convert "dd/mm/yyyy" to "dd/mm/yy" to fit in column
        date_display = date
        try:
            from datetime import datetime
            # Try to parse the date and reformat it
            formats = ['%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y', '%d.%m.%Y', '%d.%m.%y']
            parsed_date = None
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date, fmt)
                    break
                except:
                    continue
            
            if parsed_date:
                # Format as dd/mm/yy (2-digit year) to fit in column
                date_display = parsed_date.strftime('%d/%m/%y')
            else:
                # Fallback: if date is in format dd/mm/yyyy, convert to dd/mm/yy
                if len(date) >= 10 and date[2] == '/' and date[5] == '/':
                    # Format: dd/mm/yyyy -> dd/mm/yy
                    date_display = date[:6] + date[-2:]
        except:
            # If anything fails, use original date (truncated if needed)
            max_date_chars = int(col_widths['date'] / 2.5)
            date_display = date[:max_date_chars] if max_date_chars > 0 else date[:10]
        
        self.pdf.cell(col_widths['date'], 6, date_display, 0, 0, "C", True)
        x_pos += col_widths['date']
        
        # RESULT column (right-aligned) - uses fill (alternating)
        # Special handling for URINE MICROSCOPE EXAM - display full text if > 8 chars
        if is_urine_microscope and value and len(str(value)) > 8:
            # Use multi-line display for full text
            self.pdf.rect(x_pos, y_start, col_widths['result'], row_height, 'F')
            self.pdf.set_text_color(*self.black)
            
            # Wrap text manually for right alignment
            wrapped_lines = self.pdf._wrap_text(str(value), col_widths['result'] - 2)  # -2 for padding
            if not wrapped_lines:
                wrapped_lines = [str(value)]
            
            # Draw each line right-aligned
            line_height = 3.5
            y_current = y_start + (row_height - len(wrapped_lines) * line_height) / 2  # Center vertically
            for line in wrapped_lines:
                self.pdf.set_xy(x_pos, y_current)
                # Calculate x position for right alignment
                text_width = self.pdf.get_string_width(line)
                x_right = x_pos + col_widths['result'] - text_width - 1  # -1 for padding
                self.pdf.set_x(x_right)
                self.pdf.cell(col_widths['result'], line_height, line, 0, 0, "R", False)
                y_current += line_height
            
            # Reset position for next column
            self.pdf.set_xy(x_pos + col_widths['result'], y_start)
            x_pos += col_widths['result']
        else:
            y_offset = (row_height - 6) / 2 if row_height > 6 else 0
            self.pdf.rect(x_pos, y_start, col_widths['result'], row_height, 'F')
            self.pdf.set_xy(x_pos, y_start + y_offset)
            max_result_chars = int(col_widths['result'] / 2.5)
            result_display = str(value)[:max_result_chars] if max_result_chars > 0 else str(value)[:10]
            self.pdf.cell(col_widths['result'], 6, result_display, 0, 0, "R", True)
            x_pos += col_widths['result']
        
        # UNIT column (center-aligned) - uses fill (alternating)
        y_offset = (row_height - 6) / 2 if row_height > 6 else 0
        self.pdf.rect(x_pos, y_start, col_widths['unit'], row_height, 'F')
        self.pdf.set_xy(x_pos, y_start + y_offset)
        # Allow longer units like "ml/min/1,73m²" (up to 20 chars)
        unit_display = str(unit) if unit else ""
        if len(unit_display) > 20:
            unit_display = unit_display[:20]
        self.pdf.cell(col_widths['unit'], 6, unit_display, 0, 0, "C", True)
        x_pos += col_widths['unit']
        
        # REFERENCE column (center-aligned) - uses fill (alternating)
        y_offset = (row_height - 6) / 2 if row_height > 6 else 0
        self.pdf.rect(x_pos, y_start, col_widths['reference'], row_height, 'F')
        self.pdf.set_xy(x_pos, y_start + y_offset)
        ref_display = ref_range[:20] if ref_range else ""
        self.pdf.cell(col_widths['reference'], 6, ref_display, 0, 1, "C", True)
        
        # Adjust position for next row based on actual row height
        self.pdf.set_y(y_start + row_height)
        # No line spacing to avoid hachured background effect
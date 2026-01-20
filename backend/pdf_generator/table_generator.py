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
    
    def generate_category_table(self, category, dates):
        """Generate table for a category"""
        parameters = category['parameters']
        
        if not parameters:
            return
        
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
                'param': 65,
                'date': 25,
                'reference': 40,
                'unit': 20
            }
            headers = ["PARAMETER", dates[0] if dates else "VALUE", "REFERENCE", "UNIT"]
        elif n_dates == 2:
            col_widths = {
                'param': 55,
                'date': 22,
                'reference': 35,
                'unit': 18
            }
            headers = ["PARAMETER", "BASELINE", "FOLLOW-UP", "REFERENCE", "UNIT"]
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
        for param in parameters:
            # Check if we need a new page before drawing this row
            # Row height (6.5) + spacing (0.5) + bottom margin (20)
            if self.pdf.get_y() + 6.5 + 0.5 > self.pdf.h - 20:
                self.pdf.add_page()
                # Ensure we start below the header
                self.pdf.set_y(self.pdf.t_margin)
                # Redraw header on new page
                self._draw_table_header(headers, col_widths, n_dates)
            
            fill = not fill
            self._draw_table_row(param, dates, col_widths, n_dates, fill)
        
        # Add margin after table
        self.pdf.ln(8)
    
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
                self.pdf.cell(col_widths['date'], 8, header[:10], 0, 0, "R", True)  # Changed "L" to "R"
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
    
    def _draw_table_row(self, param, dates, col_widths, n_dates, fill):
        """Draw a table row for a parameter"""
        fill_color = self.light_gray if fill else self.white
        self.pdf.set_fill_color(*fill_color)
        
        y_start = self.pdf.get_y()
        
        # Parameter name - handle long names with multi-line
        self.pdf.set_font("Calibri", "", 9)
        self.pdf.set_text_color(*self.black)
        param_name = param['english_name']
        
        # Check if parameter name is longer than 33 characters
        if len(param_name) > 33:
            # Calculate approximate number of lines needed
            # Estimate: approximately 33 characters per line for column width
            estimated_lines = max(2, (len(param_name) + 32) // 33)  # Round up division
            line_height = 3.5  # Height per line in mm for font size 9
            param_height = estimated_lines * line_height
            
            # Draw filled rectangle for the parameter column first
            self.pdf.rect(15, y_start, col_widths['param'], param_height, 'F')
            
            # Use multi_cell for wrapping text
            self.pdf.set_xy(15, y_start)
            # Save current Y position before multi_cell
            y_before = self.pdf.get_y()
            self.pdf.multi_cell(col_widths['param'], line_height, param_name, 0, "L", False)
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
            self.pdf.set_xy(15, y_start)
            self.pdf.cell(col_widths['param'], 6, param_name, 0, 0, "L", True)
            param_height = 6
        
        x_pos = 15 + col_widths['param']
        
        # Calculate row height based on parameter name height
        row_height = max(param_height, 6)
        
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
            
            # Center vertically if row is taller than 6mm
            y_offset = (row_height - 6) / 2 if row_height > 6 else 0
            # Draw filled rectangle for date column
            self.pdf.rect(x_pos, y_start, col_widths['date'], row_height, 'F')
            self.pdf.set_xy(x_pos, y_start + y_offset)
            self.pdf.set_text_color(*self.black)
            self.pdf.cell(col_widths['date'], 6, str(value)[:8], 0, 0, "R", True)
            x_pos += col_widths['date']
        
        # Reference range
        ref_range = ""
        if self.reference_lookup:
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
        unit = param.get('unit', '')[:8]
        self.pdf.cell(col_widths['unit'], 6, unit, 0, 1, "C", True)
        
        # Adjust position for next row based on actual row height
        self.pdf.set_y(y_start + row_height)
        # No line spacing to avoid hachured background effect
    
    def generate_pivoted_table(self, category, dates):
        """Generate pivoted table format when there are more than 5 dates"""
        parameters = category['parameters']
        
        if not parameters:
            return
        
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
            # Get reference range once per parameter (same for all date rows)
            ref_range = ""
            if self.reference_lookup:
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
        self.pdf.ln(8)
    
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
        
        # Calculate row height first (needed for all columns)
        param_name = param['english_name'] if show_param_name else ""
        max_chars_per_line = int(col_widths['param'] / 2.5)
        line_height = 3.5  # Height per line in mm
        
        if show_param_name and len(param_name) > max_chars_per_line:
            # Multi-line parameter name
            estimated_lines = max(2, (len(param_name) + max_chars_per_line - 1) // max_chars_per_line)
            param_height = estimated_lines * line_height
            row_height = max(param_height, 6)
        else:
            param_height = 6
            row_height = 6
        
        # PARAMETER column (left-aligned) - uses param_fill (fixed for all rows of same parameter)
        param_fill_color = self.light_gray if param_fill else self.white
        self.pdf.set_fill_color(*param_fill_color)
        self.pdf.set_font("Calibri", "", 9)
        self.pdf.set_text_color(*self.black)
        self.pdf.set_xy(x_pos, y_start)
        
        if show_param_name:
            if len(param_name) > max_chars_per_line:
                # Multi-line: draw filled rectangle first
                self.pdf.rect(x_pos, y_start, col_widths['param'], param_height, 'F')
                # Use multi_cell for wrapping text
                y_before = self.pdf.get_y()
                self.pdf.multi_cell(col_widths['param'], line_height, param_name, 0, "L", False)
                y_after = self.pdf.get_y()
                actual_height = y_after - y_before
                if actual_height > 0:
                    param_height = actual_height
                    row_height = max(param_height, 6)
            else:
                # Single line
                self.pdf.cell(col_widths['param'], 6, param_name, 0, 0, "L", True)
        else:
            # Empty cell for subsequent rows - still use param_fill
            self.pdf.cell(col_widths['param'], 6, "", 0, 0, "L", True)
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
        unit_display = str(unit)[:8] if unit else ""
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
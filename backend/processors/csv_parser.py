import pandas as pd
import numpy as np
import json
import os
import re
import unicodedata

class CSVParser:
    """Parse CSV files with medical data structure"""
    
    def __init__(self):
        self.categories_config = self._load_categories_config()
        self.parameters_config = self._load_parameters_config()
    
    def _load_categories_config(self):
        """Load categories configuration"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'categories.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_parameters_config(self):
        """Load parameters configuration"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'parameters.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _is_category_row(self, row):
        """Check if a row represents a category header"""
        # Skip empty rows or rows with insufficient columns
        if len(row) == 0:
            return False
        
        # Category rows have non-empty first column and mostly empty subsequent columns
        try:
            first_col = str(row.iloc[0]).strip()
        except (IndexError, KeyError):
            return False
        
        if not first_col or first_col == 'nan':
            return False
        
        # Check if first column is not empty and has few non-empty values in other columns
        try:
            non_empty_count = sum(1 for val in row.iloc[1:] if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan')
        except (IndexError, KeyError):
            return False
        
        return non_empty_count < 3  # Category rows have very few values
    
    def _is_parameter_row(self, row):
        """Check if a row represents a parameter"""
        # Skip empty rows or rows with insufficient columns
        if len(row) == 0:
            return False
        
        # Parameter rows start with empty first column (comma in CSV)
        try:
            first_col = str(row.iloc[0]).strip()
        except (IndexError, KeyError):
            return False
        
        return first_col == '' or first_col == 'nan'
    
    def _extract_date_columns(self, df):
        """Extract date columns from the CSV and the row index that contains them.

        Many lab exports use a layout like:
        - Row 2: headers (Analisis, ID ..., Unidad)
        - Row 3: dates
        But some files can shift these rows. We therefore *search* for the row that looks
        most like a date row (contains multiple date-like strings).
        """
        if df is None or df.empty or df.shape[0] < 2:
            return [], None

        def _looks_like_date(s: str) -> bool:
            if not s or s.lower() in ("nan", "none", "null"):
                return False
            s = s.strip()
            return ("/" in s) or ("." in s) or ("-" in s)

        best_row_idx = None
        best_score = 0

        # Search the first 10 rows (or fewer) for a likely date row
        max_scan = min(10, df.shape[0])
        for r in range(max_scan):
            try:
                row = df.iloc[r]
            except (IndexError, KeyError):
                continue
            score = 0
            for c, v in enumerate(row):
                if c <= 1:  # skip first two columns (empty + "Analisis")
                    continue
                if _looks_like_date(str(v)):
                    score += 1
            if score > best_score:
                best_score = score
                best_row_idx = r

        if best_row_idx is None or best_score == 0:
            return [], None

        date_row = df.iloc[best_row_idx]
        date_columns = []

        # Unit column is usually the last non-empty header column, but dates row often ends with empty.
        unit_col_guess = df.shape[1] - 1

        for idx, val in enumerate(date_row):
            # Skip first two columns (empty + "Analisis") and likely unit column
            if idx <= 1 or idx == unit_col_guess:
                continue

            val_str = str(val).strip()
            if not val_str or val_str == "nan":
                continue

            if _looks_like_date(val_str):
                date_columns.append(idx)

        return date_columns, best_row_idx

    def _find_header_row_idx(self, df):
        """Find the header row (contains 'Analisis' and/or 'Unidad')."""
        if df is None or df.empty:
            return None
        max_scan = min(10, df.shape[0])
        for r in range(max_scan):
            try:
                row = df.iloc[r]
            except (IndexError, KeyError):
                continue
            joined = " ".join(str(x).strip().upper() for x in row if pd.notna(x))
            if "ANALISIS" in joined or "UNIDAD" in joined:
                return r
        return None
    
    def parse(self, filepath):
        """Parse CSV file and extract structured data"""
        # Read CSV without header to preserve structure
        df = pd.read_csv(filepath, header=None, encoding='utf-8')
        if df is None or df.empty:
            return {'categories': [], 'date_columns': []}
        
        # Extract date columns
        date_cols, date_row_idx = self._extract_date_columns(df)
        header_row_idx = self._find_header_row_idx(df)

        # If we couldn't find a date row, we can't build the report safely
        if not date_cols or date_row_idx is None:
            raise ValueError("Could not detect the date row/columns in the CSV. Please verify the export format.")
        
        # Find unit column by looking for "Unidad" in header row (row 2, index 2)
        # Note: CSV structure: row 0-1 (metadata), row 2 (headers with "Analisis", "ID ...", "Unidad"), row 3 (dates), row 4+ (data)
        unit_col = None
        if header_row_idx is not None:
            try:
                header_row = df.iloc[header_row_idx]
                for idx, val in enumerate(header_row):
                    val_str = str(val).strip().upper()
                    if 'UNIDAD' in val_str:
                        unit_col = idx
                        break
            except (IndexError, KeyError):
                unit_col = None
        
        # Fallback: try second-to-last column (index df.shape[1] - 2) as "Unidad" is usually before the last empty column
        if unit_col is None:
            # The "Unidad" column is typically the second-to-last column (before the trailing empty column)
            unit_col = df.shape[1] - 2 if df.shape[1] > 1 else df.shape[1] - 1
        
        # Extract categories and parameters
        categories = []
        current_category = None
        parameters = []
        
        # Start after the date/header rows (whichever is lower), but never before 0
        data_start_idx = max(i for i in [date_row_idx, header_row_idx] if i is not None) + 1
        data_start_idx = max(0, data_start_idx)

        for idx in range(data_start_idx, len(df)):
            row = df.iloc[idx]
            
            # Skip empty rows
            if len(row) == 0:
                continue
            
            # Check if it's a category row
            if self._is_category_row(row):
                try:
                    category_name_spanish = str(row.iloc[0]).strip()
                except (IndexError, KeyError):
                    continue
                # Map to English category name
                category_name = self._map_category_to_english(category_name_spanish)
                current_category = {
                    'name': category_name,
                    'spanish_name': category_name_spanish,
                    'parameters': []
                }
                categories.append(current_category)
            
            # Check if it's a parameter row
            elif self._is_parameter_row(row) and current_category is not None:
                try:
                    param_name_spanish = str(row.iloc[1]).strip() if len(row) > 1 else ''
                except (IndexError, KeyError):
                    continue
                
                if param_name_spanish and param_name_spanish != 'nan':
                    # Extract values for each date column
                    values = {}
                    for date_col_idx in date_cols:
                        if date_col_idx < len(row):
                            val = row.iloc[date_col_idx]
                            if pd.notna(val) and str(val).strip() and str(val).strip() != 'nan':
                                # Get date from row 3
                                if date_row_idx < df.shape[0] and date_col_idx < df.shape[1]:
                                    date_str = str(df.iloc[date_row_idx, date_col_idx]).strip()
                                else:
                                    continue
                                values[date_str] = str(val).strip()
                    
                    # Extract unit from the "Unidad" column
                    # The unit column is typically the second-to-last column (before the trailing empty column)
                    unit = ''
                    if unit_col is not None:
                        # Ensure we don't go out of bounds
                        if unit_col < len(row):
                            try:
                                unit_val = row.iloc[unit_col]
                                if pd.notna(unit_val):
                                    unit_str = str(unit_val).strip()
                                    # Only use if not empty and not 'nan'
                                    # Also check for common empty patterns
                                    if unit_str and unit_str.lower() not in ['nan', '', 'none', 'null', 'n/a', 'na']:
                                        unit = self._normalize_unit(unit_str)
                            except (IndexError, KeyError):
                                pass
                        # Also try the second-to-last column as fallback if unit_col didn't work
                        elif df.shape[1] > 1:
                            try:
                                fallback_col = df.shape[1] - 2
                                if fallback_col < len(row):
                                    unit_val = row.iloc[fallback_col]
                                    if pd.notna(unit_val):
                                        unit_str = str(unit_val).strip()
                                        if unit_str and unit_str.lower() not in ['nan', '', 'none', 'null', 'n/a', 'na']:
                                            unit = self._normalize_unit(unit_str)
                            except (IndexError, KeyError):
                                pass
                    
                    # Map parameter name to English (needed for fallback unit)
                    param_info = self._map_parameter_to_english(param_name_spanish)
                    
                    # If unit is still empty, try to get it from the parameter config as fallback
                    if not unit:
                        unit = param_info.get('unit', '')
                    else:
                        # Normalize the unit even if it came from CSV
                        unit = self._normalize_unit(unit)
                    
                    # Use category from parameters.json if available, otherwise use CSV category
                    param_category = param_info.get('category', '')
                    if not param_category:
                        param_category = current_category['name']
                    
                    # Use unit from CSV if available, otherwise from config (already set above)
                    parameter = {
                        'spanish_name': param_name_spanish,
                        'english_name': param_info.get('english_name', param_name_spanish),
                        'category': param_category,  # Use category from parameters.json if available
                        'unit': unit,  # Already has CSV unit or config fallback
                        'values': values,
                        'explanation': param_info.get('explanation', '')
                    }
                    
                    current_category['parameters'].append(parameter)
        
        return {
            'categories': categories,
            'date_columns': [
                str(df.iloc[date_row_idx, idx]).strip()
                for idx in date_cols
                if date_row_idx is not None and date_row_idx < df.shape[0] and idx < df.shape[1]
            ]
        }
    
    def _map_category_to_english(self, spanish_name):
        """Map Spanish category name to English"""
        if not spanish_name:
            return spanish_name

        # Normalize (handles accents / composed-vs-decomposed) and remove parenthetical qualifiers
        s = unicodedata.normalize("NFC", str(spanish_name)).strip()
        s = re.sub(r"\s*\([^)]*\)\s*", "", s).strip()  # e.g., "Endocrinología (suero/plasma)" -> "Endocrinología"
        s_lower = s.lower()

        # Direct exact match against configured spanish_name
        for cat in self.categories_config['categories']:
            cfg = unicodedata.normalize("NFC", str(cat.get("spanish_name", ""))).strip()
            if cfg and cfg.lower() == s_lower:
                return cat["name"]

        # Common Spanish variants that appear in data.csv but categories.json uses FR labels
        alias_map = {
            "inmunología": "Immunology",
            "inmunologia": "Immunology",
            "endocrinología": "Endocrinology - Pituitary Hormones",  # generic fallback bucket
            "endocrinologia": "Endocrinology - Pituitary Hormones",
        }
        if s_lower in alias_map:
            return alias_map[s_lower]

        # If not found, return cleaned version (will be handled downstream)
        return s
    
    def _normalize_unit(self, unit_str):
        """Normalize unit string to fix encoding issues and convert to proper Unicode characters"""
        if not unit_str:
            return ''
        
        unit_str = str(unit_str).strip()
        
        # Fix common encoding issues: "x10&6" -> "x10⁶", "&3" -> "³", etc.
        # Map of common malformed patterns to Unicode characters
        replacements = {
            r'x10&6': 'x10⁶',
            r'x10&3': 'x10³',
            r'x10&2': 'x10²',
            r'x10&1': 'x10¹',
            r'x10&0': 'x10⁰',
            r'&6': '⁶',
            r'&3': '³',
            r'&2': '²',
            r'&1': '¹',
            r'&0': '⁰',
            r'/mm$': '/mm³',  # If ends with /mm, likely should be /mm³
            r'/mm\s*$': '/mm³',  # Same with trailing space
        }
        
        # Apply replacements
        for pattern, replacement in replacements.items():
            unit_str = re.sub(pattern, replacement, unit_str, flags=re.IGNORECASE)
        
        # Also handle cases where superscripts might be encoded as HTML entities or other formats
        # e.g., "x10^6" -> "x10⁶"
        unit_str = re.sub(r'x10\^6', 'x10⁶', unit_str, flags=re.IGNORECASE)
        unit_str = re.sub(r'x10\^3', 'x10³', unit_str, flags=re.IGNORECASE)
        unit_str = re.sub(r'x10\^2', 'x10²', unit_str, flags=re.IGNORECASE)
        
        return unit_str
    
    def _map_parameter_to_english(self, spanish_name):
        """Map Spanish parameter name to English and get metadata"""
        if spanish_name in self.parameters_config:
            return self.parameters_config[spanish_name]
        
        # Return default structure if not found
        return {
            'english_name': spanish_name,
            'category': '',
            'unit': '',
            'explanation': ''
        }

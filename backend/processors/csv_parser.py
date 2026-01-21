import pandas as pd
import numpy as np
import json
import os
import re
import unicodedata
import logging

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
        
        if not first_col or first_col == 'nan' or first_col == '':
            return False
        
        # Exclude rows that look like dates or IDs
        first_col_upper = first_col.upper()
        if any(x in first_col_upper for x in ['ID ', 'ANALISIS', 'UNIDAD', '/', '-', '.']):
            # Check if it contains date-like patterns (numbers with separators)
            if any(c.isdigit() for c in first_col) and (('/' in first_col) or ('-' in first_col) or ('.' in first_col)):
                return False
        
        # Check if first column is not empty and has few non-empty values in other columns
        try:
            non_empty_count = sum(1 for val in row.iloc[1:] if pd.notna(val) and str(val).strip() and str(val).strip() not in ['nan', '', 'None', 'null'])
        except (IndexError, KeyError):
            return False
        
        # Category rows have very few values in other columns (relaxed from < 3 to < 5)
        return non_empty_count < 5
    
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
            if not s or s.lower() in ("nan", "none", "null", ""):
                return False
            s = str(s).strip()
            if not s:
                return False
            
            # Exclude common non-date patterns first
            s_lower = s.lower()
            if any(x in s_lower for x in ["id", "analisis", "unidad", "unit"]):
                return False
            
            # Must contain date separators
            has_separator = ("/" in s) or ("." in s) or ("-" in s)
            if not has_separator:
                return False
            
            # Check if it looks like a date format (has numbers)
            has_numbers = any(c.isdigit() for c in s)
            if not has_numbers:
                return False
            
            # IMPORTANT: Exclude pure decimal numbers (e.g., "4.82", "14.7", "44.9")
            # These are NOT dates even though they have separators
            # A date should have at least 2 separators (DD/MM/YYYY) or be in a recognizable date format
            separator_count = s.count("/") + s.count(".") + s.count("-")
            
            # If only one separator, check if it's a date-like pattern
            # Dates typically have: DD/MM/YYYY (2 separators) or DD-MM-YY (2 separators)
            # Pure decimals like "4.82" have only 1 separator
            if separator_count == 1:
                # Check if it's a decimal number (has digits before and after separator)
                import re
                # Pattern: digits.separator.digits (decimal number)
                if re.match(r'^\d+[./-]\d+$', s):
                    # This looks like a decimal, not a date
                    return False
                # If it's like "01/10" (day/month without year), it might still be a date
                # But we'll be conservative and require at least 2 separators for dates
            
            # Try to parse as date to validate format
            # Check if it matches common date patterns: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
            import re
            date_patterns = [
                r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$',  # DD/MM/YYYY or DD-MM-YYYY
                r'^\d{1,2}\.\d{1,2}\.\d{2,4}$',      # DD.MM.YYYY
            ]
            for pattern in date_patterns:
                if re.match(pattern, s):
                    # Additional validation: check if parts make sense as date
                    parts = re.split(r'[/.\-]', s)
                    if len(parts) >= 2:
                        try:
                            part1 = int(parts[0])
                            part2 = int(parts[1])
                            # Day should be 1-31, month should be 1-12
                            if (1 <= part1 <= 31 and 1 <= part2 <= 12) or (1 <= part2 <= 31 and 1 <= part1 <= 12):
                                return True
                        except ValueError:
                            pass
            
            # If we have 2+ separators and it looks date-like, accept it
            if separator_count >= 2:
                return True
            
            return False

        best_row_idx = None
        best_score = 0

        # Search the first 15 rows (or fewer) for a likely date row - increased from 10
        max_scan = min(15, df.shape[0])

        # 1) Deterministic fast-path for known export structure:
        # header row contains "Analisis" and/or "Unidad", and the next row contains the dates.
        # This matches both data.csv and data_short.csv and avoids "sometimes" behavior.
        try:
            header_row_idx = self._find_header_row_idx(df)
            if header_row_idx is not None and header_row_idx + 1 < df.shape[0]:
                candidate_idx = header_row_idx + 1
                row = df.iloc[candidate_idx]
                date_like = 0
                for c, v in enumerate(row):
                    if c <= 1:
                        continue
                    if _looks_like_date(str(v)):
                        date_like += 1
                if date_like >= 1:
                    best_row_idx = candidate_idx
                    best_score = date_like
        except Exception:
            # Keep silent; we fall back to heuristic scan below.
            pass

        # 2) Fallback heuristic scan (for shifted/weird files)
        if best_row_idx is None:
            for r in range(max_scan):
                try:
                    row = df.iloc[r]
                except (IndexError, KeyError):
                    continue
                score = 0
                date_like_count = 0
                for c, v in enumerate(row):
                    if c <= 1:  # skip first two columns (empty + "Analisis")
                        continue
                    if _looks_like_date(str(v)):
                        date_like_count += 1
                        score += 1
                # Also check if this row has a reasonable number of date-like values
                # (at least 2 to be considered a date row)
                if date_like_count >= 2 and score > best_score:
                    best_score = score
                    best_row_idx = r

        # If we still haven't found a good date row, try a more lenient approach
        # Look for any row with at least 1 date-like value (might be a file with few dates)
        if best_row_idx is None or best_score == 0:
            for r in range(max_scan):
                try:
                    row = df.iloc[r]
                except (IndexError, KeyError):
                    continue
                score = 0
                for c, v in enumerate(row):
                    if c <= 1:
                        continue
                    if _looks_like_date(str(v)):
                        score += 1
                if score >= 1:  # At least 1 date found
                    best_score = score
                    best_row_idx = r
                    break

        if best_row_idx is None or best_score == 0:
            return [], None

        date_row = df.iloc[best_row_idx]
        date_columns = []

        # Unit column is usually the last non-empty header column, but dates row often ends with empty.
        # Try to detect it more intelligently
        unit_col_guess = None
        # Check if last column looks like units (contains common unit words)
        if df.shape[1] > 0:
            last_col_idx = df.shape[1] - 1
            # Check header row for "Unidad"
            header_row_idx = self._find_header_row_idx(df)
            if header_row_idx is not None:
                try:
                    header_row = df.iloc[header_row_idx]
                    for idx, val in enumerate(header_row):
                        val_str = str(val).strip().upper()
                        if 'UNIDAD' in val_str:
                            unit_col_guess = idx
                            break
                except (IndexError, KeyError):
                    pass
        
        if unit_col_guess is None:
            unit_col_guess = df.shape[1] - 1

        for idx, val in enumerate(date_row):
            # Skip first two columns (empty + "Analisis") and likely unit column
            if idx <= 1:
                continue
            if unit_col_guess is not None and idx == unit_col_guess:
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
        logger = logging.getLogger(__name__)

        # Read CSV without header to preserve structure.
        # In production we frequently get delimiter/encoding variations (',' vs ';', UTF-8 vs Latin-1).
        # If pandas reads everything into one column, date detection will fail -> intermittent 400s.
        def _try_read(enc: str, sep):
            try:
                return pd.read_csv(
                    filepath,
                    header=None,
                    encoding=enc,
                    sep=sep,
                    engine="python",
                    dtype=str,
                    keep_default_na=False,
                )
            except Exception:
                return None

        # Try best-effort combinations; pick the one that can detect dates reliably.
        candidates = []
        for enc in ("utf-8-sig", "utf-8", "latin1"):
            # sep=None lets python engine sniff delimiter
            for sep in (None, ",", ";", "\t"):
                df_try = _try_read(enc, sep)
                if df_try is None or df_try.empty:
                    continue
                # Normalize empty strings to 'nan'-like checks downstream
                # (we already keep_default_na=False, so empties stay as "")
                date_cols_try, date_row_try = self._extract_date_columns(df_try)
                # Prefer candidates that actually detect dates; then prefer more date columns; then more columns.
                score = (1 if (date_cols_try and date_row_try is not None) else 0, len(date_cols_try), df_try.shape[1])
                candidates.append((score, enc, sep, df_try, date_cols_try, date_row_try))

        if not candidates:
            return {'categories': [], 'date_columns': []}

        # Prefer: detected dates, more detected date columns, then wider frame
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_enc, best_sep, df, date_cols, date_row_idx = candidates[0]

        # Guard against obviously incomplete/truncated files (very small shape)
        if df.shape[0] < 3 or df.shape[1] < 5:
            logger.warning(
                f"CSV appears incomplete/truncated: shape={df.shape}, encoding={best_enc}, sep={best_sep}"
            )
            raise ValueError("CSV file seems incomplete or truncated. Please re-export the CSV and try again.")

        logger.info(
            f"CSV read: shape={df.shape}, encoding={best_enc}, sep={best_sep}, "
            f"date_row_idx={date_row_idx}, date_cols={len(date_cols)}"
        )
        
        # Extract date columns
        header_row_idx = self._find_header_row_idx(df)

        # If we couldn't find a date row, we can't build the report safely
        if not date_cols or date_row_idx is None:
            # Log a small sample to help debug production uploads without dumping the whole file
            try:
                # ULTIMATE DIAGNOSTIC: Log the first 10 lines of the RAW file as text
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    raw_lines = [f.readline() for _ in range(10)]
                logger.warning(f"Date detection failed. RAW FILE CONTENT (10 lines):\n" + "".join(raw_lines))
                
                # Also log hex prefix
                with open(filepath, 'rb') as f:
                    hex_prefix = f.read(32).hex()
                logger.warning(f"File hex prefix: {hex_prefix}")
                
                sample = df.head(6).to_string(index=False, header=False)
                logger.warning(f"Pandas head(6) with chosen candidate:\n{sample}")
                # Also log a quick summary of the parsing candidates (top 5) to diagnose
                # intermittent delimiter/encoding issues in production.
                try:
                    top = candidates[:5]
                    cand_lines = []
                    for score, enc, sep, df_try, date_cols_try, date_row_try in top:
                        cand_lines.append(
                            f"- score={score} enc={enc} sep={sep} shape={df_try.shape} "
                            f"date_row={date_row_try} n_date_cols={len(date_cols_try)}"
                        )
                    logger.warning("CSV candidates (top 5):\n" + "\n".join(cand_lines))
                except Exception:
                    pass
                # Log header/date rows vicinity if present
                try:
                    hdr = self._find_header_row_idx(df)
                    logger.warning(f"Detected header_row_idx={hdr}, chosen date_row_idx={date_row_idx}")
                    if hdr is not None:
                        logger.warning("Header row:\n" + df.iloc[hdr].to_string(index=False, header=False))
                        if hdr + 1 < df.shape[0]:
                            logger.warning("Row after header (expected dates):\n" + df.iloc[hdr + 1].to_string(index=False, header=False))
                except Exception:
                    pass
            except Exception:
                pass
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
                if category_name_spanish and category_name_spanish != 'nan':
                    # Map to English category name
                    category_name = self._map_category_to_english(category_name_spanish)
                    current_category = {
                        'name': category_name,
                        'spanish_name': category_name_spanish,
                        'parameters': []
                    }
                    categories.append(current_category)
            
            # Check if it's a parameter row
            # Allow parameters even if no category found (will use default "General")
            if self._is_parameter_row(row):
                if current_category is None:
                    # Create default category if none exists
                    current_category = {
                        'name': 'General',
                        'spanish_name': 'General',
                        'parameters': []
                    }
                    categories.append(current_category)
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

        def _clean(text: str) -> str:
            # Normalize, strip, and drop any parenthetical qualifier for matching
            txt = unicodedata.normalize("NFC", str(text)).strip()
            txt = re.sub(r"\s*\([^)]*\)\s*", "", txt).strip()
            return txt.lower()

        s_lower = _clean(spanish_name)

        # Direct exact match against configured spanish_name (cleaned too)
        for cat in self.categories_config['categories']:
            cfg = cat.get("spanish_name", "")
            if cfg and _clean(cfg) == s_lower:
                return cat["name"]

        # Common Spanish variants that appear in data.csv but categories.json uses FR labels
        alias_map = {
            "inmunología": "Immunology",
            "inmunologia": "Immunology",
            "endocrinología": "Endocrinology - Pituitary Hormones",  # generic fallback bucket
            "endocrinologia": "Endocrinology - Pituitary Hormones",
            "serologia": "Serology",
            "serología": "Serology",
            "nota asociada al informe": "Report Notes",
            "nota aclaratoria informe": "Report Notes",
            "otras pruebas": "Other Tests",
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

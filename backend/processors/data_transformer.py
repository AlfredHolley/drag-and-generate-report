import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

class DataTransformer:
    """Transform parsed CSV/PDF data into structured format for PDF generation"""
    
    def __init__(self):
        self.categories_config = self._load_categories_config()
    
    def _load_categories_config(self):
        """Load categories configuration"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'categories.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def transform(self, raw_data, reference_ranges=None):
        """Transform raw parsed data into structured format, regrouping by REFERENCE_VALUES.md categories
        
        Args:
            raw_data: Parsed data from CSV or PDF parser
            reference_ranges: Optional dict of parameter_name -> reference_range (from PDF)
        """
        categories = raw_data['categories']
        date_columns = raw_data['date_columns']
        
        # Store reference ranges for use in _transform_parameter
        self._reference_ranges = reference_ranges or {}
        
        # Sort dates chronologically
        sorted_dates = self._sort_dates(date_columns)
        
        # Collect all parameters from all categories
        all_parameters = []
        for category in categories:
            for param in category['parameters']:
                # Check if parameter has values BEFORE transformation
                # Values can be in dict format {date: value} from CSV/PDF parser
                raw_values = param.get('values', {})
                has_raw_values = False
                if isinstance(raw_values, dict):
                    # Check if dict has any non-empty values
                    for date_key, val in raw_values.items():
                        if val and str(val).strip() and str(val).strip().lower() not in ['nan', '', 'none', 'null']:
                            has_raw_values = True
                            break
                elif isinstance(raw_values, list):
                    # Already transformed format
                    for val_obj in raw_values:
                        value = val_obj.get('value') if isinstance(val_obj, dict) else val_obj
                        if value and str(value).strip() and str(value).strip().lower() not in ['nan', '', 'none', 'null']:
                            has_raw_values = True
                            break
                
                # Only transform and add parameters that have values
                if has_raw_values:
                    transformed_param = self._transform_parameter(param, sorted_dates)
                    all_parameters.append(transformed_param)
        
        # Regroup parameters by their category from parameters.json (or CSV category as fallback)
        # Use categories from REFERENCE_VALUES.md (categories.json) in the correct order
        category_map = {}
        for param in all_parameters:
            # Double-check: Filter out parameters with no values after transformation
            has_values = False
            for val_obj in param.get('values', []):
                value = val_obj.get('value') if isinstance(val_obj, dict) else val_obj
                if value and str(value).strip() and str(value).strip().lower() not in ['nan', '', 'none', 'null']:
                    has_values = True
                    break
            
            # Skip parameters with no values (shouldn't happen if check above worked, but safety check)
            if not has_values:
                continue
            
            # Use category from parameter config if available, otherwise use CSV category
            original_category = param.get('category', '')  # may be a raw CSV category name
            param_category = original_category
            
            # If category is empty or not in our reference categories, try to find it
            if not param_category or not self._is_valid_category(param_category):
                # Try to find category from parameters.json via the parameter name
                param_category = self._get_category_from_config(param.get('spanish_name', ''), param_category)
            
            # If still no valid category, try to find a matching category by partial name
            if not param_category or not self._is_valid_category(param_category):
                param_category = self._find_similar_category(param_category)
            
            # If still no valid category, do NOT drop the parameter:
            # keep it under its original CSV category if present, otherwise a safe fallback bucket.
            if not param_category:
                param_category = original_category or 'Uncategorized'
            
            if param_category not in category_map:
                category_map[param_category] = []
            category_map[param_category].append(param)
        
        # Build transformed categories in the order defined in categories.json (REFERENCE_VALUES.md order)
        transformed_categories = []
        for ref_category in self.categories_config['categories']:
            category_name = ref_category['name']
            if category_name in category_map and category_map[category_name]:
                transformed_category = {
                    'name': category_name,
                    'spanish_name': ref_category.get('spanish_name', ''),
                    'parameters': category_map[category_name]
                }
                transformed_categories.append(transformed_category)
        
        # Add any remaining categories that have parameters but aren't in REFERENCE_VALUES.md
        for category_name, params in category_map.items():
            if category_name not in [cat['name'] for cat in transformed_categories]:
                # Find category info or create default
                category_info = self._get_category_info(category_name)
                transformed_category = {
                    'name': category_name,
                    'spanish_name': category_info.get('spanish_name', ''),
                    'parameters': params
                }
                transformed_categories.append(transformed_category)
        
        # Ensure we always return at least one category if we had any parameters
        # This prevents "No data to process" errors when all categories are filtered out
        if not transformed_categories and all_parameters:
            # Create an "Uncategorized" category with remaining parameters
            transformed_categories = [{
                'name': 'Uncategorized',
                'spanish_name': 'Sin categoría',
                'parameters': all_parameters
            }]
        
        return {
            'categories': transformed_categories,
            'dates': sorted_dates
        }
    
    def _is_valid_category(self, category_name):
        """Check if category name exists in REFERENCE_VALUES.md categories"""
        for cat in self.categories_config['categories']:
            if cat['name'] == category_name:
                return True
        return False
    
    def _get_category_from_config(self, spanish_name, fallback_category):
        """Get category from parameters.json config"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'parameters.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                parameters_config = json.load(f)
            
            if spanish_name in parameters_config:
                param_category = parameters_config[spanish_name].get('category', '')
                # If category is set and valid, use it
                if param_category and self._is_valid_category(param_category):
                    return param_category
                # If category is empty but we have a fallback, try to use it if valid
                elif not param_category and fallback_category and self._is_valid_category(fallback_category):
                    return fallback_category
        except Exception as e:
            pass
        
        # Return fallback if valid
        if fallback_category and self._is_valid_category(fallback_category):
            return fallback_category
        
        return ''
    
    def _get_category_info(self, category_name):
        """Get category information from config"""
        for cat in self.categories_config['categories']:
            if cat['name'] == category_name:
                return cat
        return {'spanish_name': '', 'explanation': ''}
    
    def _find_similar_category(self, category_name):
        """Find a similar category name if exact match not found"""
        if not category_name:
            return ''
        
        category_lower = category_name.lower()
        
        # Try to find partial matches (e.g., "Endocrinology" -> "Endocrinology - Thyroid Hormones")
        for cat in self.categories_config['categories']:
            cat_name_lower = cat['name'].lower()
            # If the category name contains the search term, use it
            if category_lower in cat_name_lower or cat_name_lower in category_lower:
                return cat['name']
        
        return ''
    
    def _sort_dates(self, date_strings):
        """Sort date strings chronologically"""
        def parse_date(date_str):
            """Parse date string in various formats"""
            date_str = str(date_str).strip()
            if not date_str or date_str == 'nan':
                return None
            
            # Handle dates with suffixes like "16/01/2026 - 1"
            base_date_str = date_str.split(' - ')[0].strip()
            
            # Try different date formats (including 2-digit years)
            formats = [
                '%d/%m/%Y',  # 21/12/2023
                '%d/%m/%y',  # 21/12/23
                '%d-%m-%Y',  # 21-12-2023
                '%d-%m-%y',  # 21-12-23
                '%d.%m.%Y',  # 21.12.2023
                '%d.%m.%y',  # 21.12.23
                '%Y-%m-%d',  # 2023-12-21
                '%m/%d/%Y',  # 12/21/2023
                '%m/%d/%y',  # 12/21/23
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(base_date_str, fmt)
                except:
                    continue
            
            return None
        
        # Parse and sort dates
        date_objects = []
        for date_str in date_strings:
            parsed = parse_date(date_str)
            if parsed:
                date_objects.append((date_str, parsed))
            else:
                # If can't parse, keep original order
                date_objects.append((date_str, None))
        
        # Sort by date object, then by original string for unparseable dates
        date_objects.sort(key=lambda x: (x[1] if x[1] else datetime.max, x[0]))
        
        return [date_str for date_str, _ in date_objects]
    
    def _transform_parameter(self, param, sorted_dates):
        """Transform a single parameter with values and calculations"""
        values = param['values']
        
        # Handle __SAMPLE_DATE__ placeholder from PDF parser
        if '__SAMPLE_DATE__' in values and sorted_dates:
            placeholder_value = values.pop('__SAMPLE_DATE__')
            # Use the first (and usually only) date for PDF data
            values[sorted_dates[0]] = placeholder_value
        
        # Extract values in chronological order
        ordered_values = []
        for date in sorted_dates:
            if date in values:
                ordered_values.append({
                    'date': date,
                    'value': values[date]
                })
            else:
                ordered_values.append({
                    'date': date,
                    'value': None
                })
        
        # Get reference range: first from param itself (PDF), then from stored ranges
        reference_range = param.get('reference_range', '')
        if not reference_range and self._reference_ranges:
            # Try to find by english_name or spanish_name
            english_name = param.get('english_name', '')
            spanish_name = param.get('spanish_name', '')
            reference_range = self._reference_ranges.get(english_name) or self._reference_ranges.get(spanish_name) or ''
        
        return {
            'english_name': param['english_name'],
            'spanish_name': param['spanish_name'],
            'category': param['category'],
            'unit': param['unit'],
            'explanation': param.get('explanation', ''),
            'values': ordered_values,
            'baseline_value': ordered_values[0]['value'] if ordered_values else None,
            'reference_range': reference_range  # From PDF source if available
        }
    
    def _try_float(self, value):
        """Try to convert value to float"""
        if value is None:
            return None
        try:
            # Remove common non-numeric characters
            cleaned = str(value).replace(',', '.').replace('<', '').replace('>', '').strip()
            return float(cleaned)
        except:
            return None

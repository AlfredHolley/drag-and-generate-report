import json
import os
import re
import unicodedata
from datetime import datetime
from typing import Optional, Dict, Any


class ReferenceLookup:
    """Lookup reference values based on patient metadata"""
    
    def __init__(self):
        self.reference_values = self._load_reference_values()
        self.parameters_config = self._load_parameters_config()
        self._parameter_name_mapping = self._build_parameter_mapping()
    
    def _load_reference_values(self) -> Dict[str, Any]:
        """Load reference values from JSON file"""
        config_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'reference_values.json'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_parameters_config(self) -> Dict[str, Any]:
        """Load parameters configuration to map Spanish to English names"""
        config_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'parameters.json'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _build_parameter_mapping(self) -> Dict[str, str]:
        """Build mapping from Spanish parameter names to English names used in reference_values"""
        mapping = {}
        for spanish_name, param_info in self.parameters_config.items():
            english_name = param_info.get('english_name', '')
            if english_name:
                # Normalize the English name for lookup
                normalized = self._normalize_parameter_name(english_name)
                mapping[spanish_name] = normalized
                # Also map the English name itself
                mapping[english_name] = normalized
        return mapping
    
    def _normalize_parameter_name(self, name: str) -> str:
        """Normalize parameter name for lookup in reference_values"""
        # Remove common prefixes/suffixes and normalize
        name = unicodedata.normalize("NFC", name.strip())
        
        # First, try to get English name from parameters.json if it's a Spanish name
        param_key = None
        if name in self.parameters_config:
            param_key = name
        else:
            # Fallback: match using Unicode-normalized keys (handles composed vs decomposed accents)
            for k in self.parameters_config.keys():
                if unicodedata.normalize("NFC", k) == name:
                    param_key = k
                    break

        if param_key is not None:
            english_name = self.parameters_config[param_key].get('english_name', '')
            if english_name and english_name != param_key:
                name = english_name
        
        # Common mappings for variations
        name_mappings = {
            "17 beta Estradiol": "17-Beta Estradiol",
            "17-Beta Estradiol": "17-Beta Estradiol",
            "17 beta Estradiol high‑sensitivity": "17-Beta Estradiol",
            "Hematíes": "Red Blood Cells",
            "Hemoglobina": "Hemoglobin",
            "Hemoglobin A1c": "HbA1c",
            "Hemoglobina A1c (NGSP) por HPLC": "HbA1c",
            "Hemoglobin A1c (IFCC) (HPLC)": "HbA1c (IFCC)",
            "Hemoglobina A1c (IFCC) por HPLC": "HbA1c (IFCC)",
            "Hematocrito": "Hematocrit",
            "Leucocitos": "White Blood Cells",
            "Hematíes en orina": "Urine Red Blood Cells",
            "Urine Red Blood Cells": "Urine Red Blood Cells",
            "Leucocitos en orina": "Urine White Blood Cells",
            "Urine White Blood Cells": "Urine White Blood Cells",
            "Neutrófilos": "Neutrophils",  # Absolute count
            "Neutrófilos %": "Neutrophils %",  # Percentage
            "Linfocitos": "Lymphocytes",  # Absolute count
            "Linfocitos %": "Lymphocytes %",  # Percentage
            "Monocitos": "Monocytes",  # Absolute count
            "Monocitos %": "Monocytes %",  # Percentage
            "LUC": "Large Unstained Cells",  # Absolute count
            "LUC %": "Large Unstained Cells (%)",  # Percentage
            "Plaquetas": "Platelets",
            "Glucosa": "Glucose",
            "Glucosa (suero/plasma)": "Glucose",
            "Colesterol total": "Total Cholesterol",
            "Colesterol HDL": "HDL Cholesterol",
            "Colesterol LDL": "LDL Cholesterol",
            "Triglicéridos": "Triglycerides",
            "Proteínas totales": "Total Proteins",
            "Albumina": "Albumin",
            "CRP": "CRP",
            "CRP ultrasensible": "High-sensitivity CRP",
            "Proteína C Reactiva": "CRP",
            "Proteína C Reactiva en suero (Ultrasensible)": "High-sensitivity CRP",
            "C-Reactive Protein": "CRP",
            "Ácido úrico": "Uric Acid",
            "Urato": "Uric Acid",
            "Urate": "Uric Acid",
            "Creatinina": "Creatinine",
            "Urea": "Urea",
            "Sodio": "Sodium",
            "Potasio": "Potassium",
            "Cloruros": "Chlorides",
            "Magnesio": "Magnesium",
            "Bilirrubina total": "Total Bilirubin",
            "Bilirrubina directa": "Direct Bilirubin",
            "GPT": "ALT",
            "ALT": "ALT",
            "GOT": "AST",
            "AST": "AST",
            "Gamma-GT": "Gamma-GT",
            "Gamma-glutamil transferasa (GGT)": "Gamma-GT",
            "Gamma-Glutamyl Transferase (GGT)": "Gamma-GT",
            "Fosfatasa alcalina": "Alkaline Phosphatase",
            "Hierro": "Iron",
            "Ferritina": "Ferritin",
            "Fósforo": "Phosphorus",
            "Calcio": "Calcium",
            "Calcio ionizado": "Ionized Calcium",
            "Calcio iónico": "Ionized Calcium",
            "Ionized Calcium": "Ionized Calcium",
            "TSH": "TSH",
            "Thyroid Stimulating Hormone": "TSH",
            # T4 and T3 are total forms, not free forms - no references available
            # Map them to None to prevent fuzzy matching
            "T4": None,  # Total T4 - no references available
            "T3": None,  # Total T3 - no references available
            # Only map free forms and other specific forms
            "T4L": "Free T4",
            "T4 libre": "Free T4",
            "Free Thyroxine (FT4)": "Free T4",
            "Free Thyroxine": "Free T4",
            "FT4": "Free T4",
            "T3L": "Free T3",
            "T3 libre": "Free T3",
            "Free Triiodothyronine (FT3)": "Free T3",
            "Free Triiodothyronine": "Free T3",
            "FT3": "Free T3",
            "T3 reversa": "Reverse T3 (adults)",
            "Testosterona total": "Total Testosterone",
            "Testosterona libre estimada": "Estimated Free Testosterone",
            "Testosterona biodisponible": "Bioavailable Testosterone",
            "% Testosterona libre": "% Free Testosterone",
            "Cortisol basal": "Basal Cortisol",
            "DHEA-S": "DHEA-S (35-44 years)",
            "LH": "LH",
            "FSH": "FSH",
            "Prolactina": "Prolactin",
            "SHBG": "SHBG",
            "SHBG (Globulina fijadora hormonas sexuales)": "SHBG",
            "ACTH": "ACTH",
            "IGF-1": "Somatomedin C (IGF-1, 30-39 years)",
            "Somatomedina C": "Somatomedin C (IGF-1, 30-39 years)",
            "Insulina basal": "Basal Insulin",
            "Índice HOMA": "HOMA Index",
            "Péptido C": "C-Peptide",
            "PTH intacta": "Intact PTH",
            "Osteocalcina": "Osteocalcin",
            "Adiponectina": "Adiponectin (BMI < 25)",
            "Vitamina D": "Vitamin D (25-OH)",
            "Vitamina B12": "Vitamin B12",
            "Ácido Fólico (Vitamina B9)": "Folic Acid",
            "Folic Acid (Vitamin B9)": "Folic Acid",
            "Ácido fólico eritrocitario": "Erythrocyte Folic Acid",
            "Acido folico eritrocitario": "Erythrocyte Folic Acid",
            "�cido f�lico eritrocitario": "Erythrocyte Folic Acid",  # mojibake safety net
            "Erythrocyte Folic Acid": "Erythrocyte Folic Acid",
            "PSA": "PSA",
            "Homocisteína": "Homocysteine",
            "Inmunoglobulina IgA": "Immunoglobulin IgA",
            "Inmunoglobulina IgE": "Immunoglobulin IgE",
            "Inmunoglobulina A (IgA)": "Immunoglobulin IgA",
            "IgE (ABBOTT)": "Immunoglobulin IgE",
            "Ac anti-tiroglobulina": "Anti-thyroglobulin Antibodies",
            "Ac anti-TPO": "Anti-TPO Antibodies (microsomal)",
            "Ac gliadina desaminada IgA": "Deamidated Gliadin Antibodies IgA",
            "Ac gliadina desaminada IgG": "Deamidated Gliadin Antibodies IgG",
            "Ac transglutaminasa IgA": "Transglutaminase Antibodies IgA",
            "Ac transglutaminasa IgG": "Transglutaminase Antibodies IgG",
            "TNF alfa": "TNF alpha",
            "TNF alfa (Factor de necrosis tumoral) (DESCATALOGADO TEMPORALMENTE)": "TNF alpha",
            "Interleucina 6": "Interleukin 6",
            "Interleuquina 6": "Interleukin 6",
            "Interleuquina 2": "Interleukin 2",
            "Interleuquina 10": "Interleukin 10",
            "Índice Omega 3": "Omega 3 Index (W3)",
            "VCM": "MCV",
            "HCM": "MCH",
            "CHCM": "MCHC",
            "RDW": "RDW",
            "VSG": "ESR (1st hour)",
            "Fibrinógeno": "Fibrinogen",
            "Volumen plaquetario medio": "Mean Platelet Volume",
            "VPM": "Mean Platelet Volume",

            # Autoantibodies / lab-specific variants
            "Ac Tiroglobulina (ABBOTT)": "Anti-thyroglobulin Antibodies",
            "Ac Peroxidasa (TPO)/Microsomales (ABBOTT)": "Anti-TPO Antibodies (microsomal)",
            "Ac gliadina deaminada IgA": "Deamidated Gliadin Antibodies IgA",
            "Ac gliadina deaminada IgG": "Deamidated Gliadin Antibodies IgG",
            "Ac Transglutaminasa IgA": "Transglutaminase Antibodies IgA",
            "Ac Transglutaminasa IgG": "Transglutaminase Antibodies IgG",
            "Antibody Tiroglobulina (ABBOTT)": "Anti-thyroglobulin Antibodies",
            "Antibody Peroxidasa (TPO)/Microsomales (ABBOTT)": "Anti-TPO Antibodies (microsomal)",
            "Antibody gliadina deaminada IgA": "Deamidated Gliadin Antibodies IgA",
            "Antibody gliadina deaminada IgG": "Deamidated Gliadin Antibodies IgG",
            "Antibody Transglutaminasa IgA": "Transglutaminase Antibodies IgA",
            "Antibody Transglutaminasa IgG": "Transglutaminase Antibodies IgG",
        }
        
        # Check direct mapping first
        if name in name_mappings:
            mapped = name_mappings[name]
            # If mapped to None, return None (no reference available)
            if mapped is None:
                return None
            return mapped
        
        # Try to find in reference_values by exact match first
        name_lower = name.lower()
        exact_match = None
        partial_matches = []
        
        for ref_name in self.reference_values.keys():
            ref_name_lower = ref_name.lower()
            # Exact match - return immediately
            if name_lower == ref_name_lower:
                return ref_name
            
            # Try partial match (check if key parts match)
            # Remove common words and compare
            name_words = set(name_lower.replace('(', ' ').replace(')', ' ').replace('-', ' ').split())
            ref_words = set(ref_name_lower.replace('(', ' ').replace(')', ' ').replace('-', ' ').split())
            # Remove common stop words
            stop_words = {'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'a', 'an', 'and'}
            name_words -= stop_words
            ref_words -= stop_words
            # If significant overlap, add to partial matches
            if name_words and ref_words and len(name_words & ref_words) >= min(2, len(name_words), len(ref_words)):
                # Prefer longer/more specific matches (e.g., "Ionized Calcium" over "Calcium")
                partial_matches.append((ref_name, len(ref_words), len(name_words & ref_words)))
        
        # If we have partial matches, prefer the one with more words (more specific)
        if partial_matches:
            # Sort by: 1) number of matching words (desc), 2) total words in ref_name (desc)
            partial_matches.sort(key=lambda x: (x[2], x[1]), reverse=True)
            return partial_matches[0][0]
        
        # Return original name if no mapping found
        return name
    
    def _calculate_age(self, birthdate: str) -> Optional[int]:
        """Calculate age from birthdate string (YYYY-MM-DD format)"""
        try:
            birth = datetime.strptime(birthdate, '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birth.year
            if today.month < birth.month or (today.month == birth.month and today.day < birth.day):
                age -= 1
            return age
        except (ValueError, TypeError):
            return None
    
    def _get_age_range_key(self, age: Optional[int]) -> Optional[str]:
        """Get age range key for age-dependent parameters"""
        if age is None:
            return None
        
        # Map age to range keys used in reference_values.json
        if 30 <= age <= 39:
            return "30_39"
        if 35 <= age <= 44:
            return "35_44"
        if 40 <= age <= 49:
            return "40_49"
        if 50 <= age <= 59:
            return "50_59"
        if 60 <= age <= 69:
            return "60_69"
        if 70 <= age <= 79:
            return "70_79"
        return None
    
    def _is_post_menopause(self, sex: str, age: Optional[int], menstrual_phase: Optional[str]) -> bool:
        """Determine if patient is post-menopause"""
        if sex != 'F':
            return False
        
        if menstrual_phase == 'post_menopause':
            return True
        
        # Assume post-menopause if age > 50 and no specific phase given
        if age and age > 50 and menstrual_phase is None:
            return True
        
        return False
    
    def _extract_numeric_range(self, range_str: str) -> str:
        """Extract only numeric range from reference string, removing units and text"""
        if not range_str:
            return ""
        
        # Remove common unit patterns and text
        # Keep only numbers, operators (<, >, -), commas, and decimal points
        
        # First, remove text labels like "Follicular:", "Ovulatory:", etc. but keep the values
        range_str = re.sub(r'[A-Za-z\s\-]+:\s*', '', range_str)  # Remove "Follicular: ", "Post-menopause: ", etc.
        
        # Remove all unit patterns (comprehensive list)
        # Remove x10 patterns
        range_str = re.sub(r'\s*x10[⁶³²¹⁰]', '', range_str)
        
        # Remove unit patterns with slashes (mg/dL, U/L, etc.)
        range_str = re.sub(r'\s*/\s*(mm³|mm|L|dL|mL|µL|nl|pg|ng|µg|mg|g|mol|mmol|µmol|pmol|IU|UI|U|mIU|mUI|mU|nmol|fL|%)', '', range_str, flags=re.IGNORECASE)
        
        # Remove standalone unit words (mg, g, L, etc.) that might remain
        range_str = re.sub(r'\b(mg/dL|g/dL|mg/L|g/L|µg/dL|ng/mL|pg/mL|µmol/L|mmol/L|pmol/L|nmol/L|IU/mL|UI/mL|U/mL|mIU/mL|mUI/mL|mU/L|fL|mm|%|mg|g|L|dL|mL|µL|pg|ng|µg|mol|mmol|µmol|pmol|IU|UI|U|mIU|mUI|mU|nmol)\b', '', range_str, flags=re.IGNORECASE)
        
        # Remove any remaining text words (but keep numbers, operators, commas, spaces, dashes)
        # Keep: numbers, decimal points, operators (<, >, =), dashes, commas, spaces
        range_str = re.sub(r'[^\d\s\.,\-\<\>\(\)]', '', range_str)
        
        # Remove empty parentheses and their contents
        range_str = re.sub(r'\(\s*\)', '', range_str)  # Remove empty parentheses
        range_str = re.sub(r'\(\s*[^\d\s\.,\-\<\>]*\s*\)', '', range_str)  # Remove parentheses with only non-numeric content
        
        # Clean up extra spaces and normalize
        range_str = ' '.join(range_str.split())
        # Remove spaces around dashes
        range_str = re.sub(r'\s*-\s*', ' - ', range_str)
        # Remove spaces around commas
        range_str = re.sub(r'\s*,\s*', ', ', range_str)
        
        return range_str.strip()
    
    def get_reference_range(
        self,
        parameter_name: str,
        sex: str = 'M',
        birthdate: Optional[str] = None,
        age: Optional[int] = None,
        menstrual_phase: Optional[str] = None,
        bmi: Optional[float] = None
    ) -> Optional[str]:
        """
        Get reference range for a parameter based on patient metadata
        
        Args:
            parameter_name: Parameter name (Spanish or English)
            sex: 'M' for male, 'F' for female
            birthdate: Birthdate in YYYY-MM-DD format
            age: Age in years (calculated from birthdate if not provided)
            menstrual_phase: 'follicular', 'ovulatory', 'luteal', 'post_menopause' (for females)
            bmi: Body Mass Index (for BMI-dependent parameters)
        
        Returns:
            Numeric reference range string (without units or text) or None if not found
        """
        # Calculate age if birthdate provided
        if age is None and birthdate:
            age = self._calculate_age(birthdate)
        
        # Normalize parameter name
        normalized_name = self._normalize_parameter_name(parameter_name)
        
        # Look up in reference_values
        ref_data = self.reference_values.get(normalized_name)
        if not ref_data:
            return None
        
        # Handle different reference value structures
        if isinstance(ref_data, dict):
            # Check for age-dependent parameters
            if ref_data.get('age_dependent'):
                age_key = self._get_age_range_key(age)
                if age_key and age_key in ref_data:
                    age_data = ref_data[age_key]
                    if isinstance(age_data, dict):
                        range_str = age_data.get(sex.lower(), age_data.get('male' if sex == 'M' else 'female'))
                        if range_str:
                            return self._extract_numeric_range(str(range_str))
                return None
            
            # Check for BMI-dependent parameters
            if ref_data.get('bmi_dependent'):
                if bmi and bmi < 25:
                    bmi_data = ref_data.get('bmi_lt_25', {})
                    if isinstance(bmi_data, dict):
                        range_str = bmi_data.get(sex.lower(), bmi_data.get('male' if sex == 'M' else 'female'))
                        if range_str:
                            return self._extract_numeric_range(str(range_str))
                return None
            
            # Handle female-specific structures (menstrual cycle phases)
            if sex == 'F' and 'female' in ref_data:
                female_data = ref_data['female']
                
                if isinstance(female_data, dict):
                    # Multiple phases available - show all phases with numeric values only
                    phases = []
                    if 'follicular' in female_data:
                        phases.append(self._extract_numeric_range(str(female_data['follicular'])))
                    if 'ovulatory' in female_data:
                        phases.append(self._extract_numeric_range(str(female_data['ovulatory'])))
                    if 'luteal' in female_data:
                        phases.append(self._extract_numeric_range(str(female_data['luteal'])))
                    if 'post_menopause' in female_data:
                        phases.append(self._extract_numeric_range(str(female_data['post_menopause'])))
                    if 'pre_menopause' in female_data:
                        phases.append(self._extract_numeric_range(str(female_data['pre_menopause'])))
                    
                    # Filter out empty phases and join
                    phases = [p for p in phases if p]
                    if phases:
                        return ', '.join(phases)
                else:
                    # Simple string range for females
                    return self._extract_numeric_range(str(female_data))
            
            # Handle male or simple ranges
            sex_key = 'male' if sex == 'M' else 'female'
            range_str = ref_data.get(sex_key)
            
            if range_str:
                if isinstance(range_str, str):
                    return self._extract_numeric_range(range_str)
        
        return None

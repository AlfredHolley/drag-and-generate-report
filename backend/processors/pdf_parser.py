"""
PDF Parser for Eurofins lab reports.
Extracts patient metadata, test results, units, and reference ranges from PDF files.
"""

import pdfplumber
import re
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from processors.value_translator import translate_value

logger = logging.getLogger(__name__)


class PDFParser:
    """Parse Eurofins PDF lab reports and extract structured data"""
    
    def __init__(self):
        self.categories_config = self._load_categories_config()
        self.parameters_config = self._load_parameters_config()
        
        # Category mapping from PDF section headers to standard categories (from categories.json)
        self.category_mapping = {
            # Hematology
            'haematology': 'Hematology and Hemostasis',
            'haemostasis': 'Hematology and Hemostasis',
            'hematology': 'Hematology and Hemostasis',
            'red series': 'Hematology and Hemostasis',
            'white series': 'Hematology and Hemostasis',
            'platelet series': 'Hematology and Hemostasis',
            'erythrocyte sedimentation': 'Hematology and Hemostasis',
            # Carbohydrate metabolism
            'hydrocarbon metabolism': 'Carbohydrate Metabolism',
            'carbohydrate metabolism': 'Carbohydrate Metabolism',
            'glucose': 'Carbohydrate Metabolism',
            # Lipid metabolism
            'lipid metabolism': 'Lipid Metabolism',
            'lipid': 'Lipid Metabolism',
            'cholesterol': 'Lipid Metabolism',
            # Proteins
            'proteins': 'Biochemistry (serum / plasma) - Proteins',
            'protein': 'Biochemistry (serum / plasma) - Proteins',
            # Renal function
            'renal function': 'Biochemistry (serum / plasma) - Renal Function',
            'renal': 'Biochemistry (serum / plasma) - Renal Function',
            'kidney': 'Biochemistry (serum / plasma) - Renal Function',
            # Liver
            'hepatic markers': 'Biochemistry (serum / plasma) - Liver Function',
            'liver': 'Biochemistry (serum / plasma) - Liver Function',
            'hepatic': 'Biochemistry (serum / plasma) - Liver Function',
            'liver function': 'Biochemistry (serum / plasma) - Liver Function',
            'liver function tests': 'Biochemistry (serum / plasma) - Liver Function',
            # Iron
            'iron metabolism': 'Iron Metabolism',
            'iron': 'Iron Metabolism',
            # Ions
            'ions': 'Ions',
            'electrolytes': 'Ions',
            # Phosphocalcic
            'mineral metabolism': 'Phosphocalcic Metabolism',
            'phosphocalcic': 'Phosphocalcic Metabolism',
            'calcium': 'Phosphocalcic Metabolism',
            # Endocrinology
            'endocrinology': 'Endocrinology - Pituitary Hormones',
            'thyroid': 'Endocrinology - Thyroid Hormones',
            'thyroid hormones': 'Endocrinology - Thyroid Hormones',
            'pituitary': 'Endocrinology - Pituitary Hormones',
            'pituitary hormones': 'Endocrinology - Pituitary Hormones',
            'adrenal': 'Endocrinology - Adrenal Hormones',
            'adrenal hormones': 'Endocrinology - Adrenal Hormones',
            'sex hormones': 'Endocrinology - Sex Hormones',
            # Immunology
            'immunology': 'Immunology',
            'immune': 'Immunology',
            # Serology
            'serology': 'Serology',
            # Tumor markers
            'tumor markers': 'Tumor Markers',
            'tumour markers': 'Tumor Markers',
            'tumor': 'Tumor Markers',
            # Urine
            'urine': 'Urine Analysis',
            'urine testing': 'Urine Analysis',
            'urinalysis': 'Urine Analysis',
            # Drug monitoring / Toxicology
            'drug monitoring': 'Drug Monitoring and Toxicology',
            'toxicology': 'Drug Monitoring and Toxicology',
            # Vitamins
            'vitamins': 'Vitamins',
            'vitamin': 'Vitamins',
            # Preventive medicine
            'fatty acids': 'Personalized Preventive Medicine Profile',
            'preventive medicine': 'Preventive Medicine',
            # Biochemistry - general fallback
            'biochemistry': 'Proteins',  # Default to Proteins as general biochemistry
        }
    
    def _load_categories_config(self) -> Dict:
        """Load categories configuration"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'categories.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load categories config: {e}")
            return {'categories': []}
    
    def _load_parameters_config(self) -> Dict:
        """Load parameters configuration"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'parameters.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load parameters config: {e}")
            return {}
    
    def parse(self, filepath: str) -> Dict[str, Any]:
        """
        Parse PDF file and extract structured data.
        
        Returns:
            {
                'categories': [...],
                'date_columns': ['dd/mm/yyyy'],
                'metadata': {
                    'patient_name': str,
                    'sex': str ('M' or 'F'),
                    'birthdate': str (YYYY-MM-DD format),
                    'sample_id': str,
                    'sample_date': str,
                    'source': str
                },
                'reference_ranges': {param_name: range_str, ...}
            }
        """
        logger.info(f"Parsing PDF: {filepath}")
        
        with pdfplumber.open(filepath) as pdf:
            # Extract all text from all pages
            all_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
            
            full_text = '\n'.join(all_text)
        
        # Extract metadata from header
        metadata = self._extract_metadata(full_text)
        
        # Extract results with reference ranges
        categories, reference_ranges = self._extract_results(full_text)
        
        # Get the sample date for date_columns
        sample_date = metadata.get('sample_date', '')
        date_columns = [sample_date] if sample_date else []
        
        return {
            'categories': categories,
            'date_columns': date_columns,
            'metadata': metadata,
            'reference_ranges': reference_ranges
        }
    
    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """Extract patient metadata from PDF header"""
        metadata = {
            'patient_name': '',
            'sex': '',
            'birthdate': '',
            'sample_id': '',
            'sample_date': '',
            'source': '',
            'reception_date': '',
            'validation_date': '',
            'print_date': ''
        }
        
        # Extract patient name - format: "Patient: NAME Sample:" or "Nombre: NAME"
        patient_match = re.search(r'(?:Patient|Nombre):\s*([^S\n|]+?)(?:\s+Sample:|N[°º]|$)', text, re.IGNORECASE)
        if patient_match:
            name = patient_match.group(1).strip()
            # Clean up name (remove dots, normalize spaces)
            name = re.sub(r'\s*\.\s*', ' ', name).strip()
            name = re.sub(r'\s+', ' ', name)
            # Remove trailing comma or extra characters
            name = re.sub(r',+\s*$', '', name).strip()
            # Remove "MOUFAREK: ., MAYA" artifacts
            name = re.sub(r':\s*\.\s*,', '', name).strip()
            if name:
                metadata['patient_name'] = name
        
        # Extract sample ID and date - format: "Sample: V7169911 - 16/01/2026" or "N° Laboratorio: V7169919 - 17/01/2026"
        sample_match = re.search(r'(?:Sample|N[°º]\s*Laboratorio):\s*([A-Z0-9]+)\s*[-–]\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if sample_match:
            metadata['sample_id'] = sample_match.group(1).strip()
            metadata['sample_date'] = sample_match.group(2).strip()
        
        # Extract sex - format: "Sex: HOMBRE" or "Sex: MUJER" or "Sexo: MUJER"
        sex_match = re.search(r'(?:Sex|Sexo):\s*(HOMBRE|MUJER|Male|Female|M|F)', text, re.IGNORECASE)
        if sex_match:
            sex_raw = sex_match.group(1).upper()
            if sex_raw in ['HOMBRE', 'MALE', 'M']:
                metadata['sex'] = 'M'
            elif sex_raw in ['MUJER', 'FEMALE', 'F']:
                metadata['sex'] = 'F'
        
        # Extract birth date - format: "Birth date.: 09/12/1972"
        birth_match = re.search(r'Birth\s*date\.?:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if birth_match:
            # Convert DD/MM/YYYY to YYYY-MM-DD for consistency
            date_str = birth_match.group(1)
            try:
                dt = datetime.strptime(date_str, '%d/%m/%Y')
                metadata['birthdate'] = dt.strftime('%Y-%m-%d')
            except ValueError:
                metadata['birthdate'] = date_str
        
        # Extract source/entity
        source_match = re.search(r'Source:\s*(.+?)(?:\n|Entity:|$)', text, re.IGNORECASE)
        if source_match:
            metadata['source'] = source_match.group(1).strip()
        
        # Extract reception date
        reception_match = re.search(r'Reception\s*date:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if reception_match:
            metadata['reception_date'] = reception_match.group(1)
        
        # Extract validation date
        validation_match = re.search(r'Validation\s*date:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        if validation_match:
            metadata['validation_date'] = validation_match.group(1)
        
        logger.info(f"Extracted metadata: {metadata}")
        return metadata
    
    def _extract_results(self, text: str) -> Tuple[List[Dict], Dict[str, str]]:
        """
        Extract test results from PDF text.
        
        Returns:
            (categories_list, reference_ranges_dict)
        """
        categories = []
        reference_ranges = {}
        current_category_name = 'General'
        current_category = None
        last_parameter = None  # Track last parameter to attach notes/explanations
        current_notes = []  # Collect notes for current parameter
        skip_children_section = False  # Flag to skip children reference sections
        explicit_category_detected = False  # Track if a real category was detected in the PDF
        
        # Process line by line
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip footer/header lines
            if self._is_skip_line(line):
                continue
            
            # Check if we're entering a children section (Niños, Niñas, Children, Boys, Girls)
            if re.match(r'^(Niños|Niñas|Children|Boys|Girls):', line, re.IGNORECASE):
                skip_children_section = True
                continue  # Skip the header line
            
            # Check if we're leaving children section (next section header or parameter)
            if skip_children_section:
                # Check if this is a new section (Hombres, Mujeres, or a parameter result)
                if re.match(r'^(Hombres|Mujeres|Men|Women)', line, re.IGNORECASE):
                    skip_children_section = False
                elif self._parse_result_line(line) is not None:
                    skip_children_section = False
                elif self._detect_category(line):
                    skip_children_section = False
                else:
                    # Still in children section, skip this line
                    continue
            
            # Check if this is a note/explanation line (before checking category/result)
            if self._is_note_line(line):
                # Skip lines with age ranges for children (6-9 años, 10-11 años, 12-14 años)
                if re.match(r'^(6|7|8|9|10|11|12|13|14)\s*-\s*(6|7|8|9|10|11|12|13|14)\s*(años|years|ans)', line, re.IGNORECASE):
                    continue  # Skip children age ranges
                
                # Extract reference value from "Normal value: XXX" lines and set on parameter
                normal_value_match = re.match(r'^(Normal\s+value|Valor\s+normal)\s*:\s*(.+)$', line, re.IGNORECASE)
                if normal_value_match and last_parameter is not None:
                    ref_value = normal_value_match.group(2).strip()
                    # Translate the reference value
                    ref_value = translate_value(ref_value)
                    # Set as reference if not already set
                    if not last_parameter.get('reference_range'):
                        last_parameter['reference_range'] = ref_value
                    # Don't add this line to notes
                    continue
                
                # Add to current notes if we have a last parameter
                if last_parameter is not None:
                    current_notes.append(line)
                continue
            
            # Check if this is a Hematology subsection (Red series, White series, etc.)
            hematology_subsection = None
            line_lower = line.lower()
            if 'red series' in line_lower or line.strip() == 'Red series':
                hematology_subsection = 'Hematology and Hemostasis - Red series'
            elif 'white series' in line_lower or line.strip() == 'White series':
                hematology_subsection = 'Hematology and Hemostasis - White series'
            elif 'platelet series' in line_lower or line.strip() == 'Platelet series':
                hematology_subsection = 'Hematology and Hemostasis - Platelet series'
            elif 'erythrocyte sedimentation' in line_lower:
                # Only treat as subsection header if it's NOT a result line (no numbers/brackets)
                if not re.search(r'\d+\s*(mm|%|g|mg|µ|mcg|ng|mL|L|U|IU|\[)', line):
                    hematology_subsection = 'Hematology and Hemostasis - Erythrocyte sedimentation'
            
            if hematology_subsection:
                # Save notes to last parameter before switching categories
                if last_parameter is not None and current_notes:
                    last_parameter['explanation'] = self._join_note_lines(current_notes)
                    current_notes = []
                
                # Save previous category if it has parameters AND is not already in categories
                if current_category and current_category['parameters']:
                    if current_category not in categories:
                        categories.append(current_category)
                
                current_category_name = hematology_subsection
                current_category = {
                    'name': hematology_subsection,
                    'spanish_name': '',
                    'parameters': []
                }
                explicit_category_detected = True  # Mark that a real category was detected
                last_parameter = None  # Reset when category changes
                continue
            
            # Check if this is a category/section header
            category = self._detect_category(line)
            if category:
                # Save notes to last parameter before switching categories
                if last_parameter is not None and current_notes:
                    last_parameter['explanation'] = self._join_note_lines(current_notes)
                    current_notes = []
                
                # Save previous category if it has parameters AND is not already in categories
                if current_category and current_category['parameters']:
                    if current_category not in categories:
                        categories.append(current_category)
                
                current_category_name = category
                current_category = {
                    'name': category,
                    'spanish_name': '',
                    'parameters': []
                }
                explicit_category_detected = True  # Mark that a real category was detected
                last_parameter = None  # Reset when category changes
                continue
            
            # Special handling for URINE MICROSCOPE EXAM - capture multi-line text
            # Check if we're currently collecting text for URINE MICROSCOPE EXAM
            if last_parameter and 'URINE MICROSCOPE' in last_parameter.get('english_name', '').upper():
                # Check if this line looks like continuation text (not a new parameter, category, or note)
                is_new_param = self._parse_result_line(line) is not None
                is_new_category = self._detect_category(line) is not None
                is_note = self._is_note_line(line)
                is_skip = self._is_skip_line(line)
                
                # Check if this is footer text that should stop collection
                line_upper = line.upper().strip()
                is_footer = (
                    'INFORME VALIDADO' in line_upper or
                    'VALIDADO POR' in line_upper or
                    (line_upper.startswith('POR ') and bool(re.match(r'^POR\s+[A-Z]{2,4}(,\s*[A-Z]{2,4}){2,}', line_upper))) or  # "POR MGG, HVA, JMG"
                    'DIRECCIÓN DE LABORATORIO' in line_upper or
                    'DIRECCION DE LABORATORIO' in line_upper or
                    'DIRECCIÓN DE LABORATORIO:' in line_upper or
                    'DIRECCION DE LABORATORIO:' in line_upper or
                    'LAS PRUEBAS SEÑALIZADAS' in line_upper or
                    'LAS PRUEBAS SEÑALIZADAS CON' in line_upper or
                    'HAN SIDO REALIZADAS EN UN LABORATORIO EXTERNO' in line_upper or
                    'POLÍGONO INDUSTRIAL' in line_upper or
                    'POLIGONO INDUSTRIAL' in line_upper or
                    'ALHAURÍN' in line_upper or
                    'ALHAURIN' in line_upper or
                    'MÁLAGA' in line_upper or
                    'MALAGA' in line_upper or
                    bool(re.match(r'^[A-Z]{2,4}(,\s*[A-Z]{2,4}){3,}', line_upper)) or  # Pattern like "MGG, HVA, JMG, ERS"
                    bool(re.match(r'^AVDA\.', line_upper)) or  # "Avda. de las Américas"
                    bool(re.match(r'^AVDA\s', line_upper)) or  # "Avda de las Américas"
                    'AVENIDA' in line_upper or
                    bool(re.match(r'^\d{5}\s', line))  # Postal code like "29130"
                )
                
                # If this is footer text, stop collecting immediately
                if is_footer:
                    # Stop collecting - we've reached the footer
                    # Reset last_parameter so we don't continue collecting
                    last_parameter = None
                    continue
                
                # If this is continuation text (not a new param/category/note/footer), append to value
                if not is_new_param and not is_new_category and not is_note and not is_skip:
                    # Append this line to the last parameter's value
                    # The values structure is {'__SAMPLE_DATE__': value_string}
                    if '__SAMPLE_DATE__' in last_parameter.get('values', {}):
                        current_value = last_parameter['values']['__SAMPLE_DATE__']
                        last_parameter['values']['__SAMPLE_DATE__'] = current_value + ' ' + line.strip()
                    continue
            
            # Try to parse as a result line
            result = self._parse_result_line(line)
            if result:
                # Save notes to previous parameter before starting new one
                if last_parameter is not None and current_notes:
                    last_parameter['explanation'] = self._join_note_lines(current_notes)
                    current_notes = []
                
                param_name = result['name']
                english_name = result['english_name']
                
                # Force specific parameters to correct category regardless of PDF section
                # CORTISOL and DEHYDROEPIANDROSTERONE-S should be in Adrenal Hormones
                forced_category = None
                param_name_upper = english_name.upper() if english_name else ''
                spanish_name_upper = param_name.upper() if param_name else ''
                
                if ('CORTISOL' in param_name_upper or 'CORTISOL' in spanish_name_upper or 
                    'HYDROCORTISONE' in param_name_upper or 'HYDROCORTISONE' in spanish_name_upper):
                    forced_category = 'Endocrinology - Adrenal Hormones'
                elif ('DEHYDROEPIANDROSTERONE-S' in param_name_upper or 'DHEA-S' in param_name_upper or
                      'DEHYDROEPIANDROSTERONE-S' in spanish_name_upper or 'DHEA-S' in spanish_name_upper):
                    forced_category = 'Endocrinology - Adrenal Hormones'
                # DHEA (DHYDROEPIANDROSTERONE) without -S suffix -> Sex Hormones
                elif (('DHEA' in param_name_upper or 'DHYDROEPIANDROSTERONE' in param_name_upper or
                       'DHEA' in spanish_name_upper or 'DHYDROEPIANDROSTERONE' in spanish_name_upper) and
                      '-S' not in param_name_upper and '-S' not in spanish_name_upper):
                    forced_category = 'Endocrinology - Sex Hormones'
                # Androstenedione delta 4 -> Sex Hormones
                elif ('ANDROSTENEDIONE' in param_name_upper or 'ANDROSTENEDIONA' in spanish_name_upper or
                      'DELTA 4' in param_name_upper or 'DELTA-4' in param_name_upper):
                    forced_category = 'Endocrinology - Sex Hormones'
                # TESTOSTERONE and related parameters -> Sex Hormones
                elif ('TESTOSTERONE' in param_name_upper or 'TESTOSTERONA' in spanish_name_upper or
                      'FREE TESTOSTERONE' in param_name_upper or 'BIOAVAILABLE TESTOSTERONE' in param_name_upper or
                      'ESTIMATED FREE TESTOSTERONE' in param_name_upper):
                    forced_category = 'Endocrinology - Sex Hormones'
                # Force Proteins category parameters
                elif ('PREALBUMIN' in param_name_upper or 'PREALBÚMINA' in spanish_name_upper or
                      'ALBUMIN' in param_name_upper or 'ALBÚMINA' in spanish_name_upper or
                      ('CRP' in param_name_upper and 'C-REACTIVE' in param_name_upper) or
                      'C-REACTIVE PROTEIN' in param_name_upper):
                    forced_category = 'Biochemistry (serum / plasma) - Proteins'
                # Force Renal Function category parameters
                elif ('URIC ACID' in param_name_upper or 'ÁCIDO ÚRICO' in spanish_name_upper or
                      'CREATININE' in param_name_upper or 'CREATININA' in spanish_name_upper or
                      'UREA' in param_name_upper or 'UREA' in spanish_name_upper or
                      'FILTRADO GLOMERULAR' in param_name_upper or 'FILTRADO GLOMERULAR' in spanish_name_upper or
                      'CKD-EPI' in param_name_upper or 'CKD-EPI' in spanish_name_upper or
                      'GFR' in param_name_upper and 'ESTIMATED' in param_name_upper):
                    forced_category = 'Biochemistry (serum / plasma) - Renal Function'
                # Force Liver Function category parameters
                elif ('BILIRRUBIN' in param_name_upper or 'BILIRRUBINA' in spanish_name_upper or
                      'GPT' in param_name_upper or 'ALT' in param_name_upper or
                      'GOT' in param_name_upper or 'AST' in param_name_upper or
                      'GAMMA-GT' in param_name_upper or 'GAMMA GT' in param_name_upper or
                      'ALKALINE PHOSPHATE' in param_name_upper or 'FOSFATASA ALCALINA' in spanish_name_upper):
                    forced_category = 'Biochemistry (serum / plasma) - Liver Function'
                # Force Urine testing - Chemical and urine sediment analysis
                # Check if unit indicates urine sample (µL, /µL)
                result_unit = result.get('unit', '').upper()
                is_urine_unit = 'µL' in result.get('unit', '') or 'UL' in result_unit
                # Check if parameter name is exactly "pH" or "DENSITY" or "SPECIFIC GRAVITY" (short urine parameters)
                is_ph = param_name_upper == 'PH' or spanish_name_upper == 'PH'
                is_density = (param_name_upper == 'DENSITY' or spanish_name_upper == 'DENSIDAD' or 
                             'URINE DENSITY' in param_name_upper or 'SPECIFIC GRAVITY' in param_name_upper or
                             'DENSIDAD ESPECÍFICA' in spanish_name_upper or 'GRAVEDAD ESPECÍFICA' in spanish_name_upper)
                # Check for urine microscope exam
                is_microscope_exam = ('URINE MICROSCOPE' in param_name_upper or 'MICROSCOPE EXAM' in param_name_upper or
                                     'EXAMEN MICROSCÓPICO' in spanish_name_upper or 'MICROSCOPÍA' in spanish_name_upper)
                # Force Carbohydrate Metabolism category parameters
                if (forced_category is None and 
                    ('INSULIN' in param_name_upper or 'INSULINA' in spanish_name_upper or
                     'HOMA-IR' in param_name_upper or 'HOMA' in param_name_upper or
                     'GLUCOSE' in param_name_upper or 'GLUCOSA' in spanish_name_upper or
                     'HEMOGLOBIN A1C' in param_name_upper or 'HBA1C' in param_name_upper)):
                    forced_category = 'Biochemistry (serum / plasma) - Carbohydrate Metabolism'
                
                # Force Urine testing - Chemical and urine sediment analysis
                if (forced_category is None and 
                    ('UROBILIGEN' in param_name_upper or 'UROBILINOGEN' in param_name_upper or
                     'KETONES' in param_name_upper or 'CETONAS' in spanish_name_upper or
                     'NITRITES' in param_name_upper or 'NITRITOS' in spanish_name_upper or
                     ('RED BLOOD CELL COUNT' in param_name_upper and is_urine_unit) or
                     ('WHITE CELL COUNT' in param_name_upper and is_urine_unit) or
                     is_ph or is_density or is_microscope_exam or
                     'UROBILINÓGENO' in spanish_name_upper or
                     'BILIRUBIN' in param_name_upper and is_urine_unit or
                     'GLUCOSE' in param_name_upper and is_urine_unit or
                     'PROTEIN' in param_name_upper and is_urine_unit or
                     'LEUKOCYTE' in param_name_upper and is_urine_unit)):
                    forced_category = 'Urine testing - Chemical and urine sediment analysis'
                
                # Use forced category if set, otherwise use current category from PDF
                final_category = forced_category if forced_category else current_category_name
                
                # Create parameter entry
                parameter = {
                    'spanish_name': param_name,
                    'english_name': english_name,
                    'category': final_category,
                    'unit': result['unit'],
                    'values': result['values'],
                    'explanation': '',
                    'reference_range': result['reference']  # Store reference from PDF
                }
                
                # Store reference range
                if result['reference']:
                    reference_ranges[english_name] = result['reference']
                    reference_ranges[param_name] = result['reference']
                
                # Add to appropriate category (may be different from current_category_name if forced)
                # Find or create the category for this parameter
                target_category_name = final_category
                target_category = None
                for cat in categories:
                    if cat['name'] == target_category_name:
                        target_category = cat
                        break
                
                if target_category is None:
                    # Don't create "General" category if no explicit category was detected
                    # This prevents creating a "General" category with invalid parameters (like patient name)
                    if target_category_name == 'General' and not explicit_category_detected:
                        # Skip this parameter - it's likely invalid (e.g., patient name parsed as parameter)
                        continue
                    
                    target_category = {
                        'name': target_category_name,
                        'spanish_name': '',
                        'parameters': []
                    }
                    categories.append(target_category)
                
                target_category['parameters'].append(parameter)
                last_parameter = parameter  # Track this as last parameter
                
                # Also update current_category if it's the same, for consistency
                if current_category and current_category['name'] == target_category_name:
                    current_category = target_category
        
        # Save notes to last parameter
        if last_parameter is not None and current_notes:
            last_parameter['explanation'] = self._join_note_lines(current_notes)
        
        # Don't forget the last category (only if not already in categories)
        # BUT: Don't add "General" category if it's still the default and wasn't explicitly created
        # This prevents adding a "General" category with invalid parameters (like patient name)
        if current_category and current_category['parameters']:
            # Don't add "General" category if no explicit category was detected
            if current_category['name'] == 'General' and not explicit_category_detected:
                # Skip adding this category - it likely contains invalid parameters
                pass
            elif current_category not in categories:
                categories.append(current_category)
        
        logger.info(f"Extracted {len(categories)} categories with {sum(len(c['parameters']) for c in categories)} parameters")
        return categories, reference_ranges
    
    def _join_note_lines(self, lines: List[str]) -> str:
        """
        Join note lines intelligently, preserving spaces between words.
        
        Handles cases where PDF extraction splits words across lines without spaces.
        Also formats age reference tables for better readability.
        """
        if not lines:
            return ''
        
        import re
        
        # Join lines with spaces, then clean up
        joined = ' '.join(lines)
        
        # Check if this looks like IGF-1/Somatomedin C format (age ranges with two values per range)
        # Pattern: "0-5 years: 11 - 233 8 - 251 12-15 years: 49 - 520 90 - 596"
        if self._is_igf1_format(joined):
            return self._format_igf1_list(joined)
        
        # Check if this looks like an age reference table
        # Pattern: multiple age ranges (e.g., "16 - 19 años", "20 - 24 años") followed by values
        if self._is_age_reference_table(joined):
            return self._format_age_reference_table(joined)
        
        # Fix specific spacing issues mentioned by user:
        # 1. "to47" -> "to 47" (word "to" followed by number)
        joined = re.sub(r'\bto(\d)', r'to \1', joined, flags=re.IGNORECASE)
        
        # 2. "diabetesmellitus" -> "diabetes mellitus" (two words concatenated)
        joined = re.sub(r'diabetes(mellitus)', r'diabetes \1', joined, flags=re.IGNORECASE)
        
        # 3. "areconsidered" -> "are considered" (common word concatenated)
        joined = re.sub(r'\bare(considered)', r'are \1', joined, flags=re.IGNORECASE)
        
        # 4. Fix other common concatenations: word + lowercase word
        # Pattern: common word followed by lowercase word (2+ chars)
        common_words = ['are', 'is', 'the', 'and', 'to', 'of', 'for', 'in', 'on', 'at', 'by', 'than', 'equal', 'greater']
        for word in common_words:
            # Word boundary + word + lowercase word starting (but not if it's part of an acronym)
            pattern = rf'\b({word})([a-z][a-z]{2,})\b'
            joined = re.sub(pattern, rf'\1 \2', joined, flags=re.IGNORECASE)
        
        # 5. Fix "39 to47" -> "39 to 47" (number followed by word+number)
        joined = re.sub(r'(\d+)\s+to(\d)', r'\1 to \2', joined, flags=re.IGNORECASE)
        
        # 6. Reconstruct common acronyms that might have been broken:
        # "Hb A 1 c" -> "HbA1c" (but only if it's actually broken)
        joined = re.sub(r'\bHb\s+A\s*1\s*c\b', r'HbA1c', joined, flags=re.IGNORECASE)
        # Also handle "HbA 1 c" -> "HbA1c"
        joined = re.sub(r'\bHbA\s*1\s*c\b', r'HbA1c', joined, flags=re.IGNORECASE)
        
        # 6. Clean up multiple spaces
        joined = re.sub(r'\s+', ' ', joined)
        
        # 7. Clean up spaces around punctuation (but keep spaces after periods/commas)
        joined = re.sub(r'\s+([.,;:!?])', r'\1', joined)  # Remove space before punctuation
        joined = re.sub(r'([.,;:!?])\s*([a-zA-Z])', r'\1 \2', joined)  # Ensure space after punctuation
        
        return joined.strip()
    
    def _is_igf1_format(self, text: str) -> bool:
        """
        Check if text contains IGF-1/Somatomedin C format.
        
        Pattern: Multiple age ranges followed by two numeric ranges (male and female values)
        Example: "0-5 years: 11 - 233 8 - 251 12-15 years: 49 - 520 90 - 596"
        """
        import re
        
        # Pattern: age range followed by optional colon and two numeric ranges
        # More flexible: colon is optional, handles spacing variations
        pattern = r'\d+\s*-\s*\d+\s*(?:years|años|ans)\s*:?\s*\d+\s*-\s*\d+\s+\d+\s*-\s*\d+'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        # If we have 2+ matches, it's likely IGF-1 format
        return len(matches) >= 2
    
    def _format_igf1_list(self, text: str) -> str:
        """
        Format IGF-1/Somatomedin C reference ranges as bulleted list.
        
        Input: "0-5 years: 11 - 233 8 - 251 12-15 years: 49 - 520 90 - 596"
        Output: Bulleted list format
        """
        import re
        
        # Pattern to match: "age-age years: value1 - value2 value3 - value4"
        # More flexible pattern to handle variations in spacing
        pattern = r'(\d+)\s*-\s*(\d+)\s*(?:years|años|ans)\s*:?\s*(\d+)\s*-\s*(\d+)\s+(\d+)\s*-\s*(\d+)'
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        bullet_points = []
        for match in matches:
            age_min = match.group(1)
            age_max = match.group(2)
            male_min = match.group(3)
            male_max = match.group(4)
            female_min = match.group(5)
            female_max = match.group(6)
            
            # Format as bullet point: "• age-age years: Men: min-max, Women: min-max"
            bullet_points.append(f"• {age_min}-{age_max} years: Men: {male_min} - {male_max}, Women: {female_min} - {female_max}")
        
        if bullet_points:
            return '\n'.join(bullet_points)
        
        # Fallback: return original text if parsing fails
        return text
    
    def _is_age_reference_table(self, text: str) -> bool:
        """
        Check if text contains an age reference table pattern.
        
        Pattern: Multiple age ranges (e.g., "16 - 19 años", "20 - 24 años") 
        followed by numeric ranges (e.g., "3,96 - 15,50").
        """
        import re
        
        # Count age range patterns: "XX - XX años" or "XX-XX años"
        age_pattern = r'\d+\s*-\s*\d+\s*(?:años|years|ans)'
        age_matches = len(re.findall(age_pattern, text, re.IGNORECASE))
        
        # If we have 3+ age ranges, it's likely a reference table
        return age_matches >= 3
    
    def _format_age_reference_table(self, text: str) -> str:
        """
        Format age reference table as structured data for table rendering.
        
        Returns a JSON-like string that will be parsed by PDFBuilder to render as a table.
        Format: "__REF_TABLE__{json_data}__END_TABLE__"
        """
        import re
        import json
        
        # Translation dictionary
        translations = {
            'Niños': 'Children',
            'Niñas': 'Girls',
            'Hombres': 'Men',
            'Mujeres': 'Women',
            'adultos': 'adults',
            'años': 'years'
        }
        
        # Parse the text to extract table structure
        table_data = {
            'type': 'age_reference',
            'rows': []
        }
        
        # Find all section headers and their content
        # Pattern: "Niños:", "Niñas:", "Hombres (adultos):", "Mujeres(adultos):"
        section_pattern = r'(Niños|Niñas|Hombres|Mujeres)\s*(?:\(adultos\))?\s*:'
        
        # Find all section positions
        section_positions = []
        for match in re.finditer(section_pattern, text, re.IGNORECASE):
            section_name = match.group(1)
            section_positions.append((match.start(), match.end(), section_name))
        
        # Process each section
        for i, (start, end, section_name) in enumerate(section_positions):
            # SKIP children sections (Niños, Niñas, Children, Girls, Boys)
            if section_name in ['Niños', 'Niñas'] or section_name.lower() in ['children', 'girls', 'boys']:
                continue  # Skip children sections entirely
            
            # Get content until next section or end of text
            if i + 1 < len(section_positions):
                content = text[end:section_positions[i+1][0]]
            else:
                content = text[end:]
            
            current_section = translations.get(section_name, section_name)
            
            # Parse age ranges in this section
            # Pattern: "6-9 años:: 0,13-1,87 ng/mL" or "• 6-9 años:: 0,13-1,87 ng/mL"
            # BUT: Skip age ranges for children (6-14 years)
            age_pattern = r'(?:•\s*)?(\d+)\s*-\s*(\d+)\s*(?:años|years|ans)\s*:?\s*((?:\d+[,\.]\d+\s*-\s*\d+[,\.]\d+)(?:\s+[a-zA-Z/]+)?)'
            age_matches = re.finditer(age_pattern, content, re.IGNORECASE)
            
            for match in age_matches:
                age_min = int(match.group(1))
                age_max = int(match.group(2))
                
                # Skip children age ranges (6-14 years)
                if age_max <= 14:
                    continue
                
                value_str = match.group(3).strip()
                
                # Extract value range and unit
                value_match = re.match(r'(\d+[,\.]\d+)\s*-\s*(\d+[,\.]\d+)(?:\s+([a-zA-Z/]+))?', value_str)
                if value_match:
                    val_min = value_match.group(1)
                    val_max = value_match.group(2)
                    unit = value_match.group(3) if value_match.group(3) else ''
                    
                    table_data['rows'].append({
                        'group': current_section,
                        'age_range': f"{age_min}-{age_max} {translations.get('años', 'years')}",
                        'value_range': f"{val_min} - {val_max}",
                        'unit': unit.strip()
                    })
        
        # If no sections found, try to parse as simple age ranges
        if not table_data['rows']:
            # Pattern: "16 - 19 años 3,96 - 15,50 3,36 - 18,20"
            age_pattern = r'(\d+)\s*-\s*(\d+)\s*(?:años|years|ans)\s*((?:\d+[,\.]\d+\s*-\s*\d+[,\.]\d+(?:\s+[a-zA-Z/]+)?\s*)+)'
            age_matches = re.finditer(age_pattern, text, re.IGNORECASE)
            
            for match in age_matches:
                age_min = match.group(1)
                age_max = match.group(2)
                values = match.group(3).strip()
                
                # Extract all value ranges
                value_ranges = re.findall(r'(\d+[,\.]\d+)\s*-\s*(\d+[,\.]\d+)(?:\s+([a-zA-Z/]+))?', values)
                
                for val_min, val_max, unit in value_ranges:
                    unit = unit.strip() if unit else ''
                    table_data['rows'].append({
                        'group': '',
                        'age_range': f"{age_min}-{age_max} {translations.get('años', 'years')}",
                        'value_range': f"{val_min} - {val_max}",
                        'unit': unit
                    })
        
        # If we found table data, return it as a special marker
        if table_data['rows']:
            return f"__REF_TABLE__{json.dumps(table_data)}__END_TABLE__"
        
        # Fallback: return original text
        return text.strip()
    
    def _is_skip_line(self, line: str) -> bool:
        """Check if line should be skipped (headers, footers, notes)"""
        skip_patterns = [
            r'^Patient:',
            r'^Nombre:',
            r'^Sample:',
            r'^N[°º]\s*Laboratorio:',
            r'^Source:',
            r'^Entity:',
            r'^Doctor:',
            r'^Reception date:',
            r'^Fecha Recepción:',
            r'^Validation date:',
            r'^Fecha Validación:',
            r'^Print date:',
            r'^Fecha Informe:',
            r'^This laboratory has',
            r'^Este laboratorio',
            r'^Sistema de Gestión de Calidad',
            r'^certificado de acuerdo',
            r'^norma ISO',
            r'^entidad certificadora',
            r'^SNB Diagn',
            r'^P[áa]gina \d+',
            r'^Page \d+',
            r'^\d+$',  # Just a page number
            r'^-\*-$',
            r'^Id card:',
            r'^D\.N\.I\.:',
            r'^Sex:',
            r'^Sexo:',
            r'^Birth date',
            r'^Cargo:',
            r'^Origen:',
            r'^N[°º]Historia:',
            r'^N[°º]Referencia:',
            r'^Cama:',
            r'^Fecha petición:',
            r'^Hora Alta:',
            r'^\s*$',
            r'^\d{6}$',  # Lab reference numbers
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        
        # Check if line contains footer text (even if not at start)
        footer_keywords = [
            'este laboratorio',
            'sistema de gestión de calidad',
            'certificado de acuerdo',
            'norma iso',
            'entidad certificadora',
            'sgs ics',
            'snb diagnósticos'
        ]
        line_lower = line.lower()
        for keyword in footer_keywords:
            if keyword in line_lower:
                return True
        
        return False
    
    def _is_note_line(self, line: str) -> bool:
        """
        Check if line is a note/explanation/recommendation that should be attached
        to the previous parameter's explanation rather than treated as a result.
        
        Examples:
        - "Secondary prevention and very high CVR: < 55 mg/dL"
        - "16 - 19 años: 3,9"
        - "Recommended LDL Cholesterol values..."
        """
        line_lower = line.lower().strip()
        
        # Lines starting with "- " followed by descriptive text (recommendations)
        # Pattern: "- Secondary prevention..." or "- High CVR: < 70 mg/dL"
        if re.match(r'^-\s+', line):
            return True
        
        # Lines with age ranges followed by values (reference tables)
        # Pattern: "16 - 19 años", "20 - 24 años", "0 - <2 meses", "6 meses - <1 año", "1 month - 20 years", etc.
        if re.match(r'^\d+\s*-\s*[<>]?\s*\d+\s*(años|years|ans|meses|months)', line_lower):
            return True
        # Also catch age ranges starting with time periods like "6 meses - <1 año", "1 month - 20 years"
        if re.match(r'^\d+\s*(meses|months|month|años|years|year)\s*-\s*[<>]?\s*\d+', line_lower):
            return True
        
        # Lines with cardiovascular risk indicators
        if re.search(r'(secondary prevention|high cvr|moderate cvr|low cvr|cardiovascular risk)', line_lower):
            return True
        
        # Lines starting with "Recommended", "Low", "Average", "High" followed by risk/range info
        # Also catch "Low Cardiovascular Risk:", "Average Cardivascular Risk:", etc.
        if re.match(r'^(Recommended|Low|Average|High|Moderate)\s+', line, re.IGNORECASE):
            return True
        
        # Lines for Vitamin D status categories
        # Pattern: "Deficiency:", "Insufficiency:", "Sufficiency:", "Toxicity:"
        if re.match(r'^(Deficiency|Insufficiency|Sufficiency|Toxicity)\s*:', line, re.IGNORECASE):
            return True
        
        # Lines with "Cardiovascular Risk" or "Cardivascular Risk" (typo in PDF)
        if re.search(r'Cardiovascular\s+Risk|Cardivascular\s+Risk', line, re.IGNORECASE):
            return True
        
        # Lines with "Pacientes" followed by condition (Spanish patient groups)
        if re.match(r'^Pacientes\s+', line, re.IGNORECASE):
            return True
        
        # Lines with "Values" followed by descriptive text
        if re.match(r'^Values?\s+(between|greater|below|above)', line_lower):
            return True
        
        # Lines with method names (Chemiluminiscence, Radioimmunoassay, etc.)
        if re.match(r'^(Chemiluminiscence|Chemiluminescence|Radioimmunoassay|Immunoassay|ELISA|Method:)', line, re.IGNORECASE):
            return True
        
        # Lines with "Reference Range:" followed by text
        if re.match(r'^Reference\s+Range:', line, re.IGNORECASE):
            return True
        
        # Lines with "Children:" or "Adults:" reference values
        if re.match(r'^(Children|Adults|Adultes|Niños|Adultos):', line, re.IGNORECASE):
            return True
        
        # Lines starting with "(applicable" or similar parenthetical notes
        if re.match(r'^\(applicable', line, re.IGNORECASE):
            return True
        
        # Lines with "Ratio above" or "Ratio below" (PSA ratio interpretation)
        if re.match(r'^Ratio\s+(above|below|greater|less)', line, re.IGNORECASE):
            return True
        
        # Lines with "probably benign" or "probably malignant" (interpretation notes)
        if re.search(r'probably\s+(benign|malignant)', line, re.IGNORECASE):
            return True
        
        # Lines with "Normal value:" or "Valor normal:" (reference indicator for serology, etc.)
        if re.match(r'^(Normal\s+value|Valor\s+normal)\s*:', line, re.IGNORECASE):
            return True
        
        # Lines with "Test performed" or similar disclaimer text
        if re.match(r'^Test\s+performed', line, re.IGNORECASE):
            return True
        
        # Lines starting with "In case of" (continuation of test disclaimers)
        if re.match(r'^In\s+case\s+of', line, re.IGNORECASE):
            return True
        
        # Lines with "confirmatory method" or "screening method" (test disclaimers)
        if re.search(r'(confirmatory|screening)\s+method', line, re.IGNORECASE):
            return True

        # Lines with CKD/GFR explanatory text
        # Pattern: "Current clinical guidelines", "Stage 1", "Stage 2", etc.
        # BUT: Don't treat parameter lines as notes (they have values, units, and references in brackets)
        # Check if this looks like a parameter line first (has brackets with reference)
        is_parameter_line = re.search(r'\[.*\]', line) and (
            re.search(r'\d+[,\.]\d+', line) or  # Has numeric value
            re.search(r'(En curso|en curso|en proceso|pending|In progress)', line, re.IGNORECASE)  # Has qualitative value
        )
        
        if re.match(r'^Current\s+clinical\s+guidelines', line, re.IGNORECASE):
            return True
        if re.match(r'^Stage\s+\d+[a-z]?\s+', line, re.IGNORECASE):
            return True
        # Only treat as note if it contains CKD/GFR terms AND is NOT a parameter line
        if not is_parameter_line and re.search(r'(glomerular\s+filtration|gfr|egfr|ckd|chronic\s+kidney)', line_lower):
            return True
        if re.match(r'^The\s+definition\s+of\s+CKD', line, re.IGNORECASE):
            return True
        if re.search(r'nefrologia\s+\d{4}', line_lower):
            return True
        if re.match(r'^(Depending|albuminuria|End-stage)', line, re.IGNORECASE):
            return True

        # HbA1c explanatory text can wrap across lines in the PDF extraction.
        # These continuation lines often start with a number or a mid-sentence word.
        # Example: "47 mmol/mol) are considered..." or "mellitus and cardiovascular disease)..."
        if re.match(r'^\d+\s*mmol/mol', line_lower):
            return True
        if line_lower.startswith(('mellitus', 'considered', 'are considered', 'criteria', 'diagnostic')):
            return True
        
        # Lines with "HbA1c levels" or similar explanatory text
        # NOTE: compare against lowercased text (or use IGNORECASE) to avoid missing notes.
        if re.match(r'^hba1c\s+levels', line_lower):
            return True
        
        # Lines that are just age ranges with values (table format)
        # Pattern: "25 - 34 30 - 100 años 2,5" or "25 - 34 años 2,5" or "0 - <2 meses 28,90" or similar
        if re.match(r'^\d+\s*-\s*[<>]?\s*\d+', line) and not re.search(r'\[.*\]', line):
            # Check if it looks like a reference table row
            # Must have age range pattern AND a numeric value, but no parameter name
            if re.search(r'\d+[,\.]\d+', line):
                # Check if it starts with age range (not a parameter name)
                # Age ranges typically start with numbers, not capital letters
                if not re.match(r'^[A-Z]', line):
                    # Likely a reference table row
                    return True
        
        # Lines with age ranges followed by colon and values
        # Pattern: "16 - 19 años: 3,9" or "25 - 34 años: 2,5"
        if re.match(r'^\d+\s*-\s*\d+\s*(años|years|ans)\s*:', line_lower):
            return True
        
        # Lines that are just numeric ranges (age ranges without "años")
        # Pattern: "25 - 34 2,5" (age range followed by value)
        if re.match(r'^\d+\s*-\s*\d+\s+\d+[,\.]\d+', line) and len(line) < 40:
            return True
        
        # Lines with age ranges followed by value ranges (table format)
        # Pattern: "25 - 34 30 - 100 años 2,5" or "6-9 años: 0,13-1,87 ng/mL"
        if re.match(r'^\d+\s*-\s*\d+', line) and re.search(r'\d+[,\.]\d+', line):
            # Check if it's a short line (likely a table row, not a parameter)
            if len(line) < 60 and not re.search(r'\[.*\]', line):
                # Likely a reference table row
                return True
        
        # Lines with "Niños:" or "Niñas:" (children reference ranges) - SKIP these
        # We don't want children reference ranges in explanations
        if re.match(r'^(Niños|Niñas|Children|Boys|Girls):', line, re.IGNORECASE):
            return False  # Don't treat as note, just skip it
        
        # Lines with "Hombres" or "Mujeres" followed by age ranges
        if re.match(r'^(Hombres|Mujeres|Men|Women)\s*\(', line, re.IGNORECASE):
            return True
        
        return False
    
    def _detect_category(self, line: str) -> Optional[str]:
        """Detect if line is a category header and return mapped category name"""
        line_lower = line.lower().strip()
        
        # Skip lines that are clearly results (contain [ ] for reference)
        if '[' in line and ']' in line:
            return None
        
        # Skip lines with numeric values (likely results)
        if re.search(r'\d+[,\.]\d+', line):
            return None
        
        # Skip lines that look like results with text values
        # These have a parameter name (ALL CAPS) followed by text (not just a category name)
        # Pattern: "URINE MICROSCOPE EXAM Se estudia..." should NOT be a category
        if re.match(r'^[A-Z][A-Z\s]{5,}\s+[A-Za-z]', line):
            # Line starts with multiple uppercase words followed by text
            # This is likely a result line with text value, not a category header
            words = line.split()
            # If there are many words and the line is long, it's likely a result
            if len(words) > 4 and len(line) > 40:
                return None
        
        # Check for category keywords
        for keyword, category in self.category_mapping.items():
            if keyword in line_lower:
                return category
        
        # Check for subsection headers (all caps, no numbers)
        if line.isupper() and len(line) > 3 and not re.search(r'\d', line):
            # Could be a subsection like "Red series", "White series"
            # Return None to let it continue with current category
            pass
        
        return None
    
    def _parse_result_line(self, line: str) -> Optional[Dict]:
        """
        Parse a single result line.
        
        Expected formats:
        - "PARAMETER NAME 4,68 x10⁶/mm³ [ 4,1 - 5,75 ]"
        - "PARAMETER NAME * 4,68 unit [ < 5 ]"
        - "PARAMETER NAME 4,68 unit"
        
        Returns:
            {
                'name': str,
                'english_name': str,
                'value': str,
                'unit': str,
                'reference': str
            }
            or None if not a valid result line
        """
        # Skip empty or too short lines
        if not line or len(line) < 5:
            return None
        
        # Skip if this is a note line (should have been caught earlier, but double-check)
        if self._is_note_line(line):
            return None
        
        # Pattern for result line with reference range in brackets
        # Handles: NAME [*] VALUE UNIT [ REFERENCE ]
        # Value can be: "4,68", "<1", ">5", "* 4,68", etc.
        pattern_with_ref = r'^(.+?)\s+(\*?\s*[<>]?\s*[\d,\.]+(?:\s*[<>]\s*[\d,\.]+)?)\s+([^\[\]]+?)\s*\[\s*(.+?)\s*\]$'
        
        # Pattern for result line without unit but with reference (e.g., "pH 5,5 [ 5 - 8 ]")
        # Handles: NAME VALUE [ REFERENCE ] (no unit)
        # Value can be: "5,5", "<1", ">5", etc.
        pattern_no_unit_with_ref = r'^(.+?)\s+(\*?\s*[<>]?\s*[\d,\.]+)\s*\[\s*(.+?)\s*\]$'
        
        # Pattern without reference range
        # Value can be: "4,68", "<1", ">5", etc.
        pattern_no_ref = r'^(.+?)\s+(\*?\s*[<>]?\s*[\d,\.]+)\s+([a-zA-Z%/³²µ°]+.*)$'
        
        # Pattern for qualitative results (e.g., "Negative", "Positive", "en curso", "No se detecta", "+", "++", "+++")
        pattern_qualitative = r'^(.+?)\s+(Negative|Positive|Negativo|Positivo|Normal|Anormal|en curso|in progress|pending|No se detecta|Not detected|No detectado|Reactivo|No reactivo|Reactive|Non-reactive|Trace|Indicio|\+{1,4})\s*(?:\[\s*(.+?)\s*\])?$'
        
        # Pattern for qualitative results with qualitative reference (e.g., "KETONES Negativo Negativo" or "KETONES Negativo Negative")
        # Handles: NAME QUALITATIVE_VALUE QUALITATIVE_REFERENCE (no unit, no brackets)
        # Both value and reference can be in Spanish or English
        pattern_qualitative_with_qual_ref = r'^(.+?)\s+(Negativo|Positivo|Indicio|Normal|Anormal|Negative|Positive|Trace|No se detecta|Not detected|No detectado|Reactivo|No reactivo)\s+(Negativo|Positivo|Indicio|Normal|Anormal|Negative|Positive|Trace|No se detecta|Not detected|No detectado|Reactivo|No reactivo)(?:\s*[<>]?\s*\d+)?$'
        
        # Pattern for qualitative results with symbols only (e.g., "KETONES +++" or "KETONES ++")
        # Handles: NAME +++ or NAME ++ or NAME + (standalone, no unit, no reference)
        # This is common in urine analysis for semi-quantitative results
        pattern_qualitative_symbols_only = r'^(.+?)\s+(\+{1,4})\s*$'
        
        # Pattern for qualitative results with symbols and qualitative reference (e.g., "KETONES +++ Negative" or "KETONES ++ Negativo")
        # Handles: NAME SYMBOL QUALITATIVE_REFERENCE
        pattern_qualitative_symbols_with_ref = r'^(.+?)\s+(\+{1,4})\s+(Negativo|Positivo|Indicio|Normal|Anormal|Negative|Positive|Trace|No se detecta|Not detected|No detectado|Reactivo|No reactivo)(?:\s*[<>]?\s*\d+)?$'
        
        # Pattern for qualitative results with unit and reference in brackets (e.g., "Filtrado glomerular estimado (CKD-EPI) En curso ml/min/1,73m2 [ > 60]")
        # Handles: NAME QUALITATIVE_VALUE UNIT [ REFERENCE ]
        # The unit can contain slashes, numbers, commas, dots, etc.
        pattern_qualitative_with_unit_and_ref = r'^(.+?)\s+(En curso|en curso|en proceso|pending|In progress|In Progress)\s+(.+?)\s*\[\s*(.+?)\s*\]$'
        
        # Pattern for qualitative results with unit (e.g., "RED BLOOD CELL COUNT Negativo /µL Negative < 5" or "RED BLOOD CELL COUNT + /μL Negativo")
        # Handles: NAME QUALITATIVE_VALUE UNIT REFERENCE
        # "+", "++", "+++", "++++" are common qualitative values meaning "Positive" or "Present" with varying intensity
        pattern_qualitative_with_unit = r'^(.+?)\s+(\+{1,4}|Negative|Positive|Negativo|Positivo|Indicio|Trace)\s+([/µ\w]+)\s+(.+)$'
        
        # Pattern for text results (e.g., "URINE MICROSCOPE EXAM Se estudia la muestra...")
        # Handles: NAME [long text result]
        pattern_text_result = r'^(.+?)\s+(Se\s|The\s|No\s|Normal|Anormal|Abnormal|Negative|Positive|Negativo|Positivo).+$'
        
        result = None
        
        # VERY FIRST: Try pattern for symbols only (e.g., "KETONES +++" or "KETONES ++")
        # This MUST be checked before any other pattern to prevent "KETONES +++" being captured as parameter name
        match = re.match(pattern_qualitative_symbols_only, line, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            result = {
                'name': name,
                'value': value,  # Keep as "+++" (or translate to "Positive" if needed)
                'unit': '',
                'reference': ''
            }
        
        # Try pattern for symbols with qualitative reference (e.g., "KETONES +++ Negative")
        if not result:
            match = re.match(pattern_qualitative_symbols_with_ref, line, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip()
                reference = match.group(3).strip()
                
                # Translate reference
                reference = translate_value(reference)
                
                result = {
                    'name': name,
                    'value': value,  # Keep as "+++" 
                    'unit': '',
                    'reference': reference
                }
        
        # Try qualitative pattern with qualitative reference (e.g., "KETONES Negativo Negativo" or "KETONES Negativo Negative")
        # This must be checked early to prevent "KETONES Negativo" being captured as name
        if not result:
            match = re.match(pattern_qualitative_with_qual_ref, line, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip()
                reference = match.group(3).strip()
                
                # Translate values
                value = translate_value(value)
                reference = translate_value(reference)
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': '',
                    'reference': reference
                }
        
        # Try qualitative pattern with unit and reference in brackets (e.g., "Filtrado glomerular estimado (CKD-EPI) En curso ml/min/1,73m2 [ > 60]")
        # This must be checked BEFORE pattern_with_ref to avoid misparsing
        if not result:
            match = re.match(pattern_qualitative_with_unit_and_ref, line, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip()
                unit = match.group(3).strip()
                reference = match.group(4).strip()
                
                # Translate value
                value = translate_value(value)
                
                # Clean up unit (remove trailing spaces, normalize)
                unit = self._normalize_unit(unit)
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': unit,
                    'reference': reference
                }
        
        # Try pattern with reference (including unit)
        if not result:
            match = re.match(pattern_with_ref, line)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip().replace('*', '').strip()
                unit = match.group(3).strip()
                reference = match.group(4).strip()
                
                # Clean up unit (remove trailing spaces, normalize)
                unit = self._normalize_unit(unit)
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': unit,
                    'reference': reference
                }
        
        # Try pattern without unit but with reference (e.g., "pH 5,5 [ 5 - 8 ]")
        if not result:
            match = re.match(pattern_no_unit_with_ref, line)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip().replace('*', '').strip()
                reference = match.group(3).strip()
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': '',
                    'reference': reference
                }
        
        # Try qualitative pattern with unit BEFORE simple qualitative pattern
        # (e.g., "RED BLOOD CELL COUNT Negativo /µL Negativo")
        # This must be checked BEFORE pattern_qualitative to avoid capturing "/µL Negativo" in the name
        if not result:
            match = re.match(pattern_qualitative_with_unit, line, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip()
                unit = match.group(3).strip()
                reference = match.group(4).strip()
                
                unit = self._normalize_unit(unit)
                
                # Translate values
                value = translate_value(value)
                reference = translate_value(reference)
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': unit,
                    'reference': reference
                }
        
        # Try qualitative pattern (without unit) - BEFORE numeric patterns to avoid misparse
        # e.g., "HIV 1 + HIV 2 ANTIBODIES + P24 ANTIGEN No reactivo" should not parse "2" as value
        if not result:
            match = re.match(pattern_qualitative, line, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip()
                reference = match.group(3).strip() if match.group(3) else ''
                
                # Translate values
                value = translate_value(value)
                reference = translate_value(reference) if reference else ''
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': '',
                    'reference': reference
                }
        
        # Try pattern without reference (numeric values)
        if not result:
            match = re.match(pattern_no_ref, line)
            if match:
                name = match.group(1).strip()
                value = match.group(2).strip().replace('*', '').strip()
                unit = match.group(3).strip()
                
                unit = self._normalize_unit(unit)
                
                result = {
                    'name': name,
                    'value': value,
                    'unit': unit,
                    'reference': ''
                }
        
        # Try text result pattern (for long text results like URINE MICROSCOPE EXAM)
        if not result:
            # Check specifically for URINE MICROSCOPE EXAM pattern
            # The line looks like: "URINE MICROSCOPE EXAM Se estudia la muestra..."
            # Where "URINE MICROSCOPE EXAM" is in ALL CAPS and the rest is the value
            if 'URINE MICROSCOPE EXAM' in line.upper():
                # Find where the parameter name ends
                # Look for the pattern where ALL CAPS words end
                match = re.match(r'^(URINE\s+MICROSCOPE\s+EXAM)\s+(.+)$', line, re.IGNORECASE)
                if match:
                    name = match.group(1).strip().upper()
                    value_text = match.group(2).strip()
                    
                    # This is a text result - store the full text (will be replaced with "Normal" in table)
                    result = {
                        'name': name,
                        'value': value_text,  # Full text, will be replaced with "Normal" in table_generator
                        'unit': '',
                        'reference': ''
                    }
        
        if result:
            # Get English name
            result['english_name'] = self._get_english_name(result['name'])
            
            # Create values structure compatible with DataTransformer
            # Uses 'sample_date' placeholder - will be replaced with actual date
            result['values'] = {'__SAMPLE_DATE__': result['value']}
            
            return result
        
        return None
    
    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit string"""
        if not unit:
            return ''
        
        unit = unit.strip()
        
        # Fix common encoding issues
        replacements = {
            'x106': 'x10⁶',
            'x103': 'x10³',
            'x10�': 'x10³',
            '/mm�': '/mm³',
            'mcmol': 'µmol',
            'mcg': 'µg',
        }
        
        for old, new in replacements.items():
            unit = unit.replace(old, new)
        
        return unit
    
    def _get_english_name(self, name: str) -> str:
        """Get English name for a parameter"""
        # Check parameters config
        if name in self.parameters_config:
            return self.parameters_config[name].get('english_name', name)
        
        # Try case-insensitive match
        name_lower = name.lower()
        for key, config in self.parameters_config.items():
            if key.lower() == name_lower:
                return config.get('english_name', name)
        
        # Return original name (it might already be in English)
        return name
    
    def extract_metadata_only(self, filepath: str) -> Dict[str, Any]:
        """
        Extract only metadata from PDF (faster, for initial upload response).
        
        Returns metadata dict without full parsing of results.
        """
        logger.info(f"Extracting metadata from PDF: {filepath}")
        
        with pdfplumber.open(filepath) as pdf:
            # Only read first page for metadata
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ''
            else:
                text = ''
        
        return self._extract_metadata(text)

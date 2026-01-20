"""
Script to map parameters from parameters.json to categories based on REFERENCE_VALUES.md
This ensures all parameters are assigned to the correct categories from REFERENCE_VALUES.md
"""
import json
import os

# Mapping of parameter names (English) from reference_values.json to categories
PARAMETER_TO_CATEGORY = {
    # Hematology and Hemostasis
    "Red Blood Cells": "Hematology and Hemostasis",
    "Hemoglobin": "Hematology and Hemostasis",
    "Hematocrit": "Hematology and Hemostasis",
    "MCV": "Hematology and Hemostasis",
    "MCH": "Hematology and Hemostasis",
    "MCHC": "Hematology and Hemostasis",
    "RDW": "Hematology and Hemostasis",
    "White Blood Cells": "Hematology and Hemostasis",
    "Neutrophils %": "Hematology and Hemostasis",
    "Lymphocytes %": "Hematology and Hemostasis",
    "Monocytes %": "Hematology and Hemostasis",
    "Eosinophils %": "Hematology and Hemostasis",
    "Basophils %": "Hematology and Hemostasis",
    "Platelets": "Hematology and Hemostasis",
    "Mean Platelet Volume": "Hematology and Hemostasis",
    "ESR (1st hour)": "Hematology and Hemostasis",
    "Fibrinogen": "Hematology and Hemostasis",
    
    # Carbohydrate Metabolism
    "Glucose": "Carbohydrate Metabolism",
    "HbA1c": "Carbohydrate Metabolism",
    "HbA1c (IFCC)": "Carbohydrate Metabolism",
    
    # Lipid Metabolism
    "Total Cholesterol": "Lipid Metabolism",
    "HDL Cholesterol": "Lipid Metabolism",
    "LDL Cholesterol": "Lipid Metabolism",
    "Triglycerides": "Lipid Metabolism",
    "Apolipoprotein A1": "Lipid Metabolism",
    "Apolipoprotein B": "Lipid Metabolism",
    
    # Proteins
    "Total Proteins": "Proteins",
    "Albumin": "Proteins",
    "CRP": "Proteins",
    "High-sensitivity CRP": "Proteins",
    "Ceruloplasmin": "Proteins",
    "Eosinophil Cationic Protein": "Proteins",
    
    # Renal Function
    "Uric Acid": "Renal Function",
    "Creatinine": "Renal Function",
    "Glomerular Filtration Rate (CKD-EPI)": "Renal Function",
    "Urea": "Renal Function",
    
    # Ions
    "Sodium": "Ions",
    "Potassium": "Ions",
    "Chlorides": "Ions",
    "Magnesium": "Ions",
    
    # Liver Function
    "Total Bilirubin": "Liver Function",
    "Direct Bilirubin": "Liver Function",
    "ALT": "Liver Function",
    "AST": "Liver Function",
    "Gamma-GT": "Liver Function",
    "Alkaline Phosphatase": "Liver Function",
    
    # Iron Metabolism
    "Iron": "Iron Metabolism",
    "Transferrin": "Iron Metabolism",
    "Transferrin Saturation Index": "Iron Metabolism",
    "Total Iron Binding Capacity": "Iron Metabolism",
    "Ferritin": "Iron Metabolism",
    
    # Phosphocalcic Metabolism
    "Phosphorus": "Phosphocalcic Metabolism",
    "Calcium": "Phosphocalcic Metabolism",
    "Ionized Calcium": "Phosphocalcic Metabolism",
    
    # Bone Markers
    "N-terminal Propeptide of Type I Procollagen": "Bone Markers",
    "Beta Cross Laps (CTX)": "Bone Markers",
    "Bone Alkaline Phosphatase (adults)": "Bone Markers",
    
    # Acylcarnitine Test
    "Free Carnitine": "Acylcarnitine Test",
    "Total Carnitine": "Acylcarnitine Test",
    
    # Vitamins
    "Vitamin B1 (Thiamine)": "Vitamins",
    "Vitamin B6 (pyridoxal 5 phosphate)": "Vitamins",
    "Vitamin B12": "Vitamins",
    "Holotranscobalamin": "Vitamins",
    "Homocysteine": "Vitamins",
    "Vitamin D (25-OH)": "Vitamins",
    "Methylmalonic Acid": "Vitamins",
    "Coenzyme Q10": "Vitamins",
    "Erythrocyte Folic Acid": "Vitamins",
    
    # Immunology
    "Immunoglobulin IgA": "Immunology",
    "Immunoglobulin IgE": "Immunology",
    "Anti-thyroglobulin Antibodies": "Immunology",
    "Anti-TPO Antibodies (microsomal)": "Immunology",
    "Deamidated Gliadin Antibodies IgA": "Immunology",
    "Deamidated Gliadin Antibodies IgG": "Immunology",
    "Transglutaminase Antibodies IgA": "Immunology",
    "Transglutaminase Antibodies IgG": "Immunology",
    "TNF alpha": "Immunology",
    "Interleukin 6": "Immunology",
    
    # Endocrinology - Thyroid Hormones
    "TSH": "Endocrinology - Thyroid Hormones",
    "Free T4": "Endocrinology - Thyroid Hormones",
    "Free T3": "Endocrinology - Thyroid Hormones",
    "Reverse T3 (adults)": "Endocrinology - Thyroid Hormones",
    
    # Endocrinology - Sex Hormones
    "17-Beta Estradiol": "Endocrinology - Sex Hormones",
    "Total Testosterone": "Endocrinology - Sex Hormones",
    "% Free Testosterone": "Endocrinology - Sex Hormones",
    "Estimated Free Testosterone": "Endocrinology - Sex Hormones",
    "Bioavailable Testosterone": "Endocrinology - Sex Hormones",
    
    # Endocrinology - Adrenal Hormones
    "Basal Cortisol": "Endocrinology - Adrenal Hormones",
    "DHEA-S (35-44 years)": "Endocrinology - Adrenal Hormones",
    
    # Endocrinology - Pituitary Hormones
    "LH": "Endocrinology - Pituitary Hormones",
    "FSH": "Endocrinology - Pituitary Hormones",
    "Prolactin": "Endocrinology - Pituitary Hormones",
    "SHBG": "Endocrinology - Pituitary Hormones",
    "ACTH": "Endocrinology - Pituitary Hormones",
    "Somatomedin C (IGF-1, 30-39 years)": "Endocrinology - Pituitary Hormones",
    "Basal Insulin": "Endocrinology - Pituitary Hormones",
    "HOMA Index": "Endocrinology - Pituitary Hormones",
    "C-Peptide": "Endocrinology - Pituitary Hormones",
    "Intact PTH": "Endocrinology - Pituitary Hormones",
    "Osteocalcin": "Endocrinology - Pituitary Hormones",
    "Adiponectin (BMI < 25)": "Endocrinology - Pituitary Hormones",
    
    # Preventive Medicine
    "Omega 3 Index (W3)": "Preventive Medicine",
}

def normalize_name(name):
    """Normalize parameter name for matching"""
    return name.strip().lower()

def map_parameters_to_categories():
    """Map parameters in parameters.json to categories from REFERENCE_VALUES.md"""
    # Load parameters.json
    params_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'parameters.json')
    with open(params_path, 'r', encoding='utf-8') as f:
        parameters = json.load(f)
    
    # Load reference_values.json to get all parameter names
    ref_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'reference_values.json')
    with open(ref_path, 'r', encoding='utf-8') as f:
        reference_values = json.load(f)
    
    # Create reverse mapping: normalized English name -> category
    ref_name_to_category = {}
    for ref_name, category in PARAMETER_TO_CATEGORY.items():
        ref_name_to_category[normalize_name(ref_name)] = category
    
    # Also map from reference_values.json keys
    for ref_name in reference_values.keys():
        if ref_name in PARAMETER_TO_CATEGORY:
            ref_name_to_category[normalize_name(ref_name)] = PARAMETER_TO_CATEGORY[ref_name]
    
    # Update parameters.json
    updated_count = 0
    for spanish_name, param_data in parameters.items():
        english_name = param_data.get('english_name', '')
        current_category = param_data.get('category', '')
        
        # Try to find category from mapping
        if english_name:
            normalized = normalize_name(english_name)
            if normalized in ref_name_to_category:
                new_category = ref_name_to_category[normalized]
                if new_category != current_category:
                    param_data['category'] = new_category
                    updated_count += 1
                    print(f"Updated {spanish_name} -> {new_category}")
    
    # Save updated parameters.json
    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump(parameters, f, indent=2, ensure_ascii=False)
    
    print(f"\nUpdated {updated_count} parameters with categories from REFERENCE_VALUES.md")

if __name__ == '__main__':
    map_parameters_to_categories()

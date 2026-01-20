"""
Script to translate remaining Spanish parameter names to English
"""
import json
import os

# Translation mappings for remaining parameters
TRANSLATIONS = {
    # Urine Analysis
    "pH en orina": "Urine pH",
    "Densidad en orina": "Urine Specific Gravity",
    "Glucosa en orina": "Urine Glucose",
    "Proteinas en orina": "Urine Proteins",
    "Urobilinogeno en orina": "Urine Urobilinogen",
    "Cuerpos cetonicos en orina": "Urine Ketone Bodies",
    "Nitritos en orina": "Urine Nitrites",
    "Hematies en orina": "Urine Red Blood Cells",
    "Leucocitos en orina": "Urine White Blood Cells",
    "Sedimento": "Urine Sediment",
    
    # Drug Monitoring and Toxicology
    "Cobre (serum) (ICP-MS)": "Copper (serum) (ICP-MS)",
    "Cromo (serum)": "Chromium (serum)",
    "Mercurio (blood)": "Mercury (blood)",
    "Selenio (serum)": "Selenium (serum)",
    "Magnesio eritrocitario": "Erythrocyte Magnesium",
    "Zinc (serum)": "Zinc (serum)",
    "Zinc eritrocitario": "Erythrocyte Zinc",
}

def translate_parameters():
    """Translate remaining Spanish parameter names to English"""
    params_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'parameters.json')
    with open(params_path, 'r', encoding='utf-8') as f:
        parameters = json.load(f)
    
    updated_count = 0
    for spanish_name, param_data in parameters.items():
        english_name = param_data.get('english_name', '')
        
        # Check if translation is needed
        if english_name in TRANSLATIONS:
            new_english_name = TRANSLATIONS[english_name]
            if new_english_name != english_name:
                param_data['english_name'] = new_english_name
                updated_count += 1
                print(f"Updated {spanish_name}: {english_name} -> {new_english_name}")
        elif spanish_name in TRANSLATIONS:
            new_english_name = TRANSLATIONS[spanish_name]
            if new_english_name != english_name:
                param_data['english_name'] = new_english_name
                updated_count += 1
                print(f"Updated {spanish_name}: {english_name} -> {new_english_name}")
    
    # Save updated parameters.json
    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump(parameters, f, indent=2, ensure_ascii=False)
    
    print(f"\nUpdated {updated_count} parameters with English translations")

if __name__ == '__main__':
    translate_parameters()

"""
Translate Spanish result values to English
"""
from typing import Optional

# Translation dictionary for common Spanish result values
VALUE_TRANSLATIONS = {
    "negativo": "Negative",
    "negativa": "Negative",
    "positivo": "Positive",
    "positiva": "Positive",
    "se estud": "Under study",
    "se estudia": "Under study",
    "se estudió": "Studied",
    "ausente": "Absent",
    "presente": "Present",
    "normal": "Normal",
    "anormal": "Abnormal",
    "no detectado": "Not detected",
    "detectado": "Detected",
    "reactivo": "Reactive",
    "no reactivo": "Non-reactive",
    "indeterminado": "Indeterminate",
    "indeterminada": "Indeterminate",
    "indicio": "Trace",
    "no se observan elementos anormales": "Normal",
    "no se ob": "Normal",  # Truncated version
    "no se observa": "Normal",  # Partial match
    "se estudia la muestra de orina recibida no observándose en el examen realizado ningún resultado que indique la presencia de elementos anormales.": "Normal",
}

def translate_value(value: Optional[str]) -> Optional[str]:
    """
    Translate Spanish result values to English
    
    Args:
        value: The value to translate (can be None or empty)
    
    Returns:
        Translated value, or original value if no translation found
    """
    if not value:
        return value
    
    value_str = str(value).strip()
    if not value_str:
        return value
    
    value_lower = value_str.lower()
    
    # Check for exact match (case-insensitive)
    if value_lower in VALUE_TRANSLATIONS:
        return VALUE_TRANSLATIONS[value_lower]
    
    # Check for partial matches - try longest matches first
    sorted_translations = sorted(VALUE_TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True)
    
    for spanish, english in sorted_translations:
        # Check if value starts with Spanish word
        if value_lower.startswith(spanish):
            # Replace the Spanish part with English, preserving case of remaining text
            remaining = value_str[len(spanish):]
            return english + remaining
        # Check if value ends with Spanish word
        elif value_lower.endswith(spanish):
            remaining = value_str[:-len(spanish)]
            return remaining + english
        # Check if Spanish word is contained in value (for cases like "Se estud" from "Se estudia")
        elif spanish in value_lower:
            # Replace the Spanish part
            idx = value_lower.find(spanish)
            before = value_str[:idx]
            after = value_str[idx + len(spanish):]
            return before + english + after
    
    # If no translation found, return original
    return value_str

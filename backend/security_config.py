"""
Configuration de sécurité pour l'application
"""
import os
from typing import List, Optional

# Configuration CORS - Restreindre aux domaines autorisés
# Par défaut, autoriser localhost pour le développement
# En production, définir ALLOWED_ORIGINS dans les variables d'environnement
ALLOWED_ORIGINS = os.environ.get(
    'ALLOWED_ORIGINS',
    'http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000,http://127.0.0.1:3000'
).split(',')

# Configuration Rate Limiting
# Limites par défaut (peuvent être surchargées par variables d'environnement)
RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', '10'))
RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', '100'))
RATE_LIMIT_UPLOAD_PER_HOUR = int(os.environ.get('RATE_LIMIT_UPLOAD_PER_HOUR', '20'))

# Configuration d'authentification (optionnelle)
# Si API_KEY est défini, les endpoints sensibles nécessiteront un header X-API-Key
API_KEY = os.environ.get('API_KEY', None)
API_KEY_HEADER = 'X-API-Key'

# Configuration de logging sécurisé
# Si True, les données sensibles (noms de patients, métadonnées) ne seront pas loggées
SECURE_LOGGING = os.environ.get('SECURE_LOGGING', 'true').lower() == 'true'

# Configuration des headers de sécurité
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'",
    'Referrer-Policy': 'strict-origin-when-cross-origin'
}

# Validation des fichiers
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'csv', 'pdf'}
ALLOWED_MIME_TYPES = {
    'csv': ['text/csv', 'text/plain', 'application/csv'],
    'pdf': ['application/pdf']
}

# Magic bytes pour validation
PDF_MAGIC_BYTES = b'%PDF'
CSV_MIN_SIZE = 200  # bytes
PDF_MIN_SIZE = 1000  # bytes

def validate_api_key(request) -> bool:
    """
    Valide la clé API si elle est configurée
    Retourne True si l'authentification n'est pas requise ou si la clé est valide
    """
    if not API_KEY:
        return True  # Pas d'authentification requise
    
    provided_key = request.headers.get(API_KEY_HEADER)
    return provided_key == API_KEY

def sanitize_log_message(message: str) -> str:
    """
    Supprime les données sensibles des messages de log
    """
    if not SECURE_LOGGING:
        return message
    
    # Liste de mots-clés sensibles à masquer
    sensitive_keywords = [
        'patient', 'nom', 'name', 'birthdate', 'date_naissance',
        'sex', 'sexe', 'metadata', 'métadonnées', 'extracted_metadata'
    ]
    
    # Masquer les valeurs après les mots-clés sensibles
    sanitized = message
    import re
    for keyword in sensitive_keywords:
        # Pattern pour trouver et masquer les valeurs après le mot-clé
        # Échapper } dans f-string en utilisant }}
        pattern = rf'({keyword}[=:]\s*)([^\s,}}]+)'
        sanitized = re.sub(pattern, r'\1***REDACTED***', sanitized, flags=re.IGNORECASE)
    
    return sanitized

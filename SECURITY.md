# Guide de Sécurité

Ce document décrit les mesures de sécurité implémentées dans l'application de génération de rapports médicaux.

## 🔒 Mesures de Sécurité Implémentées

### 1. **Restriction CORS**
- Les requêtes cross-origin sont limitées aux domaines autorisés
- Par défaut, seuls `localhost:8000` et `localhost:3000` sont autorisés
- Configuration via variable d'environnement `ALLOWED_ORIGINS`

### 2. **Rate Limiting**
- Protection contre les attaques par déni de service (DoS)
- Limites par défaut :
  - 10 requêtes par minute
  - 100 requêtes par heure
  - 20 uploads par heure
- Configuration via variables d'environnement :
  - `RATE_LIMIT_PER_MINUTE`
  - `RATE_LIMIT_PER_HOUR`
  - `RATE_LIMIT_UPLOAD_PER_HOUR`

### 3. **Headers de Sécurité HTTP**
Les headers suivants sont ajoutés à toutes les réponses :
- `X-Content-Type-Options: nosniff` - Empêche le MIME-sniffing
- `X-Frame-Options: DENY` - Empêche le clickjacking
- `X-XSS-Protection: 1; mode=block` - Protection XSS
- `Strict-Transport-Security` - Force HTTPS (si configuré)
- `Content-Security-Policy` - Restreint les ressources chargées
- `Referrer-Policy` - Contrôle les informations de referrer

### 4. **Logging Sécurisé**
- Les données sensibles (noms de patients, métadonnées) sont automatiquement masquées dans les logs
- Activation/désactivation via `SECURE_LOGGING=true` (par défaut activé)

### 5. **Validation des Fichiers**
- Validation des types de fichiers (extension + magic bytes)
- Limitation de taille (10MB max)
- Validation du contenu (PDF doit commencer par `%PDF`)

### 6. **Authentification par API Key (Optionnelle)**
- Si `API_KEY` est défini dans les variables d'environnement, les endpoints sensibles nécessitent un header `X-API-Key`
- Actuellement désactivé par défaut (pour compatibilité)

## 🚀 Configuration

### Variables d'Environnement

```bash
# CORS - Liste des domaines autorisés (séparés par des virgules)
ALLOWED_ORIGINS=http://localhost:8000,https://votre-domaine.com

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_HOUR=100
RATE_LIMIT_UPLOAD_PER_HOUR=20

# Authentification (optionnelle)
API_KEY=votre-cle-secrete-ici

# Logging sécurisé
SECURE_LOGGING=true
```

### Exemple de Configuration Docker

```yaml
environment:
  - ALLOWED_ORIGINS=https://votre-domaine.com
  - RATE_LIMIT_PER_HOUR=50
  - API_KEY=${API_KEY}
  - SECURE_LOGGING=true
```

## 📋 Recommandations pour la Production

### 1. **HTTPS Obligatoire**
- Configurez un reverse proxy (nginx) avec certificat SSL/TLS
- Forcez HTTPS avec `Strict-Transport-Security`
- Redirigez toutes les requêtes HTTP vers HTTPS

### 2. **Rate Limiting avec Redis**
Pour une meilleure performance en production, utilisez Redis pour le rate limiting :

```python
# Dans security_config.py, modifier :
storage_uri = os.environ.get('REDIS_URL', 'redis://localhost:6379')
```

### 3. **Authentification Renforcée**
- Activez `API_KEY` pour protéger les endpoints
- Considérez l'implémentation d'un système d'authentification utilisateur (JWT, OAuth2)

### 4. **Chiffrement des Fichiers (Optionnel)**
> **Note importante** : Les fichiers sont **transitoires** et sont automatiquement supprimés après 1 heure d'inactivité. Le chiffrement au repos est donc **moins critique** dans ce contexte.
- **Priorité** : Le chiffrement **en transit** (HTTPS) est plus important que le chiffrement au repos
- Si vous avez des exigences de conformité strictes (HIPAA, GDPR), vous pouvez considérer :
  - Chiffrement des fichiers au repos (AES-256) pour les fichiers temporaires
  - Utilisation de volumes chiffrés au niveau du système de fichiers
  - Clés de chiffrement stockées de manière sécurisée (secrets manager)

### 5. **Audit Logging**
- Implémentez un système de logs d'audit pour tracer :
  - Qui a accédé à quels fichiers
  - Quand les fichiers ont été créés/supprimés
  - Les tentatives d'accès non autorisées

### 6. **Validation Renforcée**
- Ajoutez une validation antivirus pour les fichiers uploadés
- Implémentez une validation de signature pour les PDFs médicaux

### 7. **Isolation des Données**
- Utilisez des répertoires isolés avec permissions restrictives (déjà implémenté)
- Les fichiers temporaires sont automatiquement nettoyés après 1 heure d'inactivité
- Pour des exigences de conformité strictes, considérez l'utilisation de volumes chiffrés au niveau du système

## ⚠️ Limitations Actuelles

1. **Pas de chiffrement au repos** - Les fichiers sont stockés en clair (mais sont **transitoires** - supprimés après 1h)
2. **Pas d'authentification utilisateur** - Seule une API key optionnelle est disponible
3. **Rate limiting en mémoire** - En production, utilisez Redis pour une meilleure scalabilité
4. **Pas de validation antivirus** - Les fichiers uploadés ne sont pas scannés
5. **Pas d'audit logging complet** - Seuls les logs d'application sont disponibles

## 💡 Architecture de Sécurité pour Fichiers Transitoires

Étant donné que les fichiers sont **transitoires** (supprimés automatiquement après 1 heure), les priorités de sécurité sont :

### 🔴 **Critique** (À implémenter en priorité)
1. **HTTPS/TLS** - Chiffrement en transit (le plus important)
2. **Contrôle d'accès** - Authentification et autorisation
3. **Rate limiting** - Protection contre les abus (déjà implémenté)
4. **Validation des fichiers** - Protection contre les fichiers malveillants (déjà implémenté)

### 🟡 **Important** (Recommandé pour production)
1. **Logging sécurisé** - Masquer les données sensibles (déjà implémenté)
2. **Headers de sécurité** - Protection contre les attaques web (déjà implémenté)
3. **CORS restreint** - Limiter les domaines autorisés (déjà implémenté)
4. **Audit logging** - Traçabilité des accès

### 🟢 **Optionnel** (Selon exigences de conformité)
1. **Chiffrement au repos** - Moins critique pour fichiers transitoires
2. **Volumes chiffrés** - Au niveau système de fichiers
3. **Validation antivirus** - Pour fichiers uploadés

## 🔍 Vérification de la Sécurité

### Test des Headers de Sécurité
```bash
curl -I https://votre-domaine.com/api/health
```

### Test du Rate Limiting
```bash
# Faire plusieurs requêtes rapides
for i in {1..15}; do curl http://localhost:5000/api/health; done
# Les requêtes après la 10ème devraient être limitées
```

### Test CORS
```bash
curl -H "Origin: http://malicious-site.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: X-Requested-With" \
     -X OPTIONS \
     http://localhost:5000/api/upload
# Devrait être rejeté si le domaine n'est pas dans ALLOWED_ORIGINS
```

## 📞 Support

Pour toute question concernant la sécurité, contactez l'équipe de développement.

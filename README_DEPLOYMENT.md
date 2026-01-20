# Guide de déploiement Docker Compose

Ce guide explique comment déployer l'application Medical Report Generator sur un VPS Hostinger avec Docker Compose.

## Prérequis

- VPS Hostinger avec accès SSH
- Docker et Docker Compose installés
- Accès root ou utilisateur avec permissions sudo

## Installation

### 1. Cloner le repository

```bash
git clone <votre-repo-url>
cd report-generator
```

### 2. Configurer les variables d'environnement

```bash
cp .env.example .env
nano .env  # ou votre éditeur préféré
```

Les variables importantes :
- `FLASK_ENV=production`
- `UPLOAD_FOLDER=/app/uploads`
- `OUTPUT_FOLDER=/app/outputs`
- `CLEANUP_INTERVAL=60` (vérification toutes les 60 secondes)
- `FILE_TIMEOUT=600` (suppression après 10 minutes d'inactivité)

### 3. Créer les dossiers nécessaires

```bash
mkdir -p backend/uploads backend/outputs
touch backend/uploads/.gitkeep backend/outputs/.gitkeep
```

### 4. Déployer avec Docker Compose

```bash
# Construire les images
docker-compose build

# Démarrer les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f
```

### 5. Vérifier que tout fonctionne

```bash
# Vérifier le statut des conteneurs
docker-compose ps

# Tester le health check
curl http://localhost/api/health
```

## Gestion des services

### Commandes utiles

```bash
# Voir les logs
docker-compose logs -f

# Voir les logs d'un service spécifique
docker-compose logs -f backend
docker-compose logs -f nginx

# Redémarrer un service
docker-compose restart backend

# Arrêter tous les services
docker-compose down

# Arrêter et supprimer les volumes (ATTENTION: supprime les fichiers uploadés)
docker-compose down -v

# Reconstruire après modification du code
docker-compose up -d --build
```

## Configuration du domaine (plus tard)

Une fois le domaine configuré, vous devrez :

1. Modifier `nginx/default.conf` pour remplacer `server_name _;` par votre domaine
2. Configurer SSL avec Let's Encrypt (recommandé)
3. Redémarrer nginx : `docker-compose restart nginx`

## Nettoyage automatique des fichiers

Le système nettoie automatiquement les fichiers :

- **CSV uploadés** : Supprimés immédiatement après génération du PDF
- **PDF générés** : Supprimés immédiatement après téléchargement
- **Fichiers orphelins** : Supprimés automatiquement après 10 minutes d'inactivité

Le service de nettoyage vérifie les fichiers toutes les 60 secondes et supprime ceux qui n'ont pas eu d'activité depuis plus de 10 minutes.

## Dépannage

### Le backend ne démarre pas

```bash
# Vérifier les logs
docker-compose logs backend

# Vérifier que les ports ne sont pas déjà utilisés
netstat -tulpn | grep 5000
```

### Nginx ne sert pas le frontend

```bash
# Vérifier la configuration nginx
docker-compose exec nginx nginx -t

# Vérifier les logs nginx
docker-compose logs nginx
```

### Les fichiers ne sont pas supprimés

```bash
# Vérifier que le service de nettoyage fonctionne
docker-compose logs backend | grep cleanup

# Vérifier manuellement les fichiers
ls -la backend/uploads/
ls -la backend/outputs/
```

## Sécurité

- Les fichiers sont stockés temporairement et supprimés automatiquement
- Nginx limite la taille des uploads à 10MB
- Seuls les fichiers CSV sont acceptés
- Les fichiers ne sont accessibles que via les endpoints API

## Maintenance

### Mise à jour du code

```bash
git pull
docker-compose up -d --build
```

### Sauvegarde (si nécessaire)

Les fichiers sont temporaires et ne nécessitent généralement pas de sauvegarde. Si vous devez sauvegarder les configurations :

```bash
# Sauvegarder les fichiers de configuration
tar -czf config-backup.tar.gz backend/config/ .env
```

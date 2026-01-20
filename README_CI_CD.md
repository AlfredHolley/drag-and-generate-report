# Guide de déploiement automatique (CI/CD)

Ce guide explique comment configurer le déploiement automatique depuis GitHub vers votre VPS Hostinger.

## Vue d'ensemble

Quand vous poussez du code sur la branche `main` (ou `master`) de GitHub, le code sera automatiquement mis à jour sur votre VPS et les conteneurs Docker seront reconstruits et redémarrés.

## Configuration sur GitHub

### 1. Créer les secrets GitHub

Allez dans votre repository GitHub :
1. **Settings** → **Secrets and variables** → **Actions**
2. Cliquez sur **New repository secret**
3. Ajoutez les secrets suivants :

#### Secrets requis :

- **`VPS_HOST`** : L'adresse IP ou le domaine de votre VPS (ex: `123.456.789.0` ou `vps.example.com`)
- **`VPS_USER`** : Le nom d'utilisateur SSH (ex: `root` ou `deploy`)
- **`VPS_SSH_KEY`** : Votre clé SSH privée complète (voir section "Générer une clé SSH")
- **`VPS_PORT`** : Le port SSH (optionnel, défaut: `22`)
- **`VPS_PROJECT_PATH`** : Le chemin complet vers votre projet sur le VPS (ex: `/home/user/report-generator`)

### 2. Générer une clé SSH

Sur votre machine locale :

```bash
# Générer une nouvelle clé SSH (si vous n'en avez pas)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy

# Afficher la clé privée (à copier dans GitHub Secrets)
cat ~/.ssh/github_deploy

# Afficher la clé publique (à ajouter sur le VPS)
cat ~/.ssh/github_deploy.pub
```

### 3. Ajouter la clé publique sur le VPS

Sur votre VPS :

```bash
# Se connecter au VPS
ssh user@your-vps-ip

# Ajouter la clé publique au fichier authorized_keys
echo "VOTRE_CLE_PUBLIQUE_ICI" >> ~/.ssh/authorized_keys

# Vérifier les permissions
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

### 4. Vérifier la connexion SSH

Depuis votre machine locale :

```bash
ssh -i ~/.ssh/github_deploy user@your-vps-ip
```

Si la connexion fonctionne, vous pouvez continuer.

## Configuration sur le VPS

### 1. Cloner le repository (si pas déjà fait)

```bash
cd /home/user  # ou votre répertoire préféré
git clone <votre-repo-url> report-generator
cd report-generator
```

### 2. Configurer le projet

```bash
# Créer le fichier .env
cp .env.example .env
nano .env  # Configurer selon vos besoins

# Créer les dossiers nécessaires
mkdir -p backend/uploads backend/outputs
touch backend/uploads/.gitkeep backend/outputs/.gitkeep

# Rendre le script exécutable
chmod +x scripts/update.sh
```

### 3. Premier déploiement manuel

```bash
# Déployer une première fois manuellement
./scripts/deploy.sh
```

## Utilisation

### Déploiement automatique

Une fois configuré, chaque push sur la branche `main` déclenchera automatiquement :

1. ✅ Pull du code depuis GitHub
2. ✅ Rebuild des images Docker
3. ✅ Redémarrage des conteneurs
4. ✅ Vérification de santé

### Déploiement manuel

Vous pouvez aussi déclencher un déploiement manuellement depuis GitHub :

1. Allez dans **Actions** dans votre repository
2. Sélectionnez **Deploy to VPS**
3. Cliquez sur **Run workflow**
4. Sélectionnez la branche et cliquez sur **Run workflow**

### Vérifier les déploiements

Sur GitHub :
- Allez dans **Actions** pour voir l'historique des déploiements
- Cliquez sur un workflow pour voir les logs détaillés

Sur le VPS :
```bash
# Voir les logs des conteneurs
docker-compose logs -f

# Vérifier le statut
docker-compose ps

# Voir les dernières modifications Git
cd /path/to/report-generator
git log --oneline -5
```

## Dépannage

### Le déploiement échoue

1. **Vérifier les secrets GitHub** :
   - Assurez-vous que tous les secrets sont correctement configurés
   - Vérifiez qu'il n'y a pas d'espaces en début/fin de ligne dans les secrets

2. **Vérifier la connexion SSH** :
   ```bash
   # Tester depuis votre machine locale
   ssh -i ~/.ssh/github_deploy user@your-vps-ip
   ```

3. **Vérifier les permissions** :
   ```bash
   # Sur le VPS
   ls -la scripts/update.sh
   # Doit être exécutable: -rwxr-xr-x
   ```

4. **Vérifier le chemin du projet** :
   ```bash
   # Sur le VPS, vérifier que le chemin dans VPS_PROJECT_PATH existe
   ls -la $VPS_PROJECT_PATH
   ```

### Les conteneurs ne redémarrent pas

```bash
# Vérifier les logs
docker-compose logs backend
docker-compose logs nginx

# Redémarrer manuellement
docker-compose restart
```

### Le script update.sh ne fonctionne pas

```bash
# Tester le script manuellement sur le VPS
cd /path/to/report-generator
bash scripts/update.sh

# Vérifier les erreurs
```

## Sécurité

### Bonnes pratiques

1. **Utilisez un utilisateur dédié** (pas root) :
   ```bash
   # Créer un utilisateur déploy
   adduser deploy
   usermod -aG docker deploy
   ```

2. **Limitez les permissions SSH** :
   - Utilisez une clé SSH dédiée uniquement pour le déploiement
   - Ne partagez jamais votre clé privée

3. **Protégez le fichier .env** :
   - Ne commitez jamais `.env` dans Git
   - Utilisez `.env.example` comme template

4. **Surveillez les logs** :
   ```bash
   # Voir les tentatives de connexion SSH
   tail -f /var/log/auth.log
   ```

## Workflow alternatif (si GitHub Actions ne fonctionne pas)

Si vous préférez utiliser un webhook GitHub au lieu de GitHub Actions :

1. Créer un endpoint webhook dans `backend/app.py`
2. Configurer un webhook GitHub qui appelle cet endpoint
3. L'endpoint exécute le script `update.sh`

Cette méthode nécessite que votre VPS soit accessible publiquement et que vous configuriez un secret webhook pour la sécurité.

## Commandes utiles

```bash
# Voir l'historique des déploiements GitHub Actions
# (depuis l'interface GitHub → Actions)

# Voir les logs du dernier déploiement sur le VPS
cd /path/to/report-generator
git log --oneline -5

# Vérifier que le code est à jour
git status

# Forcer une mise à jour manuelle
git pull origin main
docker-compose up -d --build
```

# Guide pour lancer l'application localement

## Prérequis

- Python 3.11 ou supérieur
- pip (gestionnaire de paquets Python)

## Étapes pour lancer l'application

### 1. Installer les dépendances Python

```bash
# Depuis la racine du projet
cd backend
pip install -r requirements.txt
```

**Note pour Windows** : Si vous avez des problèmes avec `svglib` (dépendance optionnelle pour le logo SVG), vous pouvez l'ignorer. L'application fonctionnera sans, mais le logo pourrait ne pas s'afficher dans le PDF.

### 2. Vérifier que les polices sont présentes

Assurez-vous que le dossier `fonts/` existe à la racine du projet et contient :
- VistaSansOT-Book.ttf
- VistaSansOT-Bold.ttf
- VistaSansOT-BookItalic.ttf
- VistaSansOT-Light.ttf
- VistaSansOT-LightItalic.ttf
- VistaSansOT-Reg.ttf
- Calibri.ttf
- Calibri-Bold.ttf

### 3. Vérifier que le logo est présent

Assurez-vous que `logo_bw.svg` existe à la racine du projet.

### 4. Lancer le backend Flask

```bash
# Depuis le dossier backend
cd backend
python app.py
```

Le backend devrait démarrer sur `http://localhost:5000`

### 5. Servir le frontend

Ouvrez un **nouveau terminal** et servez le frontend avec un serveur HTTP simple :

**Option A - Avec Python** :
```bash
# Depuis la racine du projet
cd frontend
python -m http.server 8000
```

**Option B - Avec Node.js** (si installé) :
```bash
# Depuis la racine du projet
cd frontend
npx http-server -p 8000
```

**Option C - Ouvrir directement dans le navigateur** :
- Ouvrez `frontend/index.html` directement dans votre navigateur
- ⚠️ **Note** : Cette méthode peut avoir des limitations CORS. Il est préférable d'utiliser un serveur HTTP.

### 6. Accéder à l'application

Ouvrez votre navigateur et allez sur : `http://localhost:8000`

## Structure des dossiers

```
report-generator/
├── backend/
│   ├── app.py              # Point d'entrée Flask
│   ├── requirements.txt    # Dépendances Python
│   ├── uploads/            # Fichiers CSV uploadés (créé automatiquement)
│   └── outputs/            # PDFs générés (créé automatiquement)
├── frontend/
│   ├── index.html          # Page principale
│   ├── app.js              # Logique JavaScript
│   ├── styles.css          # Styles CSS
│   └── logo_bw.svg         # Logo pour le footer
├── fonts/                  # Polices TTF
└── logo_bw.svg             # Logo pour le PDF
```

## Dépannage

### Le backend ne démarre pas

- Vérifiez que Python 3.11+ est installé : `python --version`
- Vérifiez que toutes les dépendances sont installées : `pip list`
- Vérifiez les logs dans le terminal pour voir les erreurs

### Le logo n'apparaît pas dans le PDF

- Vérifiez que `logo_bw.svg` existe à la racine du projet
- Vérifiez les logs du backend pour voir si le logo est trouvé
- Si `svglib` n'est pas installé, le logo pourrait ne pas fonctionner

### Le logo n'apparaît pas dans le footer du site

- Vérifiez que `frontend/logo_bw.svg` existe
- Ouvrez la console du navigateur (F12) pour voir les erreurs
- Vérifiez que vous servez le frontend avec un serveur HTTP (pas juste en ouvrant le fichier HTML)

### Erreur "Undefined font"

- Vérifiez que le dossier `fonts/` existe et contient tous les fichiers TTF nécessaires
- Vérifiez les logs du backend pour voir quelles polices sont enregistrées

### CORS errors

- Assurez-vous que le backend Flask est bien lancé sur `http://localhost:5000`
- Vérifiez que `flask-cors` est installé : `pip show flask-cors`
- Le frontend devrait automatiquement détecter `localhost` et utiliser `http://localhost:5000/api`

## Test rapide

1. Lancez le backend : `cd backend && python app.py`
2. Dans un autre terminal, servez le frontend : `cd frontend && python -m http.server 8000`
3. Ouvrez `http://localhost:8000` dans votre navigateur
4. Glissez-déposez un fichier CSV (par exemple `data.csv` ou `data_short.csv`)
5. Remplissez le formulaire de métadonnées patient
6. Téléchargez le PDF généré

## Arrêter l'application

- **Backend** : Appuyez sur `Ctrl+C` dans le terminal où Flask tourne
- **Frontend** : Appuyez sur `Ctrl+C` dans le terminal où le serveur HTTP tourne

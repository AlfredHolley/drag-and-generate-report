"""
Report Generator — Backend Flask
Endpoint principal : POST /api/convert
  - Reçoit un fichier XLSX/XLS
  - Le convertit en CSV (première feuille par défaut)
  - Retourne le CSV avec des headers informatifs
"""

import os
import io
import json
import pandas as pd
from flask import Flask, request, Response, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pdf_generator.microbiome_pdf import generate_microbiome_pdf

# Le dossier frontend est un niveau au-dessus du backend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# ── Configuration ────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Sert l'interface frontend."""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """Endpoint de vérification de l'état du serveur."""
    return jsonify({'status': 'ok', 'service': 'report-generator'})


@app.route('/api/convert', methods=['POST'])
def convert_xlsx_to_csv():
    """
    Convertit un fichier XLSX/XLS en CSV.

    Body (multipart/form-data):
        file        : Le fichier Excel à convertir
        sheet_name  : (optionnel) Nom ou index (0-based) de la feuille à utiliser.
                      Par défaut : première feuille.

    Réponse :
        text/csv — contenu CSV
        Headers personnalisés :
            X-Row-Count   : nombre de lignes de données
            X-Col-Count   : nombre de colonnes
            X-Sheet-Name  : nom de la feuille convertie
    """
    # ── Validation du fichier ────────────────────────────────────────────────
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni (clé "file" manquante)'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporté. Utilisez .xlsx ou .xls'}), 400

    # ── Lecture de la feuille demandée ───────────────────────────────────────
    sheet_param = request.form.get('sheet_name', 0)
    # Convertit en int si c'est un nombre
    try:
        sheet_param = int(sheet_param)
    except (ValueError, TypeError):
        pass  # On garde la valeur string (nom de feuille)

    # ── Conversion ───────────────────────────────────────────────────────────
    try:
        file_bytes = file.read()
        xl_file = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')

        # Résoudre le nom de feuille
        if isinstance(sheet_param, int):
            if sheet_param >= len(xl_file.sheet_names):
                return jsonify({
                    'error': f'Index de feuille {sheet_param} hors limites '
                             f'(le fichier contient {len(xl_file.sheet_names)} feuille(s))'
                }), 400
            sheet_name = xl_file.sheet_names[sheet_param]
        else:
            if sheet_param not in xl_file.sheet_names:
                return jsonify({
                    'error': f'Feuille "{sheet_param}" introuvable. '
                             f'Feuilles disponibles : {xl_file.sheet_names}'
                }), 400
            sheet_name = sheet_param

        df = xl_file.parse(sheet_name)

        # Statistiques
        row_count = len(df)
        col_count = len(df.columns)

        # Sérialisation CSV en mémoire
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8')
        csv_content = csv_buffer.getvalue()

        # Réponse avec headers informatifs
        response = Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{secure_filename(file.filename).rsplit(".", 1)[0]}.csv"',
                'X-Row-Count': str(row_count),
                'X-Col-Count': str(col_count),
                'X-Sheet-Name': sheet_name,
                'X-Sheet-Names': ','.join(xl_file.sheet_names),
                'Access-Control-Expose-Headers': 'X-Row-Count, X-Col-Count, X-Sheet-Name, X-Sheet-Names',
            }
        )
        return response

    except Exception as e:
        return jsonify({'error': f'Erreur lors de la conversion : {str(e)}'}), 500


@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    """
    Convertit un fichier XLSX/XLS en rapport PDF microbiome.

    Body (multipart/form-data):
        file        : Le fichier Excel à convertir
        sheet_name  : (optionnel) Nom ou index (0-based) de la feuille.

    Réponse :
        application/pdf — contenu du PDF
        Headers :
            Content-Disposition : attachment; filename="<nom>.pdf"
            X-Patient-Name      : nom du patient extrait du fichier
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni (clé "file" manquante)'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Nom de fichier vide'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporté. Utilisez .xlsx ou .xls'}), 400

    sheet_param = request.form.get('sheet_name', 0)
    try:
        sheet_param = int(sheet_param)
    except (ValueError, TypeError):
        pass

    try:
        file_bytes = file.read()
        xl_file = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')

        if isinstance(sheet_param, int):
            if sheet_param >= len(xl_file.sheet_names):
                return jsonify({
                    'error': f'Index de feuille {sheet_param} hors limites '
                             f'(le fichier contient {len(xl_file.sheet_names)} feuille(s))'
                }), 400
            sheet_name = xl_file.sheet_names[sheet_param]
        else:
            if sheet_param not in xl_file.sheet_names:
                return jsonify({
                    'error': f'Feuille "{sheet_param}" introuvable. '
                             f'Feuilles disponibles : {xl_file.sheet_names}'
                }), 400
            sheet_name = sheet_param

        df = xl_file.parse(sheet_name)

        # Doctor comments: optional JSON string  {pageNumber: "comment text", …}
        comments_raw = request.form.get('comments', '{}')
        try:
            comments = json.loads(comments_raw)
        except Exception:
            comments = {}

        # Génération du PDF
        pdf_bytes = generate_microbiome_pdf(df, comments=comments)

        # Nom de fichier de sortie
        base_name = secure_filename(file.filename).rsplit('.', 1)[0]
        patient_name = ''
        if 'DescripcionMuestra' in df.columns:
            v = df['DescripcionMuestra'].iloc[0]
            if not pd.isna(v):
                patient_name = str(v).strip()

        response = Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{base_name}_report.pdf"',
                'X-Patient-Name': patient_name,
                'Access-Control-Expose-Headers': 'X-Patient-Name',
            }
        )
        return response

    except Exception as e:
        return jsonify({'error': f'Erreur lors de la génération du PDF : {str(e)}'}), 500


@app.route('/api/sheets', methods=['POST'])
def list_sheets():
    """
    Retourne la liste des feuilles d'un fichier XLSX sans le convertir.

    Body (multipart/form-data):
        file : Le fichier Excel
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier fourni'}), 400

    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporté'}), 400

    try:
        file_bytes = file.read()
        xl_file = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')
        return jsonify({
            'sheets': xl_file.sheet_names,
            'count': len(xl_file.sheet_names)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Lancement ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

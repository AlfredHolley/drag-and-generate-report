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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from pdf_generator.microbiome_pdf  import generate_microbiome_pdf, MicrobiomePDFGenerator
from pdf_generator.microbiome_docx import generate_microbiome_docx

# ── Security configuration ────────────────────────────────────────────────────
from security_config import (
    ALLOWED_ORIGINS,
    SECURITY_HEADERS,
    RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_UPLOAD_PER_HOUR,
    API_KEY,
    validate_api_key,
    sanitize_log_message,
)

# Le dossier frontend est un niveau au-dessus du backend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')
# Fonts shared between the PDF generator and the web UI
_BASE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_BASE, '..', 'fonts') if os.path.isdir(
    os.path.join(_BASE, '..', 'fonts')) else '/app/fonts'

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')

# ── CORS — restricted to configured origins ───────────────────────────────────
CORS(app, origins=ALLOWED_ORIGINS)

# ── Rate limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[
        f"{RATE_LIMIT_PER_HOUR} per hour",
        f"{RATE_LIMIT_PER_MINUTE} per minute",
    ],
    storage_uri=os.environ.get('REDIS_URL', 'memory://'),
)

# ── Security headers on every response ───────────────────────────────────────
@app.after_request
def add_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response

# ── Optional API key protection on all /api/ endpoints ───────────────────────
@app.before_request
def check_api_key():
    """If API_KEY is set, every /api/ call (except /api/health) must carry
    the correct X-Api-Key header."""
    if not request.path.startswith('/api/'):
        return  # static files, fonts — not protected
    if request.path == '/api/health':
        return  # health check always public
    if not validate_api_key(request):
        return jsonify({'error': 'Unauthorized — missing or invalid API key'}), 401

# ── Configuration ─────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/fonts/<path:filename>')
def serve_font(filename):
    """Serve font files from the shared fonts/ directory."""
    return send_from_directory(FONTS_DIR, filename)


@app.route('/')
def index():
    """Sert l'interface frontend."""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """Endpoint de vérification de l'état du serveur."""
    return jsonify({'status': 'ok', 'service': 'report-generator'})


@app.route('/api/convert', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_UPLOAD_PER_HOUR} per hour")
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


@app.route('/api/parameters', methods=['POST'])
def list_parameters():
    """
    Return the list of unique parameter names present in an XLSX/XLS file.

    Body (multipart/form-data):
        file        : The Excel file
        sheet_name  : (optional) Sheet index or name (default: first sheet)

    Response:
        JSON  {"parameters": ["...", ...]}   — sorted alphabetically
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported format. Use .xlsx or .xls'}), 400

    sheet_param = request.form.get('sheet_name', 0)
    try:
        sheet_param = int(sheet_param)
    except (ValueError, TypeError):
        pass

    try:
        file_bytes = file.read()
        xl_file    = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')

        if isinstance(sheet_param, int):
            sheet_name = xl_file.sheet_names[min(sheet_param, len(xl_file.sheet_names) - 1)]
        else:
            sheet_name = sheet_param if sheet_param in xl_file.sheet_names else xl_file.sheet_names[0]

        df     = xl_file.parse(sheet_name)
        params = MicrobiomePDFGenerator.extract_parameters(df)
        return jsonify({'parameters': params, 'count': len(params)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-pdf', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_UPLOAD_PER_HOUR} per hour")
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

        # Extract @[Parameter Name] citations from all comment texts
        import re as _re
        cited_params: set = set()
        for text in comments.values():
            for match in _re.findall(r'@\[([^\]]+)\]', str(text)):
                cited_params.add(match.strip())

        # Génération du PDF
        pdf_bytes = generate_microbiome_pdf(df, comments=comments,
                                            cited_params=cited_params or None)

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


@app.route('/api/generate-docx', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_UPLOAD_PER_HOUR} per hour")
def generate_docx():
    """
    Convert an XLSX/XLS file to a microbiome Word (.docx) report.

    Body (multipart/form-data):
        file        : The Excel file
        sheet_name  : (optional) Sheet index or name
        comments    : (optional) JSON string  {pageNumber: "comment text", …}

    Response:
        application/vnd.openxmlformats-officedocument.wordprocessingml.document
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported format. Use .xlsx or .xls'}), 400

    sheet_param = request.form.get('sheet_name', 0)
    try:
        sheet_param = int(sheet_param)
    except (ValueError, TypeError):
        pass

    try:
        file_bytes = file.read()
        xl_file    = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')

        if isinstance(sheet_param, int):
            if sheet_param >= len(xl_file.sheet_names):
                return jsonify({'error': f'Sheet index {sheet_param} out of range'}), 400
            sheet_name = xl_file.sheet_names[sheet_param]
        else:
            if sheet_param not in xl_file.sheet_names:
                return jsonify({'error': f'Sheet "{sheet_param}" not found'}), 400
            sheet_name = sheet_param

        df = xl_file.parse(sheet_name)

        # Optional doctor comments
        comments_raw = request.form.get('comments', '{}')
        try:
            comments = json.loads(comments_raw)
        except Exception:
            comments = {}

        import re as _re
        cited_params: set = set()
        for text in comments.values():
            for match in _re.findall(r'@\[([^\]]+)\]', str(text)):
                cited_params.add(match.strip())

        docx_bytes = generate_microbiome_docx(df, comments=comments,
                                              cited_params=cited_params or None)

        base_name    = secure_filename(file.filename).rsplit('.', 1)[0]
        patient_name = ''
        if 'DescripcionMuestra' in df.columns:
            v = df['DescripcionMuestra'].iloc[0]
            if not pd.isna(v):
                patient_name = str(v).strip()

        return Response(
            docx_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={
                'Content-Disposition': f'attachment; filename="{base_name}_report.docx"',
                'X-Patient-Name': patient_name,
                'Access-Control-Expose-Headers': 'X-Patient-Name',
            }
        )

    except Exception as e:
        return jsonify({'error': f'DOCX generation error: {str(e)}'}), 500


@app.route('/api/alarmed-parameters', methods=['POST'])
def list_alarmed_parameters():
    """
    Return out-of-norm parameters grouped by section → subsection.

    Body (multipart/form-data):
        file       : The Excel file
        sheet_name : (optional) Sheet index or name

    Response:
        JSON { "sections": [...], "total": N }
        Each section: { "name": str, "subsections": [{ "name": str|null, "params": [...] }] }
        Each param:   { "name": str, "result": str, "unit": str, "ref": str }
    """
    import re as _re2
    from collections import OrderedDict
    from pdf_generator.microbiome_pdf import SUBSECTION_MAP

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported format. Use .xlsx or .xls'}), 400

    sheet_param = request.form.get('sheet_name', 0)
    try:
        sheet_param = int(sheet_param)
    except (ValueError, TypeError):
        pass

    try:
        file_bytes = file.read()
        xl_file    = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')
        if isinstance(sheet_param, int):
            sheet_name = xl_file.sheet_names[min(sheet_param, len(xl_file.sheet_names) - 1)]
        else:
            sheet_name = sheet_param if sheet_param in xl_file.sheet_names else xl_file.sheet_names[0]
        df = xl_file.parse(sheet_name)

        # ── Helper functions ─────────────────────────────────────────────────
        def _cp(val):
            s = str(val).strip()
            return '' if s in ('', 'nan', 'None') else _re2.sub(r'\s*\[[^\[\]]+\]\s*$', '', s).strip()

        def _cv(val):
            s = str(val).strip()
            return '' if s in ('', 'nan', 'None') else s

        def _res(row):
            r1 = _cv(row.get('Resultado1', ''))
            r2 = _cv(row.get('Resultado2', ''))
            return r1 or (r2[:40] + ('…' if len(r2) > 40 else '') if r2 else '—')

        def _ref(row):
            hi = _cv(row.get('VRMaximo', '')).replace(',', '.')
            lo = _cv(row.get('VRMinimo', '')).replace(',', '.')
            if lo and hi: return f'{lo} – {hi}'
            if hi:        return f'< {hi}'
            if lo:        return f'> {lo}'
            return '—'

        def _alarmed(row):
            return str(row.get('Alarma', 'Falso')).strip() == 'Verdadero'

        # ── Build hierarchical alarmed list ─────────────────────────────────
        result_sections = []
        total = 0

        for section in df['TipoInforme'].unique():
            sec_df      = df[df['TipoInforme'] == section]
            subs_def    = SUBSECTION_MAP.get(section, [])
            sec_entry   = {'name': str(section), 'subsections': []}

            if subs_def:
                trigger_to_idx: dict = {}
                for si, (title, _, triggers) in enumerate(subs_def):
                    if isinstance(triggers, str):
                        triggers = [triggers]
                    for t in triggers:
                        trigger_to_idx[t] = si
                sub_meta = {i: title for i, (title, _, _) in enumerate(subs_def)}

                pre_rows:        list = []
                row_assignments: list = []
                cur_idx               = None

                for _, row in sec_df.iterrows():
                    cleaned = _cp(row.get('Ensayo', ''))
                    if cleaned in trigger_to_idx:
                        cur_idx = trigger_to_idx[cleaned]
                    if cur_idx is None:
                        pre_rows.append(row.name)
                    else:
                        row_assignments.append((cur_idx, row.name))

                merged: OrderedDict = OrderedDict()
                for si, ridx in row_assignments:
                    merged.setdefault(si, []).append(ridx)
                if pre_rows and merged:
                    first_key = next(iter(merged))
                    merged[first_key] = pre_rows + merged[first_key]

                for si, indices in sorted(merged.items()):
                    sub_df = sec_df.loc[indices]
                    params = [
                        {'name': _cp(r.get('Ensayo', '')).lstrip('- ').strip(),
                         'result': _res(r),
                         'unit': _cv(r.get('Unidad1', '')),
                         'ref': _ref(r)}
                        for _, r in sub_df.iterrows()
                        if _alarmed(r) and _cp(r.get('Ensayo', '')).lstrip('- ').strip()
                    ]
                    if params:
                        sec_entry['subsections'].append(
                            {'name': sub_meta.get(si, ''), 'params': params})
                        total += len(params)
            else:
                params = [
                    {'name': _cp(r.get('Ensayo', '')).lstrip('- ').strip(),
                     'result': _res(r),
                     'unit': _cv(r.get('Unidad1', '')),
                     'ref': _ref(r)}
                    for _, r in sec_df.iterrows()
                    if _alarmed(r) and _cp(r.get('Ensayo', '')).lstrip('- ').strip()
                ]
                if params:
                    sec_entry['subsections'].append({'name': None, 'params': params})
                    total += len(params)

            if sec_entry['subsections']:
                result_sections.append(sec_entry)

        return jsonify({'sections': result_sections, 'total': total})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    _debug = os.environ.get('FLASK_ENV', 'development') != 'production'
    app.run(debug=_debug, host='0.0.0.0', port=5000)

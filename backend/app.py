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
import time
import uuid
import urllib.request as _urllib_req
import re as _re
import pandas as pd
from flask import Flask, request, Response, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pdf_generator.microbiome_pdf  import generate_microbiome_pdf, MicrobiomePDFGenerator
from pdf_generator.microbiome_docx import generate_microbiome_docx

# Le dossier frontend est un niveau au-dessus du backend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')
# Fonts shared between the PDF generator and the web UI
_BASE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_BASE, '..', 'fonts') if os.path.isdir(
    os.path.join(_BASE, '..', 'fonts')) else '/app/fonts'

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)

# ── Configuration ────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ── OnlyOffice configuration ──────────────────────────────────────────────────
# URL the browser uses to load the OnlyOffice editor UI
# Local dev : http://localhost:8080  |  Prod : https://office.yourdomain.com
ONLYOFFICE_URL         = os.environ.get('ONLYOFFICE_URL', 'http://localhost:8080')
# URL the OnlyOffice *server* (Docker container) uses to reach this Flask backend
# In Docker this is always the internal network name
ONLYOFFICE_BACKEND_URL = os.environ.get('ONLYOFFICE_BACKEND_URL', 'http://backend:5000')
# JWT secret shared with the OnlyOffice container (set JWT_ENABLED=true in compose)
ONLYOFFICE_JWT_SECRET  = os.environ.get('ONLYOFFICE_JWT_SECRET', '')

# In-memory editing sessions { key: {bytes, filename, patient_name, created} }
_oo_sessions: dict = {}
_OO_SESSION_TTL = 3600  # seconds


def _oo_sign(payload: dict) -> str:
    """Return a JWT token for the OnlyOffice editor config, or '' if JWT is disabled."""
    if not ONLYOFFICE_JWT_SECRET:
        return ''
    try:
        import jwt as _jwt  # PyJWT
        return _jwt.encode(payload, ONLYOFFICE_JWT_SECRET, algorithm='HS256')
    except Exception:
        return ''


def _oo_cleanup() -> None:
    """Lazily remove expired editing sessions."""
    now = time.time()
    expired = [k for k, v in _oo_sessions.items() if now - v['created'] > _OO_SESSION_TTL]
    for k in expired:
        del _oo_sessions[k]


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


# ── OnlyOffice editing endpoints ─────────────────────────────────────────────

@app.route('/api/office/session', methods=['POST'])
def office_create_session():
    """
    Generate a DOCX and open an OnlyOffice editing session.

    Returns the complete DocsAPI.DocEditor config so the frontend can
    load the editor without knowing internal URLs.
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

        df = xl_file.parse(sheet_name)

        comments_raw = request.form.get('comments', '{}')
        try:
            comments = json.loads(comments_raw)
        except Exception:
            comments = {}

        cited_params: set = set()
        for text in comments.values():
            for match in _re.findall(r'@\[([^\]]+)\]', str(text)):
                cited_params.add(match.strip())

        docx_bytes = generate_microbiome_docx(df, comments=comments,
                                              cited_params=cited_params or None)

        # Sanity-check: DOCX is a ZIP — first bytes must be PK\x03\x04
        if not docx_bytes or docx_bytes[:4] != b'PK\x03\x04':
            app.logger.error(
                f'[office/session] DOCX generation produced invalid bytes '
                f'(size={len(docx_bytes) if docx_bytes else 0}, '
                f'magic={docx_bytes[:4] if docx_bytes else b""})'
            )
            return jsonify({'error': 'DOCX generation failed (invalid output)'}), 500

        app.logger.info(
            f'[office/session] DOCX generated OK ({len(docx_bytes):,} bytes) '
            f'magic={docx_bytes[:4]!r}'
        )
        app.logger.info(f'[office/session] backend_url={ONLYOFFICE_BACKEND_URL}')

        # Patient name for display
        patient_name = ''
        if 'DescripcionMuestra' in df.columns:
            v = df['DescripcionMuestra'].iloc[0]
            if not pd.isna(v):
                patient_name = str(v).strip()

        base_name = secure_filename(file.filename).rsplit('.', 1)[0]
        filename  = f'{base_name}_report.docx'

        # Store session
        key = str(uuid.uuid4())
        _oo_cleanup()
        _oo_sessions[key] = {
            'bytes':        docx_bytes,
            'filename':     filename,
            'patient_name': patient_name,
            'created':      time.time(),
        }

        # Build OnlyOffice editor config
        # IMPORTANT: URL must end with .docx so OnlyOffice can detect the file type
        doc_url      = f'{ONLYOFFICE_BACKEND_URL}/api/office/doc/{key}/{filename}'
        callback_url = f'{ONLYOFFICE_BACKEND_URL}/api/office/callback/{key}'

        oo_config = {
            'document': {
                'fileType': 'docx',
                'key':      key,
                'title':    filename,
                'url':      doc_url,
            },
            'editorConfig': {
                'callbackUrl': callback_url,
                'mode':        'edit',
                'lang':        'en',
                'user':        {'id': 'doctor-1', 'name': patient_name or 'Doctor'},
                'customization': {
                    'autosave':   True,
                    'forcesave':  False,
                    'chat':       False,
                    'toolbar':    True,
                    'statusBar':  True,
                    'header':     False,
                },
            },
            'documentType': 'word',
            'height': '100%',
            'width':  '100%',
        }

        # Sign config with JWT if a secret is configured
        token = _oo_sign(oo_config)
        if token:
            oo_config['token'] = token

        return jsonify({
            'key':           key,
            'filename':      filename,
            'oo_config':     oo_config,
            'download_url':  f'/api/office/download/{key}',
            'onlyoffice_url': ONLYOFFICE_URL,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/office/doc/<key>/<filename>', methods=['GET'])
@app.route('/api/office/doc/<key>', methods=['GET'])          # backward-compat
def office_get_doc(key, filename=None):
    """
    Serve the DOCX file to the OnlyOffice Document Server.
    The URL intentionally ends with .docx so OnlyOffice can detect the file type
    from the extension (required by OnlyOffice ≥ 7.x).
    """
    remote = request.remote_addr
    ua     = request.headers.get('User-Agent', '')[:80]
    auth   = request.headers.get('Authorization', '')[:60]
    app.logger.info(
        f'[office/doc] GET key={key} fname={filename} '
        f'from={remote} ua={ua!r} auth={auth!r}'
    )
    app.logger.info(f'[office/doc] active sessions: {list(_oo_sessions.keys())}')

    session = _oo_sessions.get(key)
    if not session:
        app.logger.error(f'[office/doc] SESSION NOT FOUND for key={key}')
        return jsonify({'error': 'Session not found or expired'}), 404

    docx_bytes = session['bytes']
    fname = filename or session['filename']
    app.logger.info(
        f'[office/doc] serving {fname} ({len(docx_bytes):,} bytes) '
        f'magic={docx_bytes[:4]!r}'
    )
    return Response(
        docx_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition': f'inline; filename="{fname}"'},
    )


@app.route('/api/office/sessions-debug', methods=['GET'])
def office_sessions_debug():
    """Debug endpoint: list active OnlyOffice sessions (no secrets)."""
    now = time.time()
    return jsonify({
        'count': len(_oo_sessions),
        'sessions': [
            {
                'key': k,
                'filename': v['filename'],
                'size': len(v['bytes']),
                'magic': v['bytes'][:4].hex(),
                'age_s': round(now - v['created']),
            }
            for k, v in _oo_sessions.items()
        ]
    })


@app.route('/api/office/callback/<key>', methods=['POST'])
def office_callback(key):
    """
    OnlyOffice callback — called by the Document Server when the document is saved.
    status 1 = editing  |  2 = ready for save  |  3 = error  |  4 = closed  |  6 = forcesave
    """
    data   = request.get_json(silent=True) or {}
    status = data.get('status', 0)
    app.logger.info(
        f'[office/callback] key={key} status={status} '
        f'url={data.get("url", "")!r} '
        f'full={data}'
    )

    if status in (2, 6):
        download_url = data.get('url', '')
        if download_url and key in _oo_sessions:
            try:
                with _urllib_req.urlopen(download_url, timeout=30) as resp:
                    updated = resp.read()
                _oo_sessions[key]['bytes'] = updated
            except Exception as e:
                return jsonify({'error': 1, 'message': str(e)}), 500

    return jsonify({'error': 0})


@app.route('/api/office/download/<key>', methods=['GET'])
def office_download(key):
    """Download the (potentially edited) DOCX from an OnlyOffice session."""
    session = _oo_sessions.get(key)
    if not session:
        return jsonify({'error': 'Session not found or expired'}), 404
    return Response(
        session['bytes'],
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f'attachment; filename="{session["filename"]}"',
            'X-Patient-Name':      session.get('patient_name', ''),
            'Access-Control-Expose-Headers': 'X-Patient-Name',
        },
    )


# ── Lancement ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

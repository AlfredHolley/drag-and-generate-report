from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import sys
import uuid
import tempfile
from werkzeug.utils import secure_filename
import json
import time

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import security configuration
try:
    from security_config import (
        ALLOWED_ORIGINS, RATE_LIMIT_PER_MINUTE, RATE_LIMIT_PER_HOUR,
        RATE_LIMIT_UPLOAD_PER_HOUR, API_KEY, validate_api_key,
        sanitize_log_message, SECURITY_HEADERS
    )
except ImportError:
    # Fallback si le module de sécurité n'est pas disponible
    ALLOWED_ORIGINS = ['http://localhost:8000', 'http://localhost:3000']
    RATE_LIMIT_PER_MINUTE = 10
    RATE_LIMIT_PER_HOUR = 100
    RATE_LIMIT_UPLOAD_PER_HOUR = 20
    API_KEY = None
    def validate_api_key(request):
        return True
    def sanitize_log_message(message):
        return message
    SECURITY_HEADERS = {}

app = Flask(__name__)

# Configure CORS avec restrictions
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# Configure Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[f"{RATE_LIMIT_PER_HOUR}/hour", f"{RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri="memory://"  # En production, utiliser Redis: "redis://localhost:6379"
)

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', 'outputs')
ALLOWED_EXTENSIONS = {'csv', 'pdf'}
# Augmenté le timeout par défaut à 1 heure (3600s) au lieu de 10 min
CLEANUP_TIMEOUT = int(os.environ.get('FILE_TIMEOUT', '3600'))  
CLEANUP_INTERVAL = int(os.environ.get('CLEANUP_INTERVAL', '120')) # Vérifier toutes les 2 minutes

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Middleware pour ajouter les headers de sécurité
@app.after_request
def add_security_headers(response):
    """Ajoute les headers de sécurité à toutes les réponses"""
    # Exclure X-Frame-Options pour le preview PDF (nécessaire pour l'affichage en iframe)
    # Les autres routes gardent X-Frame-Options: DENY pour la sécurité
    is_preview_pdf = request.path.startswith('/api/preview/')
    
    for header, value in SECURITY_HEADERS.items():
        # Pour le preview PDF, ne PAS ajouter X-Frame-Options du tout
        # Cela permet l'affichage dans une iframe
        if header == 'X-Frame-Options' and is_preview_pdf:
            # Ne pas ajouter ce header pour le preview PDF
            continue
        else:
            response.headers[header] = value
    return response

# Middleware pour valider l'API key sur les endpoints sensibles
def require_api_key(f):
    """Décorateur pour protéger les endpoints avec une API key"""
    def decorated_function(*args, **kwargs):
        if not validate_api_key(request):
            return jsonify({'error': 'Unauthorized. Valid API key required.'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Initialize cleanup service
try:
    from cleanup_service import CleanupService
    cleanup_service = CleanupService(
        upload_folder=UPLOAD_FOLDER,
        output_folder=OUTPUT_FOLDER,
        timeout_seconds=CLEANUP_TIMEOUT,
        check_interval=CLEANUP_INTERVAL
    )
    cleanup_service.start()
except ImportError:
    cleanup_service = None
    print("Warning: Cleanup service not available")

def _get_activity_file(filepath):
    """Retourne le chemin du fichier d'activité associé."""
    return f"{filepath}.activity"

def _update_activity(filepath):
    """Met à jour le timestamp d'activité d'un fichier."""
    activity_file = _get_activity_file(filepath)
    try:
        with open(activity_file, 'w') as f:
            f.write(str(time.time()))
    except IOError:
        pass

def _delete_file_safe(filepath):
    """Supprime un fichier de manière sécurisée."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        activity_file = _get_activity_file(filepath)
        if os.path.exists(activity_file):
            os.remove(activity_file)
        return True
    except Exception as e:
        print(f"Error deleting {filepath}: {e}")
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _get_file_extension(filename):
    """Get file extension from filename"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


@app.route('/api/upload', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_UPLOAD_PER_HOUR}/hour")
def upload_file():
    """Receive CSV or PDF file and save it temporarily.
    
    For PDF files, also extracts and returns patient metadata for confirmation.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only CSV and PDF files are allowed'}), 400
        
        # Determine file type
        file_extension = _get_file_extension(file.filename)
        is_pdf = file_extension == 'pdf'
        
        # Check file size (max 10MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File too large. Maximum size is 10MB'}), 400
        
        # Basic sanity check: avoid obviously truncated uploads
        min_size = 1000 if is_pdf else 200  # PDFs are typically larger
        if file_size < min_size:
            return jsonify({'error': f'File too small or empty. Please re-upload the {file_extension.upper()} file.'}), 400
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        
        try:
            file.save(filepath)
            # Mark initial activity
            _update_activity(filepath)

            # Extra sanity/logging
            try:
                saved_size = os.path.getsize(filepath)
                log_msg = sanitize_log_message(
                    f"UPLOAD: filename={filename} file_id={file_id} type={file_extension} size_client={file_size} size_disk={saved_size}"
                )
                print(log_msg)
                
                if saved_size < file_size * 0.9:
                    print(f"WARNING: Upload may be truncated! Client sent {file_size} bytes but only {saved_size} saved.")
                
                # Calculer un hash MD5 pour traçabilité
                import hashlib
                with open(filepath, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()[:12]
                print(f"UPLOAD HASH: {file_hash}")
                
                # Create backup
                backup_path = filepath + ".backup"
                import shutil
                shutil.copy2(filepath, backup_path)
                print(f"UPLOAD BACKUP: created {backup_path}")

                # Validate file content based on type
                if is_pdf:
                    # Validate PDF magic bytes
                    with open(filepath, "rb") as fb:
                        magic = fb.read(8)
                    if not magic.startswith(b'%PDF'):
                        app.logger.warning(f"Upload does not look like a valid PDF. file_id={file_id}")
                        _delete_file_safe(filepath)
                        return jsonify({'error': 'Uploaded file does not appear to be a valid PDF.'}), 400
                else:
                    # CSV validation (existing logic)
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        line_count = sum(1 for _ in f)
                    print(f"UPLOAD DIAGNOSTIC: {line_count} lines in CSV file")
                    
                    if line_count < 10:
                        print(f"CRITICAL: CSV has only {line_count} lines - likely truncated!")
                    
                    with open(filepath, "rb") as fb:
                        prefix = fb.read(2048)
                    prefix_text = prefix.decode("utf-8", errors="replace")
                    if ("Analisis" not in prefix_text) and ("Datos Evolutivos" not in prefix_text):
                        app.logger.warning(
                            f"Upload content does not look like expected lab CSV. "
                            f"file_id={file_id} filename={filename}"
                        )
                        _delete_file_safe(filepath)
                        return jsonify({'error': 'Uploaded file does not look like the expected lab CSV export.'}), 400
            except Exception as e:
                app.logger.warning(f"Upload validation warning: {e}")
                # Don't fail; parsing will catch issues later
                pass
        except Exception as e:
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500
        
        # Include sizes
        try:
            saved_size_final = os.path.getsize(filepath)
        except Exception:
            saved_size_final = None

        # Build response
        response_data = {
            'file_id': file_id,
            'filename': filename,
            'file_type': file_extension,
            'size_client': file_size,
            'size_disk': saved_size_final,
            'message': 'File uploaded successfully'
        }
        
        # For PDF files, extract and return metadata for user confirmation
        if is_pdf:
            try:
                from processors.pdf_parser import PDFParser
                pdf_parser = PDFParser()
                metadata = pdf_parser.extract_metadata_only(filepath)
                response_data['extracted_metadata'] = metadata
                # Ne pas logger les métadonnées sensibles
                log_msg = sanitize_log_message(f"UPLOAD PDF: Extracted metadata: {metadata}")
                print(log_msg)
            except Exception as e:
                app.logger.warning(f"Could not extract PDF metadata: {e}")
                response_data['extracted_metadata'] = None

        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/process', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def process_file():
    """Process CSV or PDF file and generate PDF report"""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        file_id = data.get('file_id')
        if not file_id:
            return jsonify({'error': 'file_id is required'}), 400
        
        doctor_comments = data.get('doctor_comments', '').strip()
        patient_metadata = data.get('patient_metadata', {})
        
        # Validate patient metadata
        if not patient_metadata:
            return jsonify({'error': 'Patient metadata is required (sex, birthdate)'}), 400
        
        if not patient_metadata.get('sex'):
            return jsonify({'error': 'Patient sex is required'}), 400
        
        if not patient_metadata.get('birthdate'):
            return jsonify({'error': 'Patient birthdate is required'}), 400
        
        # Find the uploaded file (exclude .activity and .backup files)
        # Support both CSV and PDF files
        uploaded_file = None
        file_type = None
        try:
            for filename in os.listdir(UPLOAD_FOLDER):
                if filename.startswith(file_id):
                    # Skip activity and backup files
                    if '.activity' in filename or '.backup' in filename:
                        continue
                    if filename.endswith('.csv'):
                        uploaded_file = os.path.join(UPLOAD_FOLDER, filename)
                        file_type = 'csv'
                        break
                    elif filename.endswith('.pdf'):
                        uploaded_file = os.path.join(UPLOAD_FOLDER, filename)
                        file_type = 'pdf'
                        break
        except Exception as e:
            return jsonify({'error': f'Error accessing upload folder: {str(e)}'}), 500
        
        if not uploaded_file or not os.path.exists(uploaded_file):
            return jsonify({'error': 'File not found. Please upload the file again.'}), 404
        
        # Validate file is readable
        try:
            file_size = os.path.getsize(uploaded_file)
            
            import hashlib
            with open(uploaded_file, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:12]
            
            log_msg1 = sanitize_log_message(f"PROCESS DIAGNOSTIC: file_id={file_id} type={file_type} file={uploaded_file}")
            print(log_msg1)
            print(f"PROCESS DIAGNOSTIC: size={file_size} bytes, hash={file_hash}")
            
            # For CSV files, do additional validation
            if file_type == 'csv':
                with open(uploaded_file, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                    line_count = len(lines)
                
                print(f"PROCESS DIAGNOSTIC: {line_count} lines in CSV")
                
                if line_count < 10:
                    print(f"CRITICAL: CSV has only {line_count} lines at process time!")
                    # Try backup restore
                    backup_path = uploaded_file + ".backup"
                    if os.path.exists(backup_path):
                        with open(backup_path, 'rb') as bf:
                            backup_hash = hashlib.md5(bf.read()).hexdigest()[:12]
                        if backup_hash != file_hash:
                            print(f"CRITICAL: FILE WAS MODIFIED! Using backup instead.")
                            import shutil
                            shutil.copy2(backup_path, uploaded_file)
                
                if file_size < 200:
                    return jsonify({'error': 'Uploaded file is empty or truncated. Please re-upload.'}), 400
            else:
                # PDF validation
                if file_size < 1000:
                    return jsonify({'error': 'Uploaded PDF is too small. Please re-upload.'}), 400
                    
        except Exception as e:
            return jsonify({'error': f'File is not readable: {str(e)}'}), 400
        
        # Import processors
        try:
            from processors.csv_parser import CSVParser
            from processors.pdf_parser import PDFParser
            from processors.data_transformer import DataTransformer
            from pdf_generator.pdf_builder import PDFBuilder
        except ImportError as e:
            return jsonify({'error': f'Failed to import processors: {str(e)}'}), 500
        
        # Parse file based on type
        reference_ranges = {}
        try:
            if file_type == 'pdf':
                parser = PDFParser()
                raw_data = parser.parse(uploaded_file)
                reference_ranges = raw_data.get('reference_ranges', {})
                
                # Note: __SAMPLE_DATE__ placeholder is now handled in DataTransformer
                
                app.logger.info(f"PDF parsed: {len(raw_data.get('categories', []))} categories, "
                              f"{sum(len(c.get('parameters', [])) for c in raw_data.get('categories', []))} parameters, "
                              f"{len(reference_ranges)} reference ranges")
            else:
                parser = CSVParser()
                raw_data = parser.parse(uploaded_file)
                app.logger.info(f"CSV parsed: {len(raw_data.get('categories', []))} categories, "
                              f"{sum(len(c.get('parameters', [])) for c in raw_data.get('categories', []))} parameters")
            
            if not raw_data.get('categories') or len(raw_data['categories']) == 0:
                return jsonify({'error': f'No categories found in {file_type.upper()}. Please check the file format.'}), 400
        except Exception as e:
            app.logger.error(f"{file_type.upper()} parsing failed: {str(e)}", exc_info=True)
            return jsonify({'error': f'{file_type.upper()} parsing failed: {str(e)}. Please check the file format.'}), 400
        
        # Transform data
        try:
            transformer = DataTransformer()
            # Pass reference_ranges from PDF to transformer
            structured_data = transformer.transform(raw_data, reference_ranges=reference_ranges)
            
            num_transformed_categories = len(structured_data.get('categories', []))
            total_transformed_params = sum(len(cat.get('parameters', [])) for cat in structured_data.get('categories', []))
            app.logger.info(f"Data transformed: {num_transformed_categories} categories, {total_transformed_params} parameters")
            
            if not structured_data.get('categories') or len(structured_data['categories']) == 0:
                return jsonify({'error': 'No data to process. Please check the file format.'}), 400
        except Exception as e:
            app.logger.error(f"Data transformation failed: {str(e)}", exc_info=True)
            return jsonify({'error': f'Data transformation failed: {str(e)}'}), 500
        
        # Generate PDF
        try:
            pdf_builder = PDFBuilder(patient_metadata=patient_metadata)
            output_filename = f"{file_id}_report.pdf"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            pdf_builder.generate(
                structured_data, 
                output_path, 
                doctor_comments=doctor_comments,
                patient_metadata=patient_metadata
            )
            
            if not os.path.exists(output_path):
                return jsonify({'error': 'PDF generation failed. Output file not created.'}), 500
            
            _update_activity(output_path)
            _update_activity(uploaded_file)
        except Exception as e:
            return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500
        
        return jsonify({
            'file_id': file_id,
            'pdf_filename': output_filename,
            'message': 'PDF generated successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route('/api/preview/<file_id>', methods=['GET'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def preview_file(file_id):
    """Preview generated PDF"""
    try:
        if not file_id or len(file_id) < 10:  # Basic validation
            return jsonify({'error': 'Invalid file ID'}), 400
        
        filename = f"{file_id}_report.pdf"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'PDF not found. It may have expired or been deleted.'}), 404
        
        # Mark activity
        _update_activity(filepath)
        
        # Créer la réponse et s'assurer que X-Frame-Options n'est PAS défini
        response = send_file(filepath, mimetype='application/pdf')
        # Supprimer explicitement X-Frame-Options pour permettre l'affichage en iframe
        if 'X-Frame-Options' in response.headers:
            del response.headers['X-Frame-Options']
        
        return response
    except Exception as e:
        return jsonify({'error': f'Preview failed: {str(e)}'}), 500

@app.route('/api/download/<file_id>', methods=['GET'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def download_file(file_id):
    """Download generated PDF"""
    try:
        if not file_id or len(file_id) < 10:  # Basic validation
            return jsonify({'error': 'Invalid file ID'}), 400
        
        filename = f"{file_id}_report.pdf"
        filepath = os.path.join(OUTPUT_FOLDER, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'PDF not found. It may have expired or been deleted.'}), 404
        
        # Send file
        response = send_file(filepath, as_attachment=True, download_name='report.pdf')
        
        # Delete PDF after download
        try:
            _delete_file_safe(filepath)
        except Exception as e:
            print(f"Warning: Could not delete PDF file {filepath}: {e}")
        
        return response
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        'message': 'Medical Report Generator API',
        'endpoints': {
            'POST /api/upload': 'Upload CSV or PDF file (PDF returns extracted metadata)',
            'POST /api/process': 'Process file and generate PDF report (with optional doctor_comments)',
            'GET /api/preview/<file_id>': 'Preview generated PDF',
            'GET /api/download/<file_id>': 'Download generated PDF',
            'GET /api/health': 'Health check'
        }
    }), 200

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'}), 200

@app.route('/api/activity/<file_id>', methods=['POST'])
def mark_activity(file_id):
    """Mark activity for a file to prevent cleanup"""
    try:
        if not file_id or len(file_id) < 10:
            return jsonify({'error': 'Invalid file ID'}), 400
        
        # Try to find and mark activity for upload file
        uploaded_file = None
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith(file_id) and not filename.endswith('.activity'):
                uploaded_file = os.path.join(UPLOAD_FOLDER, filename)
                break
        
        if uploaded_file and os.path.exists(uploaded_file):
            _update_activity(uploaded_file)
        
        # Try to find and mark activity for output file
        output_file = os.path.join(OUTPUT_FOLDER, f"{file_id}_report.pdf")
        if os.path.exists(output_file):
            _update_activity(output_file)
        
        # Also use cleanup service if available
        if cleanup_service:
            cleanup_service.mark_activity(file_id, 'upload')
            cleanup_service.mark_activity(file_id, 'output')
        
        return jsonify({'status': 'ok', 'message': 'Activity marked'}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to mark activity: {str(e)}'}), 500

# Logo is now served as static file from frontend, no need for backend route

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            'POST /api/upload',
            'POST /api/process',
            'GET /api/preview/<file_id>',
            'GET /api/download/<file_id>',
            'GET /api/health',
            'GET /'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Cleanup on shutdown
import atexit
if cleanup_service:
    atexit.register(cleanup_service.stop)

@app.route('/api/upload-multiple', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_UPLOAD_PER_HOUR}/hour")
def upload_multiple_files():
    """Receive multiple PDF files and save them temporarily.
    
    Returns file IDs and extracted metadata for each file.
    """
    try:
        app.logger.info(f"upload-multiple called, request.files keys: {list(request.files.keys())}")
        
        if 'files' not in request.files:
            app.logger.warning("No 'files' key in request.files")
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        app.logger.info(f"Got {len(files)} files from request")
        if not files or len(files) == 0:
            return jsonify({'error': 'No files selected'}), 400
        
        if len(files) > 4:
            return jsonify({'error': 'Maximum 4 files allowed'}), 400
        
        uploaded_files = []
        all_metadata = []
        
        for file in files:
            if file.filename == '':
                continue
            
            if not allowed_file(file.filename):
                return jsonify({'error': f'Invalid file type: {file.filename}. Only CSV and PDF files are allowed'}), 400
            
            file_extension = _get_file_extension(file.filename)
            if file_extension != 'pdf':
                return jsonify({'error': 'Only PDF files are supported for multiple uploads'}), 400
            
            # Check file size (max 10MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            if file_size > 10 * 1024 * 1024:
                return jsonify({'error': f'File {file.filename} is too large. Maximum size is 10MB'}), 400
            
            if file_size < 1000:
                return jsonify({'error': f'File {file.filename} is too small'}), 400
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
            
            try:
                file.save(filepath)
                _update_activity(filepath)
                
                # Validate PDF magic bytes
                with open(filepath, "rb") as fb:
                    magic = fb.read(8)
                if not magic.startswith(b'%PDF'):
                    _delete_file_safe(filepath)
                    return jsonify({'error': f'{file.filename} does not appear to be a valid PDF'}), 400
                
                # Extract metadata
                try:
                    from processors.pdf_parser import PDFParser
                    pdf_parser = PDFParser()
                    metadata = pdf_parser.extract_metadata_only(filepath)
                    all_metadata.append(metadata)
                except Exception as e:
                    app.logger.warning(f"Could not extract PDF metadata from {file.filename}: {e}")
                    all_metadata.append(None)
                
                uploaded_files.append({
                    'file_id': file_id,
                    'filename': filename,
                    'filepath': filepath
                })
            except Exception as e:
                return jsonify({'error': f'Failed to save {file.filename}: {str(e)}'}), 500
        
        if len(uploaded_files) == 0:
            return jsonify({'error': 'No valid files uploaded'}), 400
        
        # Check if metadata matches (sex and birthdate) - for 2 or more files
        if len(uploaded_files) >= 2:
            metadata1 = all_metadata[0]
            metadata2 = all_metadata[1]
            
            if metadata1 and metadata2:
                sex1 = metadata1.get('sex', '').upper()
                sex2 = metadata2.get('sex', '').upper()
                birthdate1 = metadata1.get('birthdate', '')
                birthdate2 = metadata2.get('birthdate', '')
                
                if sex1 and sex2 and sex1 != sex2:
                    return jsonify({
                        'error': 'Patient sex mismatch between files',
                        'details': {
                            'file1': {'sex': sex1},
                            'file2': {'sex': sex2}
                        }
                    }), 400
                
                if birthdate1 and birthdate2 and birthdate1 != birthdate2:
                    return jsonify({
                        'error': 'Patient birthdate mismatch between files',
                        'details': {
                            'file1': {'birthdate': birthdate1},
                            'file2': {'birthdate': birthdate2}
                        }
                    }), 400
        
        return jsonify({
            'files': uploaded_files,
            'metadata': all_metadata,
            'message': f'{len(uploaded_files)} file(s) uploaded successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/process-multiple', methods=['POST'])
@limiter.limit(f"{RATE_LIMIT_PER_HOUR}/hour")
def process_multiple_files():
    """Process multiple PDF files and generate combined PDF report"""
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        file_ids = data.get('file_ids', [])
        if not file_ids or len(file_ids) == 0:
            return jsonify({'error': 'file_ids are required'}), 400
        
        if len(file_ids) > 4:
            return jsonify({'error': 'Maximum 4 files allowed'}), 400
        
        doctor_comments = data.get('doctor_comments', '').strip()
        patient_metadata = data.get('patient_metadata', {})
        
        # Validate patient metadata
        if not patient_metadata:
            return jsonify({'error': 'Patient metadata is required (sex, birthdate)'}), 400
        
        if not patient_metadata.get('sex'):
            return jsonify({'error': 'Patient sex is required'}), 400
        
        if not patient_metadata.get('birthdate'):
            return jsonify({'error': 'Patient birthdate is required'}), 400
        
        # Find uploaded files
        uploaded_files = []
        for file_id in file_ids:
            found_file = None
            try:
                for filename in os.listdir(UPLOAD_FOLDER):
                    if filename.startswith(file_id) and filename.endswith('.pdf'):
                        if '.activity' not in filename and '.backup' not in filename:
                            found_file = os.path.join(UPLOAD_FOLDER, filename)
                            break
            except Exception as e:
                return jsonify({'error': f'Error accessing upload folder: {str(e)}'}), 500
            
            if not found_file or not os.path.exists(found_file):
                return jsonify({'error': f'File {file_id} not found. Please upload again.'}), 404
            
            uploaded_files.append(found_file)
        
        # Import processors
        try:
            from processors.pdf_parser import PDFParser
            from processors.data_transformer import DataTransformer
            from pdf_generator.pdf_builder import PDFBuilder
        except ImportError as e:
            return jsonify({'error': f'Failed to import processors: {str(e)}'}), 500
        
        # Parse all files
        all_raw_data = []
        all_reference_ranges = {}
        all_sample_dates = []
        
        for filepath in uploaded_files:
            try:
                parser = PDFParser()
                raw_data = parser.parse(filepath)
                reference_ranges = raw_data.get('reference_ranges', {})
                
                # Try to get sample_date from metadata (parser returns 'metadata', not 'patient_metadata')
                metadata = raw_data.get('metadata', {})
                sample_date = metadata.get('sample_date', '')
                
                # Also check date_columns from parsed data as fallback
                date_columns = raw_data.get('date_columns', [])
                if not sample_date and date_columns and len(date_columns) > 0:
                    sample_date = date_columns[0]
                
                # Store metadata in patient_metadata for compatibility
                if 'patient_metadata' not in raw_data:
                    raw_data['patient_metadata'] = metadata
                
                all_raw_data.append(raw_data)
                all_reference_ranges.update(reference_ranges)
                if sample_date:
                    all_sample_dates.append(sample_date)
                    app.logger.info(f"Extracted sample_date: {sample_date} from {os.path.basename(filepath)}")
                else:
                    app.logger.warning(f"No sample_date extracted from {os.path.basename(filepath)}, date_columns: {date_columns}")
                
                app.logger.info(f"PDF parsed: {len(raw_data.get('categories', []))} categories")
            except Exception as e:
                app.logger.error(f"PDF parsing failed for {filepath}: {str(e)}", exc_info=True)
                return jsonify({'error': f'PDF parsing failed: {str(e)}'}), 400
        
        # Combine data from all files
        app.logger.info(f"Before combining: {len(all_raw_data)} PDFs, sample dates: {all_sample_dates}")
        combined_data = _combine_multiple_pdfs(all_raw_data, all_sample_dates)
        
        app.logger.info(f"After combining: {len(combined_data.get('categories', []))} categories")
        app.logger.info(f"Date columns: {combined_data.get('date_columns', [])}")
        
        # Debug: log first category and its parameters
        if combined_data.get('categories'):
            first_cat = combined_data['categories'][0]
            app.logger.info(f"First category: {first_cat.get('name')}, {len(first_cat.get('parameters', []))} parameters")
            if first_cat.get('parameters'):
                first_param = first_cat['parameters'][0]
                app.logger.info(f"First parameter: {first_param.get('name')}, values: {first_param.get('values', {})}")
        
        if not combined_data.get('categories') or len(combined_data['categories']) == 0:
            return jsonify({'error': 'No data to process'}), 400
        
        # Transform combined data
        try:
            transformer = DataTransformer()
            app.logger.info(f"Transforming combined data with {len(combined_data.get('date_columns', []))} date columns: {combined_data.get('date_columns', [])}")
            structured_data = transformer.transform(combined_data, reference_ranges=all_reference_ranges)
            
            app.logger.info(f"Combined data transformed: {len(structured_data.get('categories', []))} categories")
            app.logger.info(f"Transformed dates: {structured_data.get('dates', [])}")
            
            # Debug: log first category
            if structured_data.get('categories'):
                first_cat = structured_data['categories'][0]
                app.logger.info(f"First transformed category: {first_cat.get('name')}, {len(first_cat.get('parameters', []))} parameters")
                if first_cat.get('parameters'):
                    first_param = first_cat['parameters'][0]
                    app.logger.info(f"First transformed parameter: {first_param.get('name')}, {len(first_param.get('values', []))} values")
                    for val in first_param.get('values', [])[:3]:  # First 3 values
                        app.logger.info(f"  Value: date={val.get('date')}, value={val.get('value')}")
        except Exception as e:
            app.logger.error(f"Data transformation failed: {str(e)}", exc_info=True)
            return jsonify({'error': f'Data transformation failed: {str(e)}'}), 500
        
        # Generate PDF
        try:
            pdf_builder = PDFBuilder(patient_metadata=patient_metadata)
            combined_file_id = '_'.join(file_ids[:4])  # Use first 4 file IDs for output name
            output_filename = f"{combined_file_id}_report.pdf"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            pdf_builder.generate(
                structured_data, 
                output_path, 
                doctor_comments=doctor_comments,
                patient_metadata=patient_metadata
            )
            
            if not os.path.exists(output_path):
                return jsonify({'error': 'PDF generation failed. Output file not created.'}), 500
            
            for filepath in uploaded_files:
                _update_activity(filepath)
            _update_activity(output_path)
        except Exception as e:
            return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500
        
        return jsonify({
            'file_id': combined_file_id,
            'pdf_filename': output_filename,
            'message': 'Combined PDF generated successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

def _combine_multiple_pdfs(all_raw_data, all_sample_dates):
    """Combine data from multiple PDFs into a single structure"""
    app.logger.info(f"_combine_multiple_pdfs called with {len(all_raw_data)} PDFs, dates: {all_sample_dates}")
    
    if len(all_raw_data) == 0:
        return {'categories': [], 'dates': []}
    
    if len(all_raw_data) == 1:
        app.logger.info("Only one PDF, returning as-is")
        return all_raw_data[0]
    
    # Ensure we have dates - if not extracted, try to extract from date_columns
    if not all_sample_dates or len(all_sample_dates) == 0:
        app.logger.warning("No sample dates extracted, trying to use date_columns")
        # Try to get dates from date_columns in each raw_data
        for idx, raw_data in enumerate(all_raw_data):
            date_columns = raw_data.get('date_columns', [])
            if date_columns and len(date_columns) > 0:
                all_sample_dates.append(date_columns[0])
            else:
                # Last resort: use indexed date
                all_sample_dates.append(f"Timepoint {idx + 1}")
        
        # If still no dates, create placeholders
        if not all_sample_dates or len(all_sample_dates) == 0:
            all_sample_dates = [f"Timepoint {i+1}" for i in range(len(all_raw_data))]
    
    # Sort dates chronologically first (if they can be parsed)
    def parse_date_for_sort(date_str):
        """Parse date string for sorting (DD/MM/YYYY format)"""
        try:
            parts = date_str.split('/')
            if len(parts) == 3:
                return (int(parts[2]), int(parts[1]), int(parts[0]))  # YYYY, MM, DD
        except:
            pass
        return None
    
    # Create list of (original_index, date, parsed_date) for sorting
    date_list = []
    for idx, date in enumerate(all_sample_dates):
        parsed = parse_date_for_sort(date)
        date_list.append((idx, date, parsed))
    
    # Sort by parsed date, then by original index
    date_list.sort(key=lambda x: (x[2] if x[2] else (9999, 12, 31), x[0]))
    
    # Now handle duplicate dates by adding -1, -2 suffix
    processed_dates = []
    date_counts = {}
    for idx, date, parsed in date_list:
        if date in date_counts:
            date_counts[date] += 1
            processed_dates.append(f"{date} - {date_counts[date]}")
        else:
            date_counts[date] = 1
            processed_dates.append(date)
    
    # If dates are the same, add suffixes (maintain order)
    if len(set(all_sample_dates)) == 1 and len(all_sample_dates) > 1:
        processed_dates = [f"{all_sample_dates[0]} - {i+1}" for i in range(len(all_sample_dates))]
    
    app.logger.info(f"Processed dates: {processed_dates}")
    
    # Create mapping from original index to sorted/processed date
    # date_list contains (original_index, date, parsed_date) in sorted order
    original_to_processed = {}
    for sorted_idx, (original_idx, date, parsed) in enumerate(date_list):
        if sorted_idx < len(processed_dates):
            original_to_processed[original_idx] = processed_dates[sorted_idx]
        else:
            # Fallback if indices don't match
            original_to_processed[original_idx] = processed_dates[sorted_idx] if sorted_idx < len(processed_dates) else date
    
    # Use first PDF as base structure
    combined = {
        'categories': [],
        'date_columns': processed_dates,  # DataTransformer expects 'date_columns'
        'dates': processed_dates,  # Keep for compatibility
        'patient_metadata': all_raw_data[0].get('patient_metadata', {}),
        'reference_ranges': {}
    }
    
    # Create a map of parameters by name and category
    param_map = {}  # {(category_name, param_name): [values from all files]}
    
    # Process all PDFs
    for idx, raw_data in enumerate(all_raw_data):
        # Map original index to processed date
        sample_date = original_to_processed.get(idx, processed_dates[idx] if idx < len(processed_dates) else all_sample_dates[idx] if idx < len(all_sample_dates) else f"Date {idx + 1}")
        app.logger.info(f"Processing PDF {idx}, sample_date: {sample_date}, original date: {all_sample_dates[idx] if idx < len(all_sample_dates) else 'N/A'}")
        
        for category in raw_data.get('categories', []):
            cat_name = category.get('name', '')
            if cat_name not in [c.get('name') for c in combined['categories']]:
                combined['categories'].append({
                    'name': cat_name,
                    'spanish_name': category.get('spanish_name', ''),
                    'parameters': []
                })
            
            for param in category.get('parameters', []):
                param_name = param.get('english_name') or param.get('name', '')
                param_unit = param.get('unit', '')
                key = (cat_name, param_name, param_unit)
                
                if key not in param_map:
                    param_map[key] = {
                        'param': param,
                        'values_by_date': {}
                    }
                
                # Extract values for this date
                # Each PDF uses __SAMPLE_DATE__ as placeholder, extract the actual value
                values = param.get('values', {})
                value = None
                if '__SAMPLE_DATE__' in values:
                    value = values['__SAMPLE_DATE__']
                elif len(values) > 0:
                    # Fallback: get first value if __SAMPLE_DATE__ not found
                    value = list(values.values())[0]
                
                # Store value for this processed date (with suffix if needed)
                if value is not None:
                    param_map[key]['values_by_date'][sample_date] = value
                    app.logger.debug(f"  Parameter {param_name} ({param_unit}): {value} -> {sample_date}")
                else:
                    app.logger.warning(f"  Parameter {param_name} ({param_unit}): No value found for date {sample_date}")
    
    # Reconstruct categories with combined parameters
    for (cat_name, param_name, param_unit), param_data in param_map.items():
        # Find or create category
        target_cat = None
        for cat in combined['categories']:
            if cat.get('name') == cat_name:
                target_cat = cat
                break
        
        if not target_cat:
            target_cat = {
                'name': cat_name,
                'spanish_name': '',
                'parameters': []
            }
            combined['categories'].append(target_cat)
        
        # Create combined parameter
        original_param = param_data['param']
        combined_param = {
            'english_name': original_param.get('english_name', param_name),
            'name': original_param.get('name', param_name),
            'spanish_name': original_param.get('spanish_name', ''),
            'category': cat_name,
            'unit': param_unit,
            'values': param_data['values_by_date'],
            'explanation': original_param.get('explanation', ''),
            'reference_range': original_param.get('reference_range', '')
        }
        
        target_cat['parameters'].append(combined_param)
    
    app.logger.info(f"Combined data: {len(combined['categories'])} categories, {len(combined['date_columns'])} dates: {combined['date_columns']}")
    app.logger.info(f"Total parameters: {sum(len(cat['parameters']) for cat in combined['categories'])}")
    
    return combined

if __name__ == '__main__':
    app.run(debug=True, port=5000)

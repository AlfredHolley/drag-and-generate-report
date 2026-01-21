from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import uuid
import tempfile
from werkzeug.utils import secure_filename
import json
import time

# Add backend directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER', 'outputs')
ALLOWED_EXTENSIONS = {'csv'}
# Augmenté le timeout par défaut à 1 heure (3600s) au lieu de 10 min
CLEANUP_TIMEOUT = int(os.environ.get('FILE_TIMEOUT', '3600'))  
CLEANUP_INTERVAL = int(os.environ.get('CLEANUP_INTERVAL', '120')) # Vérifier toutes les 2 minutes

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Initialize cleanup service (disabled by default; enable with ENABLE_CLEANUP=true)
cleanup_service = None
_enable_cleanup = os.environ.get('ENABLE_CLEANUP', 'false').strip().lower() in ('1', 'true', 'yes', 'on')
if _enable_cleanup:
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
else:
    print("Cleanup service is disabled (set ENABLE_CLEANUP=true to enable).")

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

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Receive CSV file and save it temporarily"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only CSV files are allowed'}), 400
        
        # Check file size (max 10MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File too large. Maximum size is 10MB'}), 400
        # Basic sanity check: avoid obviously truncated uploads
        if file_size < 200:  # lab exports are typically several KB; 200B catches truncated/empty
            return jsonify({'error': 'File too small or empty. Please re-export the CSV and try again.'}), 400
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        
        try:
            file.save(filepath)
            # Mark initial activity
            _update_activity(filepath)

            # Extra sanity/logging to diagnose intermittent truncated uploads in production
            try:
                saved_size = os.path.getsize(filepath)
                app.logger.info(f"Upload saved: filename={filename} file_id={file_id} size_client={file_size} size_disk={saved_size}")

                # Read a small prefix and validate it looks like the expected export
                with open(filepath, "rb") as fb:
                    prefix = fb.read(2048)
                prefix_text = prefix.decode("utf-8", errors="replace")
                # The typical exports contain at least one of these tokens early.
                if ("Analisis" not in prefix_text) and ("Datos Evolutivos" not in prefix_text):
                    app.logger.warning(
                        f"Upload content does not look like expected lab CSV. "
                        f"file_id={file_id} filename={filename} prefix={prefix_text[:200]!r}"
                    )
                    # Keep storage clean: remove the bad upload
                    _delete_file_safe(filepath)
                    return jsonify({'error': 'Uploaded file does not look like the expected lab CSV export. Please re-export and try again.'}), 400
            except Exception:
                # Never fail upload due to logging/inspection; parsing will catch issues later.
                pass
        except Exception as e:
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500
        
        # Include sizes so frontend (and logs) can detect truncation patterns
        try:
            saved_size_final = os.path.getsize(filepath)
        except Exception:
            saved_size_final = None

        return jsonify({
            'file_id': file_id,
            'filename': filename,
            'size_client': file_size,
            'size_disk': saved_size_final,
            'message': 'File uploaded successfully'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/process', methods=['POST'])
def process_file():
    """Process CSV file and generate PDF report"""
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
        
        # Find the uploaded file
        uploaded_file = None
        try:
            for filename in os.listdir(UPLOAD_FOLDER):
                if filename.startswith(file_id):
                    uploaded_file = os.path.join(UPLOAD_FOLDER, filename)
                    break
        except Exception as e:
            return jsonify({'error': f'Error accessing upload folder: {str(e)}'}), 500
        
        if not uploaded_file or not os.path.exists(uploaded_file):
            return jsonify({'error': 'File not found. Please upload the file again.'}), 404
        
        # Validate file is readable
        try:
            with open(uploaded_file, 'r', encoding='utf-8') as f:
                # Read a small sample to ensure file is readable and not empty
                sample = f.read(512)
                if not sample:
                    return jsonify({'error': 'Uploaded file is empty. Please re-export the CSV and try again.'}), 400
        except Exception as e:
            return jsonify({'error': f'File is not readable: {str(e)}'}), 400
        
        # Import processors
        try:
            from processors.csv_parser import CSVParser
            from processors.data_transformer import DataTransformer
            from pdf_generator.pdf_builder import PDFBuilder
        except ImportError as e:
            return jsonify({'error': f'Failed to import processors: {str(e)}'}), 500
        
        # Parse CSV
        try:
            parser = CSVParser()
            raw_data = parser.parse(uploaded_file)
            
            # Log parsing results for debugging
            num_categories = len(raw_data.get('categories', []))
            total_params = sum(len(cat.get('parameters', [])) for cat in raw_data.get('categories', []))
            app.logger.info(f"CSV parsed: {num_categories} categories, {total_params} total parameters")
            
            if not raw_data.get('categories') or len(raw_data['categories']) == 0:
                return jsonify({'error': 'No categories found in CSV. Please check the file format.'}), 400
        except Exception as e:
            app.logger.error(f"CSV parsing failed: {str(e)}", exc_info=True)
            return jsonify({'error': f'CSV parsing failed: {str(e)}. Please check the file format.'}), 400
        
        # Transform data
        try:
            transformer = DataTransformer()
            structured_data = transformer.transform(raw_data)
            
            # Log transformation results for debugging
            num_transformed_categories = len(structured_data.get('categories', []))
            total_transformed_params = sum(len(cat.get('parameters', [])) for cat in structured_data.get('categories', []))
            app.logger.info(f"Data transformed: {num_transformed_categories} categories, {total_transformed_params} total parameters")
            
            if not structured_data.get('categories') or len(structured_data['categories']) == 0:
                app.logger.warning(f"No data after transformation. Raw data had {num_categories} categories with {total_params} parameters")
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
            
            # Mark activity for PDF
            _update_activity(output_path)
            
            # Keep CSV file for potential updates (doctor comments, etc.)
            # It will be cleaned up by the cleanup service after inactivity timeout
            # Mark activity for CSV file to keep it alive
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
        
        return send_file(filepath, mimetype='application/pdf')
    except Exception as e:
        return jsonify({'error': f'Preview failed: {str(e)}'}), 500

@app.route('/api/download/<file_id>', methods=['GET'])
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
            'POST /api/upload': 'Upload CSV file',
            'POST /api/process': 'Process CSV and generate PDF (with optional doctor_comments)',
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)

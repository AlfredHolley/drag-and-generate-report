// Auto-detect API base URL (use relative path in production, localhost in development)
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5000/api'
    : '/api';

// DOM Elements
const dropZonesContainer = document.getElementById('dropZonesContainer');
const timepointSelect = document.getElementById('timepointSelect');
const uploadSection = document.getElementById('uploadSection');
const processingSection = document.getElementById('processingSection');
const resultSection = document.getElementById('resultSection');
const errorSection = document.getElementById('errorSection');
const progressFill = document.getElementById('progressFill');
const downloadBtn = document.getElementById('downloadBtn');
const retryBtn = document.getElementById('retryBtn');
const backBtn = document.getElementById('backBtn');
const errorText = document.getElementById('errorText');
let doctorComments = null;
let updateBtn = null;
let previewBtn = null;
let modalOverlay = null;
let modalClose = null;
let pdfPreviewModal = null;

let currentFileId = null;
let doctorCommentsText = '';
let patientMetadata = null;
let uploadedFileId = null; // Store file ID after upload, before patient form submission
let activityInterval = null; // Interval for activity tracking
let uploadedFileIds = null; // Store multiple file IDs for combined reports
let uploadedFiles = {}; // Store uploaded files by timepoint index: {0: {file, fileId}, 1: {...}, ...}
let numberOfTimepoints = 2; // Default number of timepoints

// Function to mark activity for a file
async function markActivity(fileId) {
    if (!fileId) return;
    
    try {
        await fetch(`${API_BASE_URL}/activity/${fileId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    } catch (error) {
        // Silently fail - activity tracking is not critical
        console.debug('Activity tracking failed:', error);
    }
}

// Start activity tracking for a file
function startActivityTracking(fileId) {
    // Clear any existing interval
    stopActivityTracking();
    
    if (!fileId) return;
    
    // Mark activity immediately
    markActivity(fileId);
    
    // Then mark activity every 2 minutes (120000 ms)
    activityInterval = setInterval(() => {
        markActivity(fileId);
    }, 120000); // 2 minutes
}

// Stop activity tracking
function stopActivityTracking() {
    if (activityInterval) {
        clearInterval(activityInterval);
        activityInterval = null;
    }
}

// DOM Elements for patient form modal
let patientModalOverlay = null;
let patientModalClose = null;
let patientFormSubmit = null;
let uploadedFileInfo = null;
const patientSex = document.getElementById('patientSex');
const patientBirthdate = document.getElementById('patientBirthdate');
const patientForm = document.getElementById('patientForm');

// Menstrual cycle phase removed (not required)

// Calculate age from birthdate
function calculateAge(birthdate) {
    if (!birthdate) return null;
    const birth = new Date(birthdate);
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
        age--;
    }
    return age;
}

// Get patient metadata from form
function getPatientMetadata() {
    const sex = patientSex ? patientSex.value : null;
    const birthdate = patientBirthdate ? patientBirthdate.value : null;
    
    if (!sex || !birthdate) {
        return null;
    }
    
    const age = calculateAge(birthdate);
    
    // Get sample_id and sample_date from extracted metadata if available
    const sample_id = patientMetadata?.sample_id || null;
    const sample_date = patientMetadata?.sample_date || null;
    
    return {
        sex: sex,
        birthdate: birthdate,
        age: age,
        sample_id: sample_id,
        sample_date: sample_date
    };
}

// Validate patient form before file upload
function validatePatientForm() {
    if (!patientSex || !patientSex.value) {
        showError('Please select patient sex.');
        return false;
    }
    if (!patientBirthdate || !patientBirthdate.value) {
        showError('Please enter patient date of birth.');
        return false;
    }
    return true;
}

// Initialize DOM elements after page load
function initializeElements() {
    doctorComments = document.getElementById('doctorComments');
    updateBtn = document.getElementById('updateBtn');
    previewBtn = document.getElementById('previewBtn');
    modalOverlay = document.getElementById('modalOverlay');
    modalClose = document.getElementById('modalClose');
    pdfPreviewModal = document.getElementById('pdfPreviewModal');
    
    // Patient form modal elements
    patientModalOverlay = document.getElementById('patientModalOverlay');
    patientModalClose = document.getElementById('patientModalClose');
    patientFormSubmit = document.getElementById('patientFormSubmit');
    uploadedFileInfo = document.getElementById('uploadedFileInfo');
    
    console.log('Elements initialized:', {
        doctorComments: !!doctorComments,
        updateBtn: !!updateBtn,
        previewBtn: !!previewBtn,
        modalOverlay: !!modalOverlay,
        modalClose: !!modalClose,
        pdfPreviewModal: !!pdfPreviewModal,
        patientModalOverlay: !!patientModalOverlay,
        patientModalClose: !!patientModalClose,
        patientFormSubmit: !!patientFormSubmit
    });
    
    // Add event listeners if elements exist
    if (updateBtn) {
        updateBtn.addEventListener('click', handleUpdateComments);
    }
    if (previewBtn) {
        previewBtn.addEventListener('click', handlePreview);
    }
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });
    }
    
    // Patient form modal event listeners
    if (patientModalClose) {
        patientModalClose.addEventListener('click', closePatientModal);
    }
    if (patientModalOverlay) {
        patientModalOverlay.addEventListener('click', (e) => {
            if (e.target === patientModalOverlay) {
                closePatientModal();
            }
        });
    }
    if (patientForm) {
        patientForm.addEventListener('submit', handlePatientFormSubmit);
    }
}

// Initialize drop zones
function initializeDropZones() {
    if (!timepointSelect || !dropZonesContainer) return;
    
    numberOfTimepoints = parseInt(timepointSelect.value) || 2;
    createDropZones(numberOfTimepoints);
    
    timepointSelect.addEventListener('change', (e) => {
        numberOfTimepoints = parseInt(e.target.value) || 2;
        uploadedFiles = {}; // Reset uploaded files
        createDropZones(numberOfTimepoints);
    });
}

function createDropZones(count) {
    if (!dropZonesContainer) return;
    
    dropZonesContainer.innerHTML = '';
    
    for (let i = 0; i < count; i++) {
        const dropZone = document.createElement('div');
        dropZone.className = 'drop-zone';
        dropZone.id = `dropZone${i}`;
        dropZone.dataset.index = i;
        
        dropZone.innerHTML = `
            <div class="drop-zone-content">
                <div class="drop-zone-label">Timepoint ${i + 1}</div>
                <svg class="drop-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="17 8 12 3 7 8"></polyline>
                    <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <h2 class="drop-title">Drop PDF file here</h2>
                <p class="drop-text">or click to browse</p>
                <div class="drop-zone-filename" id="fileName${i}" style="display: none;"></div>
                <input type="file" id="fileInput${i}" accept=".pdf" hidden>
            </div>
        `;
        
        dropZonesContainer.appendChild(dropZone);
        
        // Add event listeners
        const fileInput = document.getElementById(`fileInput${i}`);
        const fileNameDisplay = document.getElementById(`fileName${i}`);
        
        dropZone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => handleFileSelectForZone(i, e));
        
        // Drag and Drop
        dropZone.addEventListener('dragover', (e) => handleDragOverForZone(i, e));
        dropZone.addEventListener('dragleave', (e) => handleDragLeaveForZone(i, e));
        dropZone.addEventListener('drop', (e) => handleDropForZone(i, e));
    }
}

function handleFileSelectForZone(zoneIndex, e) {
    const file = e.target.files[0];
    if (file) {
        handleFileForZone(zoneIndex, file);
    }
}

function handleDragOverForZone(zoneIndex, e) {
    e.preventDefault();
    const dropZone = document.getElementById(`dropZone${zoneIndex}`);
    if (dropZone) {
        dropZone.classList.add('drag-over');
    }
}

function handleDragLeaveForZone(zoneIndex, e) {
    e.preventDefault();
    const dropZone = document.getElementById(`dropZone${zoneIndex}`);
    if (dropZone) {
        dropZone.classList.remove('drag-over');
    }
}

function handleDropForZone(zoneIndex, e) {
    e.preventDefault();
    const dropZone = document.getElementById(`dropZone${zoneIndex}`);
    if (dropZone) {
        dropZone.classList.remove('drag-over');
    }
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileForZone(zoneIndex, files[0]);
    }
}

function handleFileForZone(zoneIndex, file) {
    // Validate file type
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.pdf')) {
        showError(`Timepoint ${zoneIndex + 1}: Please upload a PDF file.`);
        return;
    }
    
    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        showError(`Timepoint ${zoneIndex + 1}: File is too large. Maximum size is 10MB.`);
        return;
    }
    
    // Validate file is not empty
    if (file.size === 0) {
        showError(`Timepoint ${zoneIndex + 1}: File is empty.`);
        return;
    }
    
    // Store file and upload
    uploadedFiles[zoneIndex] = { file: file, fileId: null };
    updateDropZoneDisplay(zoneIndex, file.name);
    uploadFileForZone(zoneIndex, file);
}

function updateDropZoneDisplay(zoneIndex, fileName) {
    const dropZone = document.getElementById(`dropZone${zoneIndex}`);
    const fileNameDisplay = document.getElementById(`fileName${zoneIndex}`);
    
    if (dropZone) {
        dropZone.classList.add('has-file');
    }
    if (fileNameDisplay) {
        fileNameDisplay.textContent = fileName;
        fileNameDisplay.style.display = 'block';
    }
}

async function uploadFileForZone(zoneIndex, file) {
    try {
        console.log(`Uploading file for zone ${zoneIndex}:`, file.name);
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const error = await response.json();
                errorMessage = error.error || errorMessage;
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        if (!data.file_id) {
            throw new Error('Invalid response from server');
        }
        
        // Store file ID
        uploadedFiles[zoneIndex].fileId = data.file_id;
        uploadedFiles[zoneIndex].metadata = data.extracted_metadata;
        
        console.log(`File uploaded for zone ${zoneIndex}, file_id:`, data.file_id);
        
        // Check if all files are uploaded
        checkAllFilesUploaded();
        
    } catch (error) {
        console.error(`Upload error for zone ${zoneIndex}:`, error);
        delete uploadedFiles[zoneIndex];
        const dropZone = document.getElementById(`dropZone${zoneIndex}`);
        const fileNameDisplay = document.getElementById(`fileName${zoneIndex}`);
        if (dropZone) dropZone.classList.remove('has-file');
        if (fileNameDisplay) fileNameDisplay.style.display = 'none';
        showError(`Timepoint ${zoneIndex + 1}: ${error.message || 'Failed to upload file'}`);
    }
}

function checkAllFilesUploaded() {
    // Check if all required files are uploaded
    const uploadedCount = Object.keys(uploadedFiles).filter(idx => uploadedFiles[idx].fileId).length;
    
    if (uploadedCount === numberOfTimepoints) {
        // All files uploaded, show patient form modal
        console.log('All files uploaded, showing patient form');
        showPatientFormForMultipleFiles();
    }
}

function showPatientFormForMultipleFiles() {
    // Collect all metadata
    const allMetadata = [];
    const fileIds = [];
    
    for (let i = 0; i < numberOfTimepoints; i++) {
        if (uploadedFiles[i] && uploadedFiles[i].fileId) {
            fileIds.push(uploadedFiles[i].fileId);
            allMetadata.push(uploadedFiles[i].metadata);
        }
    }
    
    // Store file IDs
    uploadedFileId = fileIds.join(',');
    uploadedFileIds = fileIds;
    
    // Pre-fill patient form with extracted metadata from first PDF
    if (allMetadata.length > 0 && allMetadata[0]) {
        const meta = allMetadata[0];
        console.log('Pre-filling form with PDF metadata:', meta);
        
        patientMetadata = {
            sample_id: meta.sample_id || null,
            sample_date: meta.sample_date || null
        };
        
        if (meta.sex && patientSex) {
            patientSex.value = meta.sex;
        }
        
        if (meta.birthdate && patientBirthdate) {
            patientBirthdate.value = meta.birthdate;
        }
    }
    
    // Show patient form modal
    if (uploadedFileInfo) {
        let infoText = `${fileIds.length} PDF file(s) uploaded:\n`;
        for (let i = 0; i < fileIds.length; i++) {
            const fileData = uploadedFiles[i];
            const sizeKb = fileData.file && fileData.file.size ? Math.round(fileData.file.size / 1024) : null;
            infoText += `Timepoint ${i + 1}: ${fileData.file.name}${sizeKb ? ` (${sizeKb} KB)` : ''}`;
            if (allMetadata[i] && allMetadata[i].sample_date) {
                infoText += ` - Sample date: ${allMetadata[i].sample_date}`;
            }
            infoText += '\n';
        }
        uploadedFileInfo.textContent = infoText;
    }
    
    if (patientFormSubmit) patientFormSubmit.disabled = false;
    
    showSection('upload');
    openPatientModal();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeDropZones();
});

// Buttons
downloadBtn.addEventListener('click', handleDownload);
retryBtn.addEventListener('click', resetUI);

// Attach back button event listener
function attachBackButtonListener() {
    const backBtnElement = document.getElementById('backBtn');
    if (backBtnElement) {
        // Remove any existing listener to avoid duplicates
        backBtnElement.removeEventListener('click', resetUI);
        backBtnElement.addEventListener('click', resetUI);
        console.log('Back button event listener attached');
    } else {
        console.warn('Back button not found');
    }
}

// Attach listener immediately if button exists, or wait for DOM
if (backBtn) {
    backBtn.addEventListener('click', resetUI);
} else {
    // If button doesn't exist yet, wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', attachBackButtonListener);
    // Also try after a short delay in case DOMContentLoaded already fired
    setTimeout(attachBackButtonListener, 100);
}

// Close modals with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (patientModalOverlay && !patientModalOverlay.classList.contains('hidden')) {
            closePatientModal();
        } else if (modalOverlay && !modalOverlay.classList.contains('hidden')) {
            closeModal();
        }
    }
});

// Functions
function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    
    const files = Array.from(e.dataTransfer.files);
    console.log('handleDrop: files count =', files.length, files.map(f => f.name));
    if (files.length > 0) {
        if (files.length === 1) {
            handleFile(files[0]);
        } else {
            handleMultipleFiles(files);
        }
    }
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    console.log('handleFileSelect: files count =', files.length, files.map(f => f.name));
    if (files.length > 0) {
        if (files.length === 1) {
            handleFile(files[0]);
        } else {
            handleMultipleFiles(files);
        }
    }
}

function handleFile(file) {
    // Validate file type
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.csv') && !fileName.endsWith('.pdf')) {
        showError('Please upload a CSV or PDF file.');
        return;
    }
    
    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
        showError('File is too large. Maximum size is 10MB.');
        return;
    }
    
    // Validate file is not empty
    if (file.size === 0) {
        showError('File is empty. Please upload a valid file.');
        return;
    }
    
    // Upload file first, then show patient form modal
    uploadFile(file);
}

function handleMultipleFiles(files) {
    console.log('handleMultipleFiles called with', files.length, 'files');
    // Only allow PDFs for multiple uploads
    const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    console.log('PDF files filtered:', pdfFiles.length, pdfFiles.map(f => f.name));
    
    if (pdfFiles.length === 0) {
        showError('For multiple uploads, only PDF files are supported.');
        return;
    }
    
    if (pdfFiles.length > 2) {
        showError('Maximum 2 files allowed for multiple uploads.');
        return;
    }
    
    // Validate all files
    const maxSize = 10 * 1024 * 1024; // 10MB
    for (const file of pdfFiles) {
        if (file.size > maxSize) {
            showError(`File ${file.name} is too large. Maximum size is 10MB.`);
            return;
        }
        if (file.size === 0) {
            showError(`File ${file.name} is empty.`);
            return;
        }
    }
    
    // Upload multiple files
    console.log('Calling uploadMultipleFiles with', pdfFiles.length, 'files');
    uploadMultipleFiles(pdfFiles);
}

async function uploadFile(file) {
    try {
        showSection('processing');
        progressFill.style.width = '30%';

        // Ensure modal submit is disabled until upload is confirmed
        if (patientFormSubmit) patientFormSubmit.disabled = true;
        if (uploadedFileInfo) uploadedFileInfo.textContent = '';
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const error = await response.json();
                errorMessage = error.error || errorMessage;
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        if (!data.file_id) {
            throw new Error('Invalid response from server');
        }
        
        uploadedFileId = data.file_id;
        progressFill.style.width = '50%';

        // Determine file type
        const fileType = data.file_type || (file.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'csv');
        const fileTypeLabel = fileType.toUpperCase();

        // Show patient form modal ONLY after upload is confirmed
        if (uploadedFileInfo) {
            const sizeKb = file && file.size ? Math.round(file.size / 1024) : null;
            let infoText = `${fileTypeLabel} uploaded: ${data.filename || file.name}${sizeKb ? ` (${sizeKb} KB)` : ''}`;
            
            // For PDF files with extracted metadata, show additional info
            if (fileType === 'pdf' && data.extracted_metadata) {
                const meta = data.extracted_metadata;
                if (meta.patient_name) {
                    infoText += `\nPatient: ${meta.patient_name}`;
                }
                if (meta.sample_date) {
                    infoText += ` | Sample date: ${meta.sample_date}`;
                }
            }
            uploadedFileInfo.textContent = infoText;
        }
        
        // Pre-fill patient form with extracted metadata from PDF
        if (fileType === 'pdf' && data.extracted_metadata) {
            const meta = data.extracted_metadata;
            console.log('Pre-filling form with PDF metadata:', meta);
            
            // Store extracted metadata (including sample_id and sample_date) for later use
            patientMetadata = {
                sample_id: meta.sample_id || null,
                sample_date: meta.sample_date || null
            };
            
            // Pre-fill sex
            if (meta.sex && patientSex) {
                patientSex.value = meta.sex;
            }
            
            // Pre-fill birthdate (convert from DD/MM/YYYY to YYYY-MM-DD if needed)
            if (meta.birthdate && patientBirthdate) {
                // Backend already converts to YYYY-MM-DD format
                patientBirthdate.value = meta.birthdate;
            }
        }
        
        if (patientFormSubmit) patientFormSubmit.disabled = false;

        showSection('upload');
        openPatientModal();
        
    } catch (error) {
        console.error('Upload error:', error);
        if (patientFormSubmit) patientFormSubmit.disabled = true;
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError('Cannot connect to server. Please make sure the backend is running.');
        } else {
            showError(error.message || 'Failed to upload file. Please try again.');
        }
    }
}

async function uploadMultipleFiles(files) {
    try {
        console.log('uploadMultipleFiles: uploading', files.length, 'files');
        showSection('processing');
        progressFill.style.width = '30%';

        if (patientFormSubmit) patientFormSubmit.disabled = true;
        if (uploadedFileInfo) uploadedFileInfo.textContent = '';
        
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
            console.log('Added file to FormData:', file.name, file.size);
        }
        
        console.log('Sending request to /upload-multiple');
        const response = await fetch(`${API_BASE_URL}/upload-multiple`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const error = await response.json();
                errorMessage = error.error || errorMessage;
                if (error.details) {
                    errorMessage += `\nDetails: ${JSON.stringify(error.details)}`;
                }
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        console.log('uploadMultipleFiles response:', data);
        if (!data.files || data.files.length === 0) {
            throw new Error('Invalid response from server');
        }
        
        uploadedFileId = data.files.map(f => f.file_id).join(','); // Store comma-separated IDs
        console.log('Stored uploadedFileId:', uploadedFileId);
        progressFill.style.width = '50%';

        // Show patient form modal with multiple files info
        if (uploadedFileInfo) {
            let infoText = `${data.files.length} PDF file(s) uploaded:\n`;
            data.files.forEach((file, idx) => {
                const sizeKb = files[idx] && files[idx].size ? Math.round(files[idx].size / 1024) : null;
                infoText += `${idx + 1}. ${file.filename}${sizeKb ? ` (${sizeKb} KB)` : ''}`;
                if (data.metadata && data.metadata[idx]) {
                    const meta = data.metadata[idx];
                    if (meta.sample_date) {
                        infoText += ` - Sample date: ${meta.sample_date}`;
                    }
                }
                infoText += '\n';
            });
            uploadedFileInfo.textContent = infoText;
        }
        
        // Pre-fill patient form with extracted metadata from first PDF
        if (data.metadata && data.metadata[0]) {
            const meta = data.metadata[0];
            console.log('Pre-filling form with PDF metadata:', meta);
            
            patientMetadata = {
                sample_id: meta.sample_id || null,
                sample_date: meta.sample_date || null
            };
            
            if (meta.sex && patientSex) {
                patientSex.value = meta.sex;
            }
            
            if (meta.birthdate && patientBirthdate) {
                patientBirthdate.value = meta.birthdate;
            }
        }
        
        if (patientFormSubmit) patientFormSubmit.disabled = false;

        showSection('upload');
        openPatientModal();
        
    } catch (error) {
        console.error('Upload error:', error);
        if (patientFormSubmit) patientFormSubmit.disabled = true;
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError('Cannot connect to server. Please make sure the backend is running.');
        } else {
            showError(error.message || 'Failed to upload files. Please try again.');
        }
    }
}

async function processFile(fileId, comments = '') {
    try {
        progressFill.style.width = '70%';
        
        // Get current patient metadata (in case it was updated)
        const metadata = patientMetadata || getPatientMetadata();
        
        const response = await fetch(`${API_BASE_URL}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                file_id: fileId,
                doctor_comments: comments || '',
                patient_metadata: metadata
            })
        });
        
        if (!response.ok) {
            let errorMessage = 'Processing failed';
            try {
                const error = await response.json();
                errorMessage = error.error || errorMessage;
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        if (!data.file_id) {
            throw new Error('Invalid response from server');
        }
        
        currentFileId = data.file_id;
        progressFill.style.width = '100%';
        
        // Start activity tracking
        startActivityTracking(currentFileId);
        
        // Wait a bit for visual feedback
        setTimeout(() => {
            showSection('result');
        }, 500);
        
    } catch (error) {
        console.error('Process error:', error);
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError('Cannot connect to server. Please make sure the backend is running.');
        } else {
            showError(error.message || 'Failed to process file. Please check your file format.');
        }
    }
}

async function processMultipleFiles(fileIds, metadata, comments = '') {
    try {
        progressFill.style.width = '70%';
        
        const response = await fetch(`${API_BASE_URL}/process-multiple`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                file_ids: fileIds,
                doctor_comments: comments || '',
                patient_metadata: metadata
            })
        });
        
        if (!response.ok) {
            let errorMessage = 'Processing failed';
            try {
                const error = await response.json();
                errorMessage = error.error || errorMessage;
            } catch (e) {
                errorMessage = `Server error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        if (!data.file_id) {
            throw new Error('Invalid response from server');
        }
        
        currentFileId = data.file_id;
        progressFill.style.width = '100%';
        
        // Start activity tracking
        startActivityTracking(currentFileId);
        
        // Wait a bit for visual feedback
        setTimeout(() => {
            showSection('result');
        }, 500);
        
    } catch (error) {
        console.error('Process multiple error:', error);
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError('Cannot connect to server. Please make sure the backend is running.');
        } else {
            showError(error.message || 'Failed to process files. Please try again.');
        }
    }
}

function handleUpdateComments() {
    if (!doctorComments) {
        console.error('Doctor comments element not found');
        return;
    }
    
    doctorCommentsText = doctorComments.value.trim();
    
    if (!currentFileId) {
        showError('No file available.');
        return;
    }
    
    // Show processing
    showSection('processing');
    progressFill.style.width = '50%';
    
    // Reprocess with comments - check if multiple files
    if (uploadedFileIds && uploadedFileIds.length > 1) {
        processMultipleFiles(uploadedFileIds, patientMetadata, doctorCommentsText);
    } else {
        processFile(currentFileId, doctorCommentsText);
    }
}

async function handlePreview() {
    console.log('handlePreview called');
    
    if (!currentFileId) {
        showError('No file available for preview.');
        return;
    }
    
    // Update comments if changed
    const currentComments = doctorComments ? doctorComments.value.trim() : '';
    if (currentComments !== doctorCommentsText) {
        // Update first, then show preview
        doctorCommentsText = currentComments;
        showSection('processing');
        progressFill.style.width = '50%';
        
        try {
            await processFile(currentFileId, doctorCommentsText);
            // After processing, show preview
            setTimeout(() => {
                openModal();
            }, 500);
        } catch (error) {
            console.error('Error updating comments:', error);
            showError('Failed to update comments. Please try again.');
        }
        return;
    }
    
    // Show preview
    openModal();
}

function openModal() {
    console.log('openModal called, currentFileId:', currentFileId);
    
    if (!modalOverlay || !pdfPreviewModal) {
        console.error('Modal elements not found', {
            modalOverlay: !!modalOverlay,
            pdfPreviewModal: !!pdfPreviewModal
        });
        // Try to reinitialize
        initializeElements();
        if (!modalOverlay || !pdfPreviewModal) {
            showError('Preview not available. Please refresh the page.');
            return;
        }
    }
    
    // Mark activity when previewing
    if (currentFileId) {
        markActivity(currentFileId);
    }
    
    const previewUrl = `${API_BASE_URL}/preview/${currentFileId}`;
    console.log('Loading PDF preview from:', previewUrl);
    
    pdfPreviewModal.src = previewUrl;
    modalOverlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
    
    console.log('Modal opened');
}

function closeModal() {
    if (!modalOverlay || !pdfPreviewModal) {
        return;
    }
    
    modalOverlay.classList.add('hidden');
    pdfPreviewModal.src = ''; // Clear iframe to stop loading
    document.body.style.overflow = ''; // Restore scrolling
}

function handleDownload() {
    if (!currentFileId) {
        showError('No file available for download.');
        return;
    }
    
    // Stop activity tracking - file will be deleted after download
    stopActivityTracking();
    
    // Update comments if changed before download
    if (doctorComments.value.trim() !== doctorCommentsText) {
        // Update first, then download
        doctorCommentsText = doctorComments.value.trim();
        showSection('processing');
        progressFill.style.width = '50%';
        
        processFile(currentFileId, doctorCommentsText).then(() => {
            setTimeout(() => {
                const downloadUrl = `${API_BASE_URL}/download/${currentFileId}`;
                window.open(downloadUrl, '_blank');
            }, 1000);
        });
        return;
    }
    
    const downloadUrl = `${API_BASE_URL}/download/${currentFileId}`;
    window.open(downloadUrl, '_blank');
}

function showSection(section) {
    // Hide all sections
    uploadSection.classList.add('hidden');
    processingSection.classList.add('hidden');
    resultSection.classList.add('hidden');
    errorSection.classList.add('hidden');
    
    // Show requested section
    switch(section) {
        case 'upload':
            uploadSection.classList.remove('hidden');
            break;
        case 'processing':
            processingSection.classList.remove('hidden');
            break;
        case 'result':
            resultSection.classList.remove('hidden');
            break;
        case 'error':
            errorSection.classList.remove('hidden');
            break;
    }
}

function showError(message) {
    errorText.textContent = message;
    showSection('error');
}

function openPatientModal() {
    if (!patientModalOverlay) {
        console.error('Patient modal overlay not found');
        return;
    }
    
    patientModalOverlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closePatientModal() {
    if (!patientModalOverlay) {
        return;
    }
    
    patientModalOverlay.classList.add('hidden');
    document.body.style.overflow = '';
}

function handlePatientFormSubmit(e) {
    e.preventDefault();
    
    // Validate form
    if (!validatePatientForm()) {
        return;
    }
    
    // Get patient metadata from form
    const formMetadata = getPatientMetadata();
    
    // Merge with existing metadata (to preserve sample_id and sample_date from PDF)
    patientMetadata = {
        ...patientMetadata,
        ...formMetadata
    };
    
    // Close modal
    closePatientModal();
    
    // Process file(s) with patient metadata
    if (uploadedFileId) {
        console.log('handlePatientFormSubmit: uploadedFileId =', uploadedFileId);
        // Check if multiple files (comma-separated IDs)
        const fileIds = uploadedFileId.split(',');
        console.log('handlePatientFormSubmit: fileIds =', fileIds, 'length =', fileIds.length);
        
        if (fileIds.length > 1) {
            console.log('Processing multiple files:', fileIds);
            // Multiple files - use process-multiple route
            uploadedFileIds = fileIds; // Store for later use (e.g., update comments)
            currentFileId = fileIds.join('_'); // Combined ID for output
            for (const fileId of fileIds) {
                markActivity(fileId);
            }
            showSection('processing');
            progressFill.style.width = '60%';
            processMultipleFiles(fileIds, patientMetadata);
        } else {
            console.log('Processing single file:', uploadedFileId);
            // Single file - use regular process route
            uploadedFileIds = null; // Clear multiple file IDs
            currentFileId = uploadedFileId;
            markActivity(uploadedFileId);
            showSection('processing');
            progressFill.style.width = '60%';
            processFile(currentFileId);
        }
    } else {
        showError('No file available. Please upload a file again.');
    }
}

function resetUI() {
    try {
        console.log('resetUI called');
        
        // Stop activity tracking
        stopActivityTracking();
        
        // Reset all state variables
        currentFileId = null;
        uploadedFileId = null;
        uploadedFileIds = null;
        uploadedFiles = {}; // Reset uploaded files for multiple timepoints
        doctorCommentsText = '';
        patientMetadata = null;
        
        // Reset uploaded file info display
        if (uploadedFileInfo) {
            uploadedFileInfo.textContent = '';
        }
        
        // Reset doctor comments
        if (doctorComments) {
            doctorComments.value = '';
        }
        
        // Reset patient form
        if (patientForm) {
            patientForm.reset();
        }
        
        // Reset timepoint selector to default (1)
        numberOfTimepoints = 1;
        if (timepointSelect) {
            timepointSelect.value = '1';
        }
        
        // Recreate drop zones to reset their state completely
        // This clears all file inputs and displays
        if (dropZonesContainer) {
            dropZonesContainer.innerHTML = ''; // Clear first
            if (typeof createDropZones === 'function') {
                createDropZones(numberOfTimepoints);
            }
        }
        
        // Reset progress bar
        if (progressFill) {
            progressFill.style.width = '0%';
        }
        
        closeModal();
        closePatientModal();
        showSection('upload');
        
        console.log('resetUI completed');
    } catch (error) {
        console.error('Error in resetUI:', error);
        // Still try to show upload section even if there's an error
        try {
            showSection('upload');
        } catch (e) {
            console.error('Error showing upload section:', e);
        }
    }
}

// Health check on load
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (!response.ok) {
            console.warn('Backend health check failed');
        }
    } catch (error) {
        console.warn('Backend not available:', error);
        // Don't show error to user, just log it
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeElements);
} else {
    initializeElements();
}

// Logo is already set in HTML, no need to set it here
// If logo fails to load, the onerror handler in HTML will hide it

// Health check
checkHealth();

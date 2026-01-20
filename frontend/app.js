// Auto-detect API base URL (use relative path in production, localhost in development)
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5000/api'
    : '/api';

// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
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
const patientSex = document.getElementById('patientSex');
const patientBirthdate = document.getElementById('patientBirthdate');
const menstrualPhase = document.getElementById('menstrualPhase');
const menstrualPhaseGroup = document.getElementById('menstrualPhaseGroup');
const patientForm = document.getElementById('patientForm');

// Show/hide menstrual phase based on sex
if (patientSex) {
    patientSex.addEventListener('change', () => {
        if (patientSex.value === 'F') {
            menstrualPhaseGroup.classList.remove('hidden');
        } else {
            menstrualPhaseGroup.classList.add('hidden');
            if (menstrualPhase) {
                menstrualPhase.value = '';
            }
        }
    });
}

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
    const phase = menstrualPhase && menstrualPhase.value ? menstrualPhase.value : null;
    
    if (!sex || !birthdate) {
        return null;
    }
    
    const age = calculateAge(birthdate);
    
    return {
        sex: sex,
        birthdate: birthdate,
        age: age,
        menstrual_phase: sex === 'F' ? phase : null
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

// Event Listeners
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileSelect);

// Drag and Drop
dropZone.addEventListener('dragover', handleDragOver);
dropZone.addEventListener('dragleave', handleDragLeave);
dropZone.addEventListener('drop', handleDrop);

// Buttons
downloadBtn.addEventListener('click', handleDownload);
retryBtn.addEventListener('click', resetUI);
if (backBtn) {
    backBtn.addEventListener('click', resetUI);
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
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

function handleFile(file) {
    // Validate file type
    if (!file.name.endsWith('.csv')) {
        showError('Please upload a CSV file.');
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
        showError('File is empty. Please upload a valid CSV file.');
        return;
    }
    
    // Upload file first, then show patient form modal
    uploadFile(file);
}

async function uploadFile(file) {
    try {
        showSection('processing');
        progressFill.style.width = '30%';
        
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
        
        // Hide processing, show patient form modal
        showSection('upload');
        openPatientModal();
        
    } catch (error) {
        console.error('Upload error:', error);
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showError('Cannot connect to server. Please make sure the backend is running.');
        } else {
            showError(error.message || 'Failed to upload file. Please try again.');
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
            showError(error.message || 'Failed to process file. Please check your CSV format.');
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
    
    // Reprocess with comments
    processFile(currentFileId, doctorCommentsText);
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
    
    // Store patient metadata
    patientMetadata = getPatientMetadata();
    
    // Close modal
    closePatientModal();
    
    // Process file with patient metadata
    if (uploadedFileId) {
        currentFileId = uploadedFileId;
        // Mark activity for uploaded file
        markActivity(uploadedFileId);
        showSection('processing');
        progressFill.style.width = '60%';
        processFile(currentFileId);
    } else {
        showError('No file available. Please upload a file again.');
    }
}

function resetUI() {
    // Stop activity tracking
    stopActivityTracking();
    
    currentFileId = null;
    uploadedFileId = null;
    doctorCommentsText = '';
    patientMetadata = null;
    fileInput.value = '';
    if (doctorComments) {
        doctorComments.value = '';
    }
    if (patientForm) {
        patientForm.reset();
    }
    if (menstrualPhaseGroup) {
        menstrualPhaseGroup.classList.add('hidden');
    }
    progressFill.style.width = '0%';
    closeModal();
    closePatientModal();
    showSection('upload');
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

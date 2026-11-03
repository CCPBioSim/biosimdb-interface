import { ChunkedUploader } from '../uploads/chunked_upload.js';
import { addWorkflowId, getWorkflowId } from '../core/workflow.js';
import { escapeHtml, hideLoadingOverlay, showAlert, showLoadingOverlay } from '../core/ui.js';
import { populateFields, setFieldsDisabled } from '../webform/fields.js';
import { saveExtracted, saveFormState } from '../webform/state.js';
import { showValidationErrors } from '../webform/validation.js';

/** Upload the selected files in chunks, then request metadata extraction. */
async function uploadAndExtract() {
    const topology = document.querySelector('input[name="topology"]').files[0];
    const trajectories = Array.from(
        document.querySelectorAll('input[name="trajectory[]"]')
    ).flatMap(input => Array.from(input.files));

    const uploader = new ChunkedUploader(getWorkflowId());
    const formData = addWorkflowId(new FormData());
    formData.append('topology_name', await uploader.upload(topology));
    for (const file of trajectories) {
        formData.append('trajectory_names[]', await uploader.upload(file));
    }

    const r = await fetch(window.APPLICATION_BASE + '/extract_metadata', {
        method: 'POST',
        body: formData,
    });
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
        throw new Error(`Unexpected server response (${r.status}).`);
    }
    return r.json();
}

/** Fill the form from extraction results and surface any validation errors. */
function handleExtraction(data) {
    if (data.error) {
        showAlert(`<strong>${escapeHtml(data.error)}</strong>`, 'danger', 5000);
        return;
    }
    if (!data.simulation_metadata) return;

    try {
        populateFields(data.simulation_metadata);
    } finally {
        saveExtracted(data.simulation_metadata);
        saveFormState();
        setFieldsDisabled(false);
    }
    if (data.message) {
        showAlert(data.message, 'success', 5000);
    }
    if (data.validation_errors && data.validation_errors.length > 0) {
        showValidationErrors(data.validation_errors);
    }
}

/**
 * Handle the "Extract metadata" button: upload files, extract, populate the form.
 * @param {HTMLElement} button - The clicked extract button.
 */
export function extractMetadata(button) {
    showLoadingOverlay(button, 'Extracting...');
    setFieldsDisabled(true);

    return uploadAndExtract()
        .then(handleExtraction)
        .catch(err => showAlert(`<strong>Error:</strong> ${err.message}`, 'danger', 10000))
        .finally(() => hideLoadingOverlay(button));
}

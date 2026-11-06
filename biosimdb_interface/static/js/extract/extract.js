import { ChunkedUploader } from '../uploads/chunked_upload.js';
import { addWorkflowId, clearWorkflow, getWorkflowId } from '../core/workflow.js';
import { createStepper, escapeHtml, hideLoadingOverlay, showAlert, showLoadingOverlay } from '../core/ui.js';
import { populateFields, setFieldsDisabled } from '../webform/fields.js';
import { saveExtracted, saveFormState } from '../webform/state.js';
import { showValidationErrors } from '../webform/validation.js';

/** Upload the selected files in chunks, then request metadata extraction. */
async function uploadAndExtract(panel, uploader) {
    const topology = document.querySelector('input[name="topology"]').files[0];
    const trajectories = Array.from(
        document.querySelectorAll('input[name="trajectory[]"]')
    ).flatMap(input => Array.from(input.files));

    const files = [topology, ...trajectories];
    const steps = files.map((f, i) => ({ id: `file${i}`, label: `Uploading ${f.name}` }));
    steps.push({ id: 'extract', label: 'Extracting metadata' });
    const update = createStepper(panel, steps);
    steps.forEach(s => update(s.id, 'pending'));

    const formData = addWorkflowId(new FormData());
    const names = [];
    for (const [i, file] of files.entries()) {
        const id = `file${i}`;
        const show = f => update(id, 'active', f, `${(f * 100).toFixed(0)}% of ${(file.size / 1e6).toFixed(1)} MB`);
        show(0);
        try {
            names.push(await uploader.upload(file, show));
        } catch (err) {
            update(id, 'error');
            throw err;
        }
        update(id, 'done');
    }
    formData.append('topology_name', names[0]);
    names.slice(1).forEach(n => formData.append('trajectory_names[]', n));

    update('extract', 'active', null, 'Reading topology and trajectories on the server...');

    const r = await fetch(window.APPLICATION_BASE + '/extract_metadata', {
        method: 'POST',
        body: formData,
        signal: uploader.signal,
    });
    update('extract', r.ok ? 'done' : 'error');
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
    const panel = showLoadingOverlay(button, 'Extracting...', true);
    setFieldsDisabled(true);

    const controller = new AbortController();
    const uploader = new ChunkedUploader(getWorkflowId(), { signal: controller.signal });
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn-outline-secondary mt-2';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', () => {
        controller.abort();
        clearWorkflow(); // discard files already uploaded to the server
    });
    panel.after(cancelBtn);
    panel.parentElement.classList.add('flex-column');

    return uploadAndExtract(panel, uploader)
        .then(handleExtraction)
        .catch(err => {
            if (err.name === 'AbortError') {
                showAlert('Extraction cancelled.', 'info', 5000);
                return;
            }
            showAlert(`<strong>Error:</strong> ${err.message}`, 'danger', 10000);
        })
        .finally(() => hideLoadingOverlay(button));
}

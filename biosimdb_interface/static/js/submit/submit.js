import { addWorkflowId, getWorkflowId } from '../core/workflow.js';
import { hideLoadingOverlay, showAlert, showLoadingOverlay } from '../core/ui.js';
import { clearFormState, requireExtraction } from '../webform/state.js';
import { showValidationErrors } from '../webform/validation.js';

/**
 * Validates the form by posting to `/webform` with a dry-run `save` flag,
 * then calls `onSuccess` if validation passes or displays errors as an alert.
 * @param {HTMLFormElement} form - The simulation form element.
 * @param {function} onSuccess - Callback invoked with the server response data on success.
 */
function validateAndSubmit(form, onSuccess) {
    const formData = addWorkflowId(new FormData(form));
    // Files were already stored server-side by extraction; don't re-upload them.
    formData.delete('topology');
    formData.delete('trajectory[]');
    formData.append('save', '1');
    return fetch(window.APPLICATION_BASE + '/webform', { method: 'POST', body: formData })
        .then(async r => {
            const ct = r.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
                throw new Error(`Unexpected server response (${r.status}).`);
            }
            return r.json();
        })
        .then(data => {
            if (data.validation_errors && data.validation_errors.length > 0) {
                showValidationErrors(data.validation_errors);
                return false;
            }
            if (data.success) {
                onSuccess(data);
                return true;
            }
            return false;
        })
        .catch(err => {
            showAlert(`<strong>Error:</strong> ${err.message}`, 'danger', 5000);
            return false;
        });
}

/** Append a hidden input to a form. */
function addHiddenInput(form, name, value) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.appendChild(input);
}

/**
 * Handle the "Submit" button: validate, then submit the form natively.
 * @param {HTMLElement} button - The clicked submit button.
 */
export function submitSimulation(button) {
    const form = document.getElementById('simulationForm');
    if (!requireExtraction(form)) return;
    showLoadingOverlay(button, 'Submitting...');
    validateAndSubmit(form, () => {
        clearFormState();
        addHiddenInput(form, 'submit', '1');
        addHiddenInput(form, 'workflow_id', getWorkflowId());
        HTMLFormElement.prototype.submit.call(form);
    }).then(success => {
        if (!success) hideLoadingOverlay(button);
    });
}

/**
 * Handle the "Save" button: validate, then download the metadata as JSON.
 * @param {HTMLElement} button - The clicked save button.
 */
export function saveMetadata(button) {
    const form = document.getElementById('simulationForm');
    if (!requireExtraction(form)) return;
    showLoadingOverlay(button, 'Saving...');
    validateAndSubmit(form, (data) => {
        const blob = new Blob([JSON.stringify(data.data, null, 2)], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = 'simulation_metadata.json'; a.click();
        URL.revokeObjectURL(url);
    }).finally(() => hideLoadingOverlay(button));
}

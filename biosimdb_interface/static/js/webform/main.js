import { clearWorkflow } from '../core/workflow.js';
import { autoDismissAlerts } from '../core/ui.js';
import { extractMetadata } from '../extract/extract.js';
import { saveMetadata, submitSimulation } from '../submit/submit.js';
import { addInstance, lockForm, populateFields, removeInstance, setFieldsDisabled } from './fields.js';
import { loadExtracted, restoreFormState, saveFormState } from './state.js';

// Handle click events for extract, save, submit, add/remove molecule instances, and clear
document.addEventListener('click', function(e) {
    const target = e.target;

    if (target.classList.contains('extract-metadata-btn')) {
        extractMetadata(target);
    } else if (target.matches('input[name="submit"]')) {
        e.preventDefault();
        submitSimulation(target);
    } else if (target.matches('input[name="save"]')) {
        e.preventDefault();
        saveMetadata(target);
    } else if (target.classList.contains('add-instance')) {
        addInstance(target);
    } else if (target.classList.contains('remove-instance')) {
        removeInstance(target);
    } else if (target.classList.contains('clear-metadata-btn')) {
        clearWorkflow();
        lockForm();
    }
});

// On page load: restore extracted metadata and form state from sessionStorage,
// or disable fields if the form is empty.
document.addEventListener('DOMContentLoaded', () => {
    if (window.CLEAR_CLIENT_STATE) {
        lockForm();
        return;
    }

    const extracted = loadExtracted();
    if (extracted) {
        populateFields(extracted);
        restoreFormState();
        setFieldsDisabled(false);
        return;
    }
    lockForm();
});

window.addEventListener('pageshow', (event) => {
    if (event.persisted && (window.CLEAR_CLIENT_STATE || !loadExtracted())) {
        lockForm();
    }
});

// Persist form state on any user input or change so it survives page refreshes.
['input', 'change'].forEach(type => {
    document.addEventListener(type, function(e) {
        if (e.target.closest('#simulationForm') && e.target.type !== 'file') saveFormState();
    });
});

autoDismissAlerts();

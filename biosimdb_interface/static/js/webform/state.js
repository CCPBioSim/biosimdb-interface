const EXTRACTED_KEY = 'extractedMetadata';
const FORM_STATE_KEY = 'formState';

/** Return the extracted metadata cached for this tab, or null. */
export function loadExtracted() {
    const saved = sessionStorage.getItem(EXTRACTED_KEY);
    return saved ? JSON.parse(saved) : null;
}

/** Cache extracted metadata for this tab. */
export function saveExtracted(metadata) {
    sessionStorage.setItem(EXTRACTED_KEY, JSON.stringify(metadata));
}

/** Remove cached extracted metadata and form values. */
export function clearFormState() {
    sessionStorage.removeItem(EXTRACTED_KEY);
    sessionStorage.removeItem(FORM_STATE_KEY);
}

/**
 * Persists current form field values to sessionStorage so they survive page refreshes.
 * Excludes file, button, submit, and hidden inputs.
 */
export function saveFormState() {
    const state = {};
    document.querySelectorAll('#simulationForm input, #simulationForm select, #simulationForm textarea').forEach(el => {
        const type = (el.type || '').toLowerCase();
        if (type === 'file' || type === 'button' || type === 'submit' || type === 'hidden' || !el.name) return;
        state[el.name] = type === 'checkbox' ? el.checked : el.value;
    });
    sessionStorage.setItem(FORM_STATE_KEY, JSON.stringify(state));
}

/**
 * Restores form field values from sessionStorage.
 * Skips submit and hidden inputs to avoid overwriting button labels or CSRF tokens.
 */
export function restoreFormState() {
    const saved = sessionStorage.getItem(FORM_STATE_KEY);
    if (!saved) return;
    Object.entries(JSON.parse(saved)).forEach(([name, value]) => {
        const el = document.querySelector(`[name="${CSS.escape(name)}"]`);
        if (!el) return;
        const type = (el.type || '').toLowerCase();
        if (type === 'submit' || type === 'hidden') return;  // never restore onto buttons
        type === 'checkbox' ? el.checked = value : el.value = value;
    });
}

/**
 * Guards save/submit actions by checking that metadata has been extracted.
 * Uses native browser validation UI (`reportValidity`) to surface the error on the topology input.
 * @param {HTMLFormElement} form - The simulation form element.
 * @returns {boolean} `true` if extraction has been performed; `false` otherwise.
 */
export function requireExtraction(form) {
    if (!sessionStorage.getItem(EXTRACTED_KEY)) {
        const topologyInput = document.querySelector('input[name="topology"]');
        topologyInput.setCustomValidity('Please extract metadata from your uploaded files first.');
        form.reportValidity();
        topologyInput.setCustomValidity('');
        return false;
    }
    return true;
}

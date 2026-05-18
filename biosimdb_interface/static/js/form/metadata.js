// Handle click events for extract, save, submit, add/remove molecule instances, and clear
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('extract-metadata-btn')) {
        // if (e.target.disabled) return; // Prevent double clicks

        e.target.disabled = true;

        // Add a wait spinner and grey out background page when data extraction is happening
        const loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loading-overlay';
        loadingOverlay.style.cssText = 'position:fixed; inset:0; z-index:2000; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,0.5);';
        loadingOverlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
        document.body.appendChild(loadingOverlay);


        e.target.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Extracting...';
        setFieldsDisabled(true);
        const formData = new FormData();

        // Get uploaded files
        const topology = document.querySelector(`input[name="topology"]`).files[0];
        const trajectories = document.querySelectorAll(`input[name="trajectory[]"]`);

        formData.append(`topology`, topology);
        trajectories.forEach(input => {
            Array.from(input.files).forEach(file => {
                formData.append(`trajectory[]`, file);
            });
        });

        fetch('/extract_metadata', {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else if (data.simulation_metadata) {
                populateFields(data.simulation_metadata);
                sessionStorage.setItem('extractedMetadata', JSON.stringify(data.simulation_metadata));
                saveFormState();
                setFieldsDisabled(false);
                if (data.message) {
                    showAlert(data.message, 'success', 4000);
                }
                if (data.validation_errors && data.validation_errors.length > 0) {
                    const [heading, ...errors] = data.validation_errors;
                    const list = errors.map(e => `<li>${e}</li>`).join('');
                    showAlert(`<strong>${heading}</strong><ul class="mb-0 mt-1">${list}</ul>`, 'warning', 4000);
                }
            }
        })
        .finally(() => {
            e.target.disabled = false;
            e.target.textContent = 'Extract Metadata';
            document.getElementById('loading-overlay')?.remove();
        });
    }

    if (e.target.matches('input[name="submit"]')) {
        e.preventDefault();
        const form = document.getElementById('simulationForm');
        if (!requireExtraction(form)) return;
        validateAndSubmit(form, () => {
            sessionStorage.removeItem('formState');
            sessionStorage.removeItem('extractedMetadata');
            const hidden = document.createElement('input');
            hidden.type = 'hidden'; hidden.name = 'submit'; hidden.value = '1';
            form.appendChild(hidden);
            HTMLFormElement.prototype.submit.call(form);
        });
    }

    if (e.target.matches('input[name="save"]')) {
        e.preventDefault();
        const form = document.getElementById('simulationForm');
        if (!requireExtraction(form)) return;
        validateAndSubmit(form, (data) => {
            const blob = new Blob([JSON.stringify(data.data, null, 2)], {type: 'application/json'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'simulation_metadata.json'; a.click();
            URL.revokeObjectURL(url);
        });
    }

    if (e.target.classList.contains('add-instance')) {
        const container = e.target.closest('.multiple-field-container');
        const template = container.querySelector('.multiple-field-template');
        const instances = container.querySelectorAll('.field-instance');
        const newIndex = instances.length + 1;
        const max = container.dataset.max ? parseInt(container.dataset.max) : null;

        if (max !== null && instances.length >= max) {
                alert(`Maximum of ${max} entries allowed.`);
                return;
        }

        const newInstance = template.cloneNode(true);
        newInstance.className = 'field-instance mb-4';
        newInstance.style.display = 'block';
        newInstance.querySelector('.instance-number').textContent = newIndex;

        newInstance.querySelectorAll('input, select, textarea').forEach(input => {
            input.name = input.name.replace('[TEMPLATE]', `[${newIndex}]`);
            input.value = '';
        });

        container.insertBefore(newInstance, e.target);
        renumberInstances(container);
        // Initialise popovers on the newly cloned instance
        newInstance.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => new bootstrap.Popover(el));
    }

    if (e.target.classList.contains('remove-instance')) {
        const container = e.target.closest('.multiple-field-container');
        const instances = container.querySelectorAll('.field-instance');

        if (instances.length > 1) {
            e.target.closest('.field-instance').remove();
            renumberInstances(container);
        }
    }

    if (e.target.classList.contains('clear-metadata-btn')) {
        const form = document.getElementById('simulationForm');

        // Clear all non-button inputs/selects/textareas
        form.querySelectorAll('input, select, textarea').forEach(el => {
            const type = (el.type || '').toLowerCase();

            if (type === 'submit' || type === 'button' || type === 'hidden') return;

            if (type === 'checkbox' || type === 'radio') {
                el.checked = false;
            } else if (type === 'file') {
                el.value = '';
            } else if (el.tagName === 'SELECT') {
                el.selectedIndex = 0;
            } else {
                el.value = '';
            }
        });

        // Keep only first molecule_ID instance per container
        form.querySelectorAll('.multiple-field-container').forEach(container => {
            const instances = container.querySelectorAll('.field-instance');
            instances.forEach((instance, idx) => {
                if (idx > 0) instance.remove();
            });
            renumberInstances(container);
        });

        setFieldsDisabled(true);
        sessionStorage.removeItem('extractedMetadata');
        sessionStorage.removeItem('formState');
    }

});

/**
 * Populates form fields from extracted simulation metadata.
 * @param {Object} metadata - Nested metadata object keyed by section then field name.
 */
function populateFields(metadata) {
    Object.entries(metadata).forEach(([section, sectionData]) => {
        Object.entries(sectionData).forEach(([fieldName, fieldValue]) => {
            if (fieldName === '@type') return;
            // nested fields
            if (Array.isArray(fieldValue)) {
                const container = document.querySelector(
                    `[data-field="${fieldName}"][data-section="${section}"]`
                );
                if (!container) return;
                const template = container.querySelector('.multiple-field-template');

                // Snapshot existing values before clearing
                const snapshot = {};
                container.querySelectorAll('.field-instance input, .field-instance select, .field-instance textarea').forEach(el => {
                    if (el.name) snapshot[el.name] = (el.type === 'checkbox') ? el.checked : el.value;
                });

                container.querySelectorAll('.field-instance').forEach(el => el.remove());
                fieldValue.forEach((item, i) => {
                    const inst = template.cloneNode(true);
                    inst.className = 'field-instance mb-4';
                    inst.style.display = 'block';
                    inst.querySelector('.instance-number').textContent = i + 1;
                    inst.querySelectorAll('input, select, textarea').forEach(el => {
                        el.name = el.name.replace('[TEMPLATE]', `[${i + 1}]`);
                    });
                    container.insertBefore(inst, container.querySelector('.add-instance'));
                    // Initialise popovers on dynamically added instances
                    inst.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => new bootstrap.Popover(el));
                    setNestedFields(`${section}[${fieldName}][${i + 1}]`, item);

                    // Restore snapshot for fields extraction left empty
                    inst.querySelectorAll('input, select, textarea').forEach(el => {
                        if (!el.name || snapshot[el.name] === undefined) return;
                        const type = (el.type || '').toLowerCase();
                        if (type === 'checkbox') {
                            if (!el.checked) el.checked = snapshot[el.name];
                        } else {
                            if (el.value === '' && snapshot[el.name] !== '') el.value = snapshot[el.name];
                        }
                    });
                });
                renumberInstances(container);
            } else if (fieldValue && typeof fieldValue === "object") {
                setNestedFields(`${section}[${fieldName}]`, fieldValue);
            } else {
                const input = document.querySelector(`[name="${section}[${fieldName}]"]`);
                if (!input) return;
                if (input.type === 'checkbox') {
                    if (fieldValue) input.checked = true;
                } else {
                    if (fieldValue !== null && fieldValue !== undefined && fieldValue !== '') {
                        input.value = fieldValue;
                    }
                }
            }
        });
    });
}


/**
 * Renumbers all field instances within a repeatable container after add/remove.
 * Updates both the visible header text and the `name` attributes of all inputs.
 * @param {HTMLElement} container - The `.multiple-field-container` element to renumber.
 */
function renumberInstances(container) {
    const instances = container.querySelectorAll('.field-instance');
    instances.forEach((instance, index) => {
        const newIndex = index + 1;

        // Update header text
        const header = instance.querySelector('h6');
        header.textContent = header.textContent.replace(/\d+/, newIndex);

        // Update input names
        instance.querySelectorAll('input, select, textarea').forEach(input => {
            input.name = input.name.replace(/\[(\d+)\]/, `[${newIndex}]`);
        });
    });
}

/**
 * Recursively sets form field values from a nested object using bracket-notation paths.
 * Primitive arrays (e.g. vectors) are joined as comma-separated strings.
 * @param {string} basePath - Bracket-notation path prefix (e.g. `"simulation[box_vectors]"`).
 * @param {Object} obj - Object whose entries map to form field name suffixes and values.
 */
function setNestedFields(basePath, obj) {
    Object.entries(obj).forEach(([key, val]) => {
        const path = `${basePath}[${key}]`;
        if (Array.isArray(val)) {
            // primitive array (vector) → join as text
            const input = document.querySelector(`[name="${path}"]`);
            if (input) input.value = val.join(", ");
        } else if (val && typeof val === "object") {
            setNestedFields(path, val);
        } else {
            const input = document.querySelector(`[name="${path}"]`);
            if (!input) return;
            if (input.type === "checkbox") {
                if (val) input.checked = true;
            } else {
                if (val !== null && val !== undefined && val !== '') input.value = val;
            }
        }
    });
}

/**
 * Enables or disables all editable form fields and adds/removes click-blocking overlays.
 * When disabled, an overlay with a Bootstrap popover is added to each `.field-container`
 * to prompt the user to extract metadata first.
 * @param {boolean} disabled - `true` to disable fields and add overlays; `false` to re-enable.
 */
function setFieldsDisabled(disabled) {
    document.querySelectorAll('#simulationForm input, #simulationForm select, #simulationForm textarea').forEach(el => {
        const type = (el.type || '').toLowerCase();
        if (type === 'file' || type === 'button' || type === 'submit') return;
        el.disabled = disabled;
    });

    document.querySelectorAll('#simulationForm .add-instance, #simulationForm .remove-instance').forEach(btn => {
        btn.disabled = disabled;
    });

    if (disabled) {
        document.querySelectorAll('#simulationForm .field-container').forEach(container => {
            const overlay = document.createElement('div');
            overlay.className = 'disabled-field-overlay';
            overlay.style.cssText = 'position:absolute; inset:0; z-index:1; cursor:not-allowed;';
            overlay.setAttribute('data-bs-toggle', 'popover');
            overlay.setAttribute('data-bs-content', 'Extract metadata from files first to enable these fields.');
            overlay.setAttribute('data-bs-trigger', 'click');
            overlay.setAttribute('data-bs-placement', 'top');
            container.style.position = 'relative';
            container.appendChild(overlay);
            new bootstrap.Popover(overlay);
            overlay.addEventListener('show.bs.popover', () => {
                document.querySelectorAll('.disabled-field-overlay').forEach(other => {
                    if (other !== overlay) bootstrap.Popover.getInstance(other)?.hide();
                });
            });
        });
    } else {
        document.querySelectorAll('.disabled-field-overlay').forEach(overlay => {
            bootstrap.Popover.getInstance(overlay)?.dispose();
            overlay.remove();
        });
    }
}

/**
 * Persists current form field values to sessionStorage so they survive page refreshes.
 * Excludes file, button, submit, and hidden inputs.
 */
function saveFormState() {
    const state = {};
    document.querySelectorAll('#simulationForm input, #simulationForm select, #simulationForm textarea').forEach(el => {
        const type = (el.type || '').toLowerCase();
        if (type === 'file' || type === 'button' || type === 'submit' || type === 'hidden' || !el.name) return;
        state[el.name] = type === 'checkbox' ? el.checked : el.value;
    });
    sessionStorage.setItem('formState', JSON.stringify(state));
}

/**
 * Restores form field values from sessionStorage.
 * Skips submit and hidden inputs to avoid overwriting button labels or CSRF tokens.
 */
function restoreFormState() {
    const saved = sessionStorage.getItem('formState');
    if (!saved) return;
    Object.entries(JSON.parse(saved)).forEach(([name, value]) => {
        const el = document.querySelector(`[name="${CSS.escape(name)}"]`);
        if (!el) return;
        const type = (el.type || '').toLowerCase();
        if (type === 'submit' || type === 'hidden') return;  // never restore onto buttons
        type === 'checkbox' ? el.checked = value : el.value = value;
    });
}

// On page load: restore extracted metadata and form state from sessionStorage,
// or disable fields if the form is empty.
document.addEventListener('DOMContentLoaded', () => {
    const saved = sessionStorage.getItem('extractedMetadata');
    if (saved) {
        populateFields(JSON.parse(saved));
        restoreFormState();
        setFieldsDisabled(false);
        return;
    }
    const hasValues = Array.from(
        document.querySelectorAll('#simulationForm input, #simulationForm select, #simulationForm textarea')
    ).some(el => {
        const type = (el.type || '').toLowerCase();
        if (type === 'file' || type === 'button' || type === 'submit') return false;
        return type === 'checkbox' ? el.checked : el.value.trim() !== '';
    });
    if (!hasValues) setFieldsDisabled(true);
});

// Persist form state on any user input so it survives page refreshes.
document.addEventListener('input', function(e) {
    if (e.target.closest('#simulationForm') && e.target.type !== 'file') saveFormState();
});
// Persist form state on any user input so it survives page refreshes.
document.addEventListener('change', function(e) {
    if (e.target.closest('#simulationForm') && e.target.type !== 'file') saveFormState();
});

/**
 * Shows a dismissible Bootstrap alert fixed at the top of the page.
 * @param {string} html - HTML content for the alert body.
 * @param {string} [type='warning'] - Bootstrap alert variant (e.g. 'warning', 'danger', 'success').
 * @param {number} [timeout=50000] - Auto-dismiss delay in milliseconds. Pass 0 to disable.
 */
function showAlert(html, type = 'warning', timeout = 50000) {
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.style.cssText = 'position:fixed; top:1rem; left:50%; transform:translateX(-50%); z-index:1055; min-width:400px; max-width:700px; box-shadow:0 2px 8px rgba(0,0,0,.15);';
    alertEl.innerHTML = `${html}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(alertEl);
    if (timeout) {
        setTimeout(() => {
            alertEl.classList.remove('show');
            setTimeout(() => alertEl.remove(), 150);
        }, timeout);
    }
}

/**
 * Guards save/submit actions by checking that metadata has been extracted.
 * Uses native browser validation UI (`reportValidity`) to surface the error on the topology input.
 * @param {HTMLFormElement} form - The simulation form element.
 * @returns {boolean} `true` if extraction has been performed; `false` otherwise.
 */
function requireExtraction(form) {
    if (!sessionStorage.getItem('extractedMetadata')) {
        const topologyInput = document.querySelector('input[name="topology"]');
        topologyInput.setCustomValidity('Please extract metadata from your uploaded files first.');
        form.reportValidity();
        topologyInput.setCustomValidity('');
        return false;
    }
    return true;
}

/**
 * Validates the form by posting to `/webform` with a dry-run `save` flag,
 * then calls `onSuccess` if validation passes or displays errors as an alert.
 * @param {HTMLFormElement} form - The simulation form element.
 * @param {function} onSuccess - Callback invoked with the server response data on success.
 */
function validateAndSubmit(form, onSuccess) {
    const formData = new FormData(form);
    formData.append('save', '1');
    fetch('/webform', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.validation_errors && data.validation_errors.length > 0) {
                const [heading, ...errors] = data.validation_errors;
                const list = errors.map(err => `<li>${err}</li>`).join('');
                showAlert(`${heading}<ul class="mb-0 mt-1">${list}</ul>`, 'warning', 4000);
            } else if (data.success) {
                onSuccess(data);
            }
        })
        .catch(err => showAlert(`<strong>Error:</strong> ${err.message}`, 'danger', 5000));
}

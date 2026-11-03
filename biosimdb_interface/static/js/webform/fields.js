import { clearFormState } from './state.js';
import { clearValidationHighlights } from './validation.js';

/**
 * Populates form fields from extracted simulation metadata.
 * @param {Object} metadata - Nested metadata object keyed by section then field name.
 */
export function populateFields(metadata) {
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
        const header = instance.querySelector('.biosimdb-subsection-title');
        const numberEl = instance.querySelector('.instance-number');

        if (numberEl) {
            numberEl.textContent = newIndex;
        } else if (header) {
            header.textContent = header.textContent.replace(/\d+$/, newIndex);
        }

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
            const input = document.querySelector(`[name="${path}"]`);
            if (!input) return;
            input.value = Array.isArray(val[0])
                ? val.map(row => row.join(", ")).join("; ")
                : val.join(", ");
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
 * Appends a new instance to a repeatable field container from its template.
 * @param {HTMLElement} addButton - The clicked `.add-instance` button.
 */
export function addInstance(addButton) {
    const container = addButton.closest('.multiple-field-container');
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

    container.insertBefore(newInstance, addButton);
    renumberInstances(container);
    // Initialise popovers on the newly cloned instance
    newInstance.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => new bootstrap.Popover(el));
}

/**
 * Removes an instance from a repeatable container, keeping at least one.
 * @param {HTMLElement} removeButton - The clicked `.remove-instance` button.
 */
export function removeInstance(removeButton) {
    const container = removeButton.closest('.multiple-field-container');
    const instances = container.querySelectorAll('.field-instance');

    if (instances.length > 1) {
        removeButton.closest('.field-instance').remove();
        renumberInstances(container);
    }
}

/**
 * Enables or disables all editable form fields and adds/removes click-blocking overlays.
 * When disabled, an overlay with a Bootstrap popover is added to each `.field-container`
 * to prompt the user to extract metadata first.
 * @param {boolean} disabled - `true` to disable fields and add overlays; `false` to re-enable.
 */
export function setFieldsDisabled(disabled) {
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
 * Resets the form to its initial locked state: clears all field values,
 * removes cached extraction state, and disables editable fields.
 */
export function lockForm() {
    clearValidationHighlights();
    document.querySelectorAll('#simulationForm input, #simulationForm select, #simulationForm textarea').forEach(el => {
        const type = (el.type || '').toLowerCase();
        if (type === 'submit' || type === 'button' || type === 'hidden') return;

        if (type === 'checkbox' || type === 'radio') {
            el.checked = false;
        } else if (el.tagName === 'SELECT') {
            el.selectedIndex = 0;
        } else {
            el.value = '';
        }
    });

    document.querySelectorAll('#simulationForm .multiple-field-container').forEach(container => {
        container.querySelectorAll('.field-instance').forEach((instance, idx) => {
            if (idx > 0) instance.remove();
        });
        renumberInstances(container);
    });

    clearFormState();
    setFieldsDisabled(true);
}

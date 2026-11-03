import { escapeHtml, showAlert } from '../core/ui.js';

/**
 * Render validation errors as HTML.
 * Accepts the legacy flat form [heading, ...errors] or groups [{heading, errors}, ...].
 */
export function renderValidationErrors(items) {
    const groups = (items.length && typeof items[0] === 'object')
        ? items
        : [{ heading: items[0], errors: items.slice(1) }];

    return groups.map(({ heading, errors }) => {
        const rows = (errors || []).map(e => {
            const text = String(e);
            const nested = /^\s*↳/.test(text);
            if (nested) {
                const msg = text.replace(/^\s*↳\s*/, '');
                return `<li class="list-unstyled ms-4 text-muted">↳ ${escapeHtml(msg)}</li>`;
            }
            return `<li>${escapeHtml(text)}</li>`;
        }).join('');
        return `<strong>${escapeHtml(heading)}</strong>` +
               (rows ? `<ul class="mb-2 mt-1">${rows}</ul>` : '');
    }).join('');
}

/**
 * Converts a slash-delimited schema path to the matching HTML form field name.
 * Schema array indices are zero-based and are converted to the form's one-based indices.
 *
 * @param {string} path - Schema path, such as "/section/items/0/name".
 * @returns {string} Matching form field name, such as "section[items][1][name]".
 */
function schemaPathToFormName(path) {
    const parts = path.split('/').filter(Boolean);

    return parts.map((part, index) => {
        // LinkML array indices are zero-based; the form's repeated fields are one-based.
        const segment = /^\d+$/.test(part) ? String(Number(part) + 1) : part;
        return index === 0 ? segment : `[${segment}]`;
    }).join('');
}

/**
 * Extracts error messages from grouped validation errors or the legacy array format.
 *
 * @param {Array<Object|string>} items - Grouped errors or a legacy array with a heading first.
 * @returns {string[]} The validation error messages.
 */
function getValidationMessages(items) {
    if (!Array.isArray(items) || items.length === 0) return [];

    if (typeof items[0] === 'object') {
        return items.flatMap(group => group.errors || []);
    }

    // Legacy shape: [heading, ...error messages]
    return items.slice(1);
}

/**
 * Removes invalid styling from form controls.
 */
export function clearValidationHighlights() {
    document.querySelectorAll(
        '#simulationForm input.is-invalid, ' +
        '#simulationForm select.is-invalid, ' +
        '#simulationForm textarea.is-invalid'
    ).forEach(control => control.classList.remove('is-invalid'));
}

/**
 * Converts a dotted form-conversion error path to bracket notation.
 * For example, "section.field.1.sub" becomes "section[field][1][sub]".
 *
 * @param {string} path - Dotted field path; numeric indices are already one-based.
 * @returns {string} The matching HTML form field name.
 */
function dottedPathToFormName(path) {
    return path.split('.').map((p, i) => (i === 0 ? p : `[${p}]`)).join('');
}

/**
 * Extracts a form field name from a schema-validation or form-conversion error.
 *
 * @param {string} error - Validation error message.
 * @returns {string|null} Matching form field name, or null if the message has no field path.
 */
function errorToFormName(error) {
    const text = String(error);

    // LinkML validation: "... in /section/field/0/sub"
    const schema = text.match(/\bin (\/\S+)\s*$/);
    if (schema) return schemaPathToFormName(schema[1]);

    // FormConversionError: "section.field.1.sub: message"
    const conv = text.match(/^([\w.]+):\s/);
    return conv ? dottedPathToFormName(conv[1]) : null;
}

/**
 * Highlights controls corresponding to validation errors and focuses the first one.
 *
 * @param {Array<Object|string>} validationErrors - Grouped errors or a legacy error array.
 */
function highlightValidationFields(validationErrors) {
    const controls = [
        ...document.querySelectorAll(
            '#simulationForm input, #simulationForm select, #simulationForm textarea'
        ),
    ];

    controls.forEach(control => control.classList.remove('is-invalid'));

    for (const error of getValidationMessages(validationErrors)) {
        const formName = errorToFormName(error);
        if (!formName) continue;

        controls
            .filter(control =>
                control.name === formName ||
                control.name === `${formName}[]` ||
                control.name.startsWith(`${formName}[`)
            )
            .forEach(control => control.classList.add('is-invalid'));
    }

    // This only guides the user to the first highlighted field.
    const firstInvalid = controls.find(control => control.classList.contains('is-invalid'));
    firstInvalid?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    firstInvalid?.focus({ preventScroll: true });
}

/** Highlight invalid fields and show the grouped errors in an alert. */
export function showValidationErrors(validationErrors) {
    highlightValidationFields(validationErrors);
    showAlert(renderValidationErrors(validationErrors), 'warning', 30000);
}

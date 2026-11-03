/**
 * Fade out and remove an existing Bootstrap alert after a delay.
 *
 * @param {HTMLElement} alertEl - Rendered Bootstrap alert element.
 * @param {number} timeout - Delay in milliseconds.
 */
export function dismissAlertAfter(alertEl, timeout = 5000) {
    setTimeout(() => {
        alertEl.classList.remove('show');
        setTimeout(() => alertEl.remove(), 150);
    }, timeout);
}

/** Auto-dismiss alerts rendered by the server (e.g. flashed messages). */
export function autoDismissAlerts(timeout = 10000) {
    document.querySelectorAll('.alert').forEach((alertEl) => {
        dismissAlertAfter(alertEl, timeout);
    });
}

/**
 * Shows a dismissible Bootstrap alert fixed at the top of the page.
 * @param {string} html - HTML content for the alert body.
 * @param {string} [type='warning'] - Bootstrap alert variant (e.g. 'warning', 'danger', 'success').
 * @param {number} [timeout=50000] - Auto-dismiss delay in milliseconds. Pass 0 to disable.
 */
export function showAlert(html, type = 'warning', timeout = 50000) {
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.style.cssText = 'position:fixed; top:1rem; left:50%; transform:translateX(-50%); z-index:1055; min-width:400px; max-width:700px; box-shadow:0 2px 8px rgba(0,0,0,.15);';
    alertEl.innerHTML = `${html}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    document.body.appendChild(alertEl);
    if (timeout) dismissAlertAfter(alertEl, timeout);
}

export function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

/**
 * Shows a full-page wait overlay and puts a button into a disabled "working" state.
 * @param {HTMLElement} button - The button that triggered the action.
 * @param {string} loadingText - Text to show on the button while working.
 */
export function showLoadingOverlay(button, loadingText) {
    button.dataset.originalText = button.textContent;
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status"></span>${loadingText}`;

    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.style.cssText = 'position:fixed; inset:0; z-index:2000; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,0.5);';
    overlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    document.body.appendChild(overlay);
}

/**
 * Restores a button's original label and removes the wait overlay.
 * @param {HTMLElement} button - The button to restore.
 */
export function hideLoadingOverlay(button) {
    button.disabled = false;
    button.textContent = button.dataset.originalText ?? button.textContent;
    delete button.dataset.originalText;
    document.getElementById('loading-overlay')?.remove();
}

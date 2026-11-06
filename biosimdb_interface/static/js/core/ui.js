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
 * @param {boolean} [withSteps=false] - Show an empty panel for a stepper instead of a spinner.
 * @returns {HTMLElement|null} The panel to render a stepper into when `withSteps` is true.
 */
export function showLoadingOverlay(button, loadingText, withSteps = false) {
    button.dataset.originalText = button.textContent;
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status"></span>${loadingText}`;

    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.style.cssText = 'position:fixed; inset:0; z-index:2000; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,0.5);';
    overlay.innerHTML = withSteps
        ? '<div id="loading-steps" class="card shadow p-3" style="min-width:360px; max-width:600px;"></div>'
        : '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    document.body.appendChild(overlay);
    return withSteps ? overlay.firstElementChild : null;
}

/**
 * Render a list of progress steps into a container.
 * @param {HTMLElement} container - Element to render into.
 * @param {{id: string, label: string}[]} steps - Ordered steps.
 * @returns {function(string, string, ?number, string=): void} update(id, state, fraction, detail)
 *   where state is 'pending' | 'active' | 'done' | 'error'; fraction is 0-1 or null
 *   for an indeterminate bar.
 */
export function createStepper(container, steps) {
    container.innerHTML = steps.map(s => `
        <div class="step mb-2 text-start" data-step="${escapeHtml(s.id)}">
            <span class="icon me-2"></span><span class="label">${escapeHtml(s.label)}</span>
            <div class="detail small text-muted ms-4"></div>
            <div class="progress ms-4 mt-1 d-none" style="height:6px">
                <div class="progress-bar"></div>
            </div>
        </div>`).join('');

    const icons = { pending: '○', active: '⏳', done: '✅', error: '❌' };
    return (id, state, fraction = null, detail = '') => {
        const el = [...container.querySelectorAll('.step')].find(e => e.dataset.step === id);
        if (!el) return;
        el.classList.toggle('text-muted', state === 'pending');
        el.querySelector('.icon').textContent = icons[state];
        el.querySelector('.detail').textContent = state === 'active' ? detail : '';
        el.querySelector('.progress').classList.toggle('d-none', state !== 'active');
        const bar = el.querySelector('.progress-bar');
        bar.classList.toggle('progress-bar-striped', fraction == null);
        bar.classList.toggle('progress-bar-animated', fraction == null);
        bar.style.width = fraction == null ? '100%' : `${Math.round(fraction * 100)}%`;
    };
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

/**
 * Return a UUID unique to this browser tab.
 * sessionStorage is intentionally tab-scoped, unlike localStorage.
 */
export function getWorkflowId() {
    const key = 'biosimdbWorkflowId';
    let workflowId = sessionStorage.getItem(key);

    if (!workflowId) {
        workflowId = crypto.randomUUID();
        sessionStorage.setItem(key, workflowId);
    }

    return workflowId;
}

/** Add the current tab's workflow ID to a request payload. */
export function addWorkflowId(formData) {
    formData.set('workflow_id', getWorkflowId());
    return formData;
}

/**
 * Delete the current tab's server-side workflow without affecting new work.
 */
export function clearWorkflow() {
    const workflowId = sessionStorage.getItem('biosimdbWorkflowId');
    if (!workflowId) return;

    sessionStorage.removeItem('biosimdbWorkflowId');

    const formData = new FormData();
    formData.set('workflow_id', workflowId);

    fetch(window.APPLICATION_BASE + '/clear_extraction', {
        method: 'POST',
        body: formData,
    });
}

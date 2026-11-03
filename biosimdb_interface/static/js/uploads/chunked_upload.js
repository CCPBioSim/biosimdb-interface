/** Uploads files to the server in parallel, resumable chunks. */
export class ChunkedUploader {
    constructor(workflowId, { concurrency = 4, retries = 4 } = {}) {
        this.workflowId = workflowId;
        this.concurrency = concurrency;
        this.retries = retries;
        this.base = `${window.APPLICATION_BASE}/uploads`;
    }

    /** POST JSON and return the parsed body, throwing the server error on failure. */
    async _post(path, payload) {
        const r = await fetch(`${this.base}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ workflow_id: this.workflowId, ...payload }),
        });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || 'Upload failed.');
        return data;
    }

    /** PUT one chunk, retrying network/5xx errors with exponential backoff. */
    async _sendChunk(file, init, index) {
        const start = index * init.chunk_size;
        const body = file.slice(start, Math.min(start + init.chunk_size, file.size));
        const url = `${this.base}/${init.upload_id}/chunks/${index}` +
            `?workflow_id=${encodeURIComponent(this.workflowId)}`;

        for (let attempt = 0; ; attempt++) {
            try {
                const r = await fetch(url, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/octet-stream' },
                    body,
                });
                if (r.ok) return;
                if (r.status < 500) {
                    throw Object.assign(new Error((await r.json()).error), { fatal: true });
                }
            } catch (err) {
                if (err.fatal || attempt >= this.retries) throw err;
            }
            await new Promise(res => setTimeout(res, 500 * 2 ** attempt));
        }
    }

    /** Upload a File; resolves to its server-side filename. */
    async upload(file, onProgress = () => {}) {
        const init = await this._post('/init', { filename: file.name, size: file.size });
        const pending = [];
        for (let i = 0; i < init.total_chunks; i++) {
            if (!init.received.includes(i)) pending.push(i);
        }

        let done = init.total_chunks - pending.length;
        const worker = async () => {
            while (pending.length) {
                await this._sendChunk(file, init, pending.shift());
                onProgress(++done / init.total_chunks);
            }
        };
        const workers = Math.min(this.concurrency, pending.length);
        await Promise.all(Array.from({ length: workers }, worker));

        return (await this._post(`/${init.upload_id}/complete`, {})).filename;
    }
}

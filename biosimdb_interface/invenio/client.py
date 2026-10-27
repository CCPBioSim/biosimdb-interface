"""Upload files to an InvenioRDM instance draft record.

By default the file is sent as a multipart (chunked) upload: each part is PUT
straight to object storage via a pre-signed URL, so no single request stays
open for the whole transfer.
If multipart fails for a smaller file, use one PUT through the repository.

Adapted from a script provided by Andrew Harper, STFC.
"""

import json
from pathlib import Path

import requests
from flask import current_app

from biosimdb_interface.core.cancellation import UploadCancelled

from .multipart import upload_file

# S3 multipart limits: parts must be >= 5 MiB (except the last), at most 10000 parts.
PART_SIZE = 100  # 100 MiB; S3 requires parts of at least 5 MiB


def run_record_upload(
    api_url, api_key, metadata_path, files, community, cancelled=lambda: False
):
    api = api_url.removesuffix("/api").rstrip("/")
    s = requests.Session()
    s.headers.update(
        {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
    )

    with Path(metadata_path).open("r", encoding="utf8") as file:
        data = json.load(file)

    r = s.post(f"{api}/api/records", json=data)
    r.raise_for_status()
    draft_id = r.json()["id"]

    try:
        for file in files:
            if cancelled():
                raise UploadCancelled
            path = Path(file)
            commit_url = upload_file(
                s,
                api,
                draft_id,
                path,
                path.name,
                path.stat().st_size,
                PART_SIZE,
                cancelled=cancelled,
            )
            r = s.post(commit_url)
            r.raise_for_status()

        if cancelled():
            raise UploadCancelled
        r = s.get(f"{api}/api/communities/{community}")
        r.raise_for_status()
        r = s.put(
            f"{api}/api/records/{draft_id}/draft/review",
            json={
                "receiver": {"community": r.json()["id"]},
                "type": "community-submission",
            },
        )
        r.raise_for_status()
    except BaseException:  # cancel, HTTP error, SystemExit...
        r = s.delete(f"{api}/api/records/{draft_id}/draft", timeout=30)
        current_app.logger.info(f"Draft {draft_id} delete -> HTTP {r.status_code}")
        raise
    return None, draft_id

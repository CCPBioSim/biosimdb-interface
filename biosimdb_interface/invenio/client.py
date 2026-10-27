#!/usr/bin/env python
"""Upload files to an InvenioRDM instance draft record."""

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
    """Create a draft, upload its files, and submit it to a community.

    Creates a draft using the metadata JSON, uploads each file, then submits
    the draft for review by the specified community. If an upload or
    submission step fails, attempts to delete the draft and re-raises the
    error.

    Args:
        api_url (str): InvenioRDM base URL, with or without the ``/api`` suffix.
        api_key (str): Bearer token for the InvenioRDM API.
        metadata_path (str | Path): Path to the record metadata JSON file.
        files (Iterable[str | Path]): Files to upload.
        community (str): Community identifier to submit the draft to.
        cancelled (Callable[[], bool]): Callback that returns ``True`` when
            the upload should be cancelled.

    Returns:
        tuple: ``(None, draft_id)`` for the created record.

    Raises:
        UploadCancelled: If cancellation is requested.
        requests.RequestException: If an API request fails.
        Exception: If a file transfer or API response is unsuccessful.
    """
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
    return draft_id

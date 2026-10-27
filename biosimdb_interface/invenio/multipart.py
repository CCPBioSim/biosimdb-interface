"""Upload files to an InvenioRDM instance draft record.

By default the file is sent as a multipart (chunked) upload: each part is PUT
straight to object storage via a pre-signed URL, so no single request stays
open for the whole transfer.
If multipart fails for a smaller file, use one PUT through the repository.

Adapted from a script provided by Andrew Harper, STFC.
"""

import logging  # Don't use current_app in threads
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests
from flask import current_app

from biosimdb_interface.core.cancellation import MultipartTooSlow, UploadCancelled

from .progress import PartReader, Progress, ProgressReader

log = logging.getLogger(__name__)

# S3 multipart limits: parts must be >= 5 MiB (except the last), at most 10000 parts.
MIN_PART_SIZE = 5 * 1024 * 1024
MAX_PARTS = 10000
PART_RETRIES = 3  # retries for each file part
SINGLE_MAX = 1 * 1024**3  # at or below this, a fallback to a single PUT is allowed
SLOW_AFTER = 120  # seconds before multipart is judged too slow


def check(r, expected, what):
    if r.status_code == expected:
        return
    hint = {
        401: "\n  The token was rejected - check it is correct and has not been revoked.",
        403: (
            "\n  Permission denied - check your token is correct and not revoked, and that"
            "\n  the draft is one you own or can edit."
        ),
        404: "\n  Not found - check the draft ID and that it is still a draft.",
    }.get(r.status_code, "")
    raise Exception(f"{what} failed: HTTP {r.status_code}{hint}\n{r.text[:2000]}")


def upload_single(s, api, draft_id, path, key, size, cancelled=lambda: False):
    r = s.post(f"{api}/api/records/{draft_id}/draft/files", json=[{"key": key}])
    check(r, 201, "File init")
    links = next(e["links"] for e in r.json()["entries"] if e["key"] == key)

    progress = Progress(size)
    current_app.logger.info(
        f"Uploading {key} ({size / 1e9:.2f} GB) in one PUT at {time.strftime('%H:%M:%S %Z')}"
    )
    try:
        r = s.put(
            links["content"],
            data=ProgressReader(path, progress, cancelled),
            headers={"Content-Type": "application/octet-stream"},
        )
    except UploadCancelled:
        raise
    except requests.RequestException as e:
        if progress.sent == size:
            where = (
                f"whole body sent - died {progress.wait_time()} into waiting "
                f"for the server's response"
            )
        else:
            where = "died mid-transfer"
        current_app.logger.error(
            f"\nUpload FAILED at {time.strftime('%H:%M:%S %Z')}: {e!r}\n"
            f"  sent {progress.status()}\n  {where}"
        )
    current_app.logger.info(
        f"Server responded HTTP {r.status_code}, {progress.wait_time()} after the last byte was sent"
    )
    current_app.logger.info(f"  x-request-id: {r.headers.get('x-request-id')}")
    check(r, 200, "File upload")
    return links["commit"]


def put_part(s3, path, part, url, part_size, size, progress, cancelled):
    """PUT one part to its pre-signed S3 URL, retrying on failure."""
    if cancelled():
        raise UploadCancelled
    offset = (part - 1) * part_size
    length = min(part_size, size - offset)
    for attempt in range(1, PART_RETRIES + 1):
        body = PartReader(path, offset, length, cancelled)
        try:
            r = s3.put(url, data=body, timeout=(10, 600))
            if r.status_code == 200:
                progress.add(length)
                log.debug(f"part {part} done: {progress.status()}")
                return
            err = f"HTTP {r.status_code}: {r.text[:500]}"
        except UploadCancelled:
            raise
        except requests.RequestException as e:
            err = repr(e)
        finally:
            body.close()
        log.info(
            f"  part {part} attempt {attempt}/{PART_RETRIES} failed: {err}", flush=True
        )
        time.sleep(2**attempt)
    raise RuntimeError(f"part {part} failed after {PART_RETRIES} attempts: {err}")


def upload_multipart(
    s, api, draft_id, path, key, size, chunk_mb, workers, cancelled=lambda: False
):
    part_size = max(chunk_mb * 1024 * 1024, MIN_PART_SIZE, math.ceil(size / MAX_PARTS))
    parts = max(1, math.ceil(size / part_size))

    r = s.post(
        f"{api}/api/records/{draft_id}/draft/files",
        json=[
            {
                "key": key,
                "size": size,
                "transfer": {"type": "M", "parts": parts, "part_size": part_size},
            }
        ],
    )
    check(r, 201, "Multipart file init")
    links = next(e["links"] for e in r.json()["entries"] if e["key"] == key)
    part_links = links.get("parts")
    if not part_links or len(part_links) != parts:
        current_app.logger.error(
            f"Multipart init returned {len(part_links or [])} part links, "
            f"expected {parts}:\n{links}"
        )

    progress = Progress(size)
    current_app.logger.debug(
        f"Uploading {key} ({size / 1e9:.2f} GB) as {parts} x {part_size / 2**20:.0f} MiB "
        f"parts, {workers} at a time, at {time.strftime('%H:%M:%S %Z')}"
    )
    # Pre-signed URLs carry their own auth - don't send the Invenio token to S3.
    s3 = requests.Session()
    s3.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=workers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                put_part,
                s3,
                path,
                p["part"],
                p["url"],
                part_size,
                size,
                progress,
                cancelled,
            )
            for p in part_links
        ]
        try:
            for f in as_completed(futures):
                f.result()
        except (RuntimeError, UploadCancelled, MultipartTooSlow) as e:
            for f in futures:
                f.cancel()
            if isinstance(e, (UploadCancelled, MultipartTooSlow)):
                raise
            log.error(
                f"\nUpload FAILED at {time.strftime('%H:%M:%S %Z')}: {e}\n"
                f"  sent {progress.status()}"
            )
    current_app.logger.debug(f"All {parts} parts uploaded")
    return links["commit"]


def upload_file(s, api, draft_id, path, key, size, chunk_mb, cancelled=lambda: False):
    """Upload one file; returns its commit URL."""
    if size > SINGLE_MAX:
        return upload_multipart(
            s, api, draft_id, path, key, size, chunk_mb, 1, cancelled
        )

    deadline = time.monotonic() + SLOW_AFTER

    def stop():
        if cancelled():
            raise UploadCancelled
        if time.monotonic() > deadline:
            raise MultipartTooSlow
        return False

    try:
        return upload_multipart(s, api, draft_id, path, key, size, chunk_mb, 1, stop)
    except MultipartTooSlow:
        current_app.logger.info(
            f"Multipart for {key} exceeded {SLOW_AFTER}s; falling back to single PUT",
            flush=True,
        )
        # Discard the half-initialised multipart entry before re-initialising the key.
        s.delete(
            f"{api}/api/records/{draft_id}/draft/files/{quote(key, safe='')}",
            timeout=30,
        )
        return upload_single(s, api, draft_id, path, key, size, cancelled)

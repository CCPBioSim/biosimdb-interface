"""Resumable chunked uploads written in place inside a workflow directory."""

import hashlib
import json
import os
import shutil

from werkzeug.utils import secure_filename

STAGING_DIRNAME = ".staging"
DEFAULT_CHUNK_SIZE = 32 * 1024 * 1024
_READ_SIZE = 1024 * 1024


class UploadError(Exception):
    """Client-facing upload error carrying an HTTP status code."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


class ChunkedUpload:
    """One file being uploaded in chunks into a workflow directory.

    Chunks are written at their offset into a preallocated ``data.part`` file.
    Each finished chunk leaves an empty marker file, so any worker process can
    serve any chunk. ``complete`` renames the file into place (no copy).
    """

    def __init__(self, tmpdir, upload_id):
        if not (
            len(upload_id) == 32 and all(c in "0123456789abcdef" for c in upload_id)
        ):
            raise UploadError("Invalid upload ID.")
        self.tmpdir = tmpdir
        self.upload_id = upload_id
        self.staging = os.path.join(tmpdir, STAGING_DIRNAME, upload_id)
        self.part_path = os.path.join(self.staging, "data.part")
        self._meta_path = os.path.join(self.staging, "meta.json")
        self.meta = None

    @staticmethod
    def make_id(filename, size):
        """Deterministic ID so an interrupted upload of the same file resumes."""
        return hashlib.sha256(f"{filename}:{size}".encode()).hexdigest()[:32]

    @classmethod
    def start(cls, tmpdir, filename, size, max_bytes, chunk_size=DEFAULT_CHUNK_SIZE):
        """Start or resume an upload after validating name, size and free space."""
        name = secure_filename(filename or "")
        if not name:
            raise UploadError("Invalid filename.")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise UploadError("Invalid file size.")
        if size > max_bytes:
            raise UploadError("File exceeds the maximum allowed size.", 413)

        upload = cls(tmpdir, cls.make_id(name, size))
        if not os.path.isfile(upload._meta_path):
            if shutil.disk_usage(tmpdir).free < size:
                raise UploadError("Not enough disk space on the server.", 507)
            upload._create(name, size, chunk_size)
        return upload.load()

    def _create(self, name, size, chunk_size):
        """Preallocate the data file and persist metadata."""
        os.makedirs(self.staging, exist_ok=True)
        fd = os.open(self.part_path, os.O_WRONLY | os.O_CREAT, 0o640)
        try:
            if hasattr(os, "posix_fallocate"):
                os.posix_fallocate(fd, 0, size)
            else:
                os.ftruncate(fd, size)
        except OSError as exc:
            shutil.rmtree(self.staging, ignore_errors=True)
            raise UploadError("Not enough disk space on the server.", 507) from exc
        finally:
            os.close(fd)

        meta = {
            "name": name,
            "size": size,
            "chunk_size": chunk_size,
            "total": -(-size // chunk_size),
        }
        with open(self._meta_path + ".tmp", "w") as f:
            json.dump(meta, f)
        os.replace(self._meta_path + ".tmp", self._meta_path)

    def load(self):
        """Load metadata from disk; raises 404 for an unknown upload."""
        try:
            with open(self._meta_path) as f:
                self.meta = json.load(f)
        except FileNotFoundError as exc:
            raise UploadError("Unknown upload. Please restart it.", 404) from exc
        return self

    def received(self):
        """Return sorted indices of chunks that were fully written."""
        return sorted(int(n) for n in os.listdir(self.staging) if n.isdigit())

    def describe(self):
        """Return the JSON-ready state sent to the client."""
        return {
            "upload_id": self.upload_id,
            "filename": self.meta["name"],
            "chunk_size": self.meta["chunk_size"],
            "total_chunks": self.meta["total"],
            "received": self.received(),
        }

    def write_chunk(self, index, stream, content_length):
        """Write one chunk at its offset; mark it received only when complete."""
        meta = self.meta
        if not 0 <= index < meta["total"]:
            raise UploadError("Chunk index out of range.")

        offset = index * meta["chunk_size"]
        expected = min(meta["chunk_size"], meta["size"] - offset)
        if content_length != expected:
            raise UploadError(f"Chunk must be exactly {expected} bytes.")

        written = 0
        fd = os.open(self.part_path, os.O_WRONLY)
        try:
            while written < expected:
                buf = stream.read(min(_READ_SIZE, expected - written))
                if not buf:
                    break
                os.pwrite(fd, buf, offset + written)
                written += len(buf)
        finally:
            os.close(fd)

        if written != expected:
            raise UploadError("Incomplete chunk received.")
        open(os.path.join(self.staging, str(index)), "wb").close()

    def complete(self, sha256=None):
        """Verify the upload and atomically move it into the workflow directory.

        Returns:
            str: Final path of the uploaded file.
        """
        missing = set(range(self.meta["total"])) - set(self.received())
        if missing:
            raise UploadError(f"Missing {len(missing)} chunk(s).", 409)
        if sha256 and self._sha256() != sha256.lower():
            raise UploadError("Checksum mismatch. Please re-upload.", 422)

        final = os.path.join(self.tmpdir, self.meta["name"])
        os.replace(self.part_path, final)
        self.abort()
        return final

    def _sha256(self):
        """Return the SHA-256 hex digest of the assembled file."""
        digest = hashlib.sha256()
        with open(self.part_path, "rb") as f:
            while block := f.read(8 * _READ_SIZE):
                digest.update(block)
        return digest.hexdigest()

    def abort(self):
        """Discard the staging directory."""
        shutil.rmtree(self.staging, ignore_errors=True)


def resolve_uploaded_file(tmpdir, filename):
    """Return the path of a completed upload; reject names that are not plain files."""
    name = secure_filename(filename or "")
    path = os.path.join(tmpdir, name)
    if not name or name != filename or not os.path.isfile(path):
        raise UploadError(f"Uploaded file not found: {filename}", 404)
    return path

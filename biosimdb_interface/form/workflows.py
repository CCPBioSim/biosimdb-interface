"""Server-side, tab-scoped temporary workflow management."""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field

from .utils import make_upload_tmpdir


class WorkflowNotFound(Exception):
    """Raised when a workflow ID is missing, invalid, or expired."""


@dataclass
class Workflow:
    """State for one browser-tab extraction/submission workflow."""

    workflow_id: str
    tmpdir: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "extracted"


class WorkflowStore:
    """Maintain isolated temporary directories keyed by browser workflow ID."""

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._workflows: dict[str, Workflow] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _validate_id(workflow_id: str | None) -> str:
        """Validate and normalize a client-generated UUID workflow ID."""
        try:
            return str(uuid.UUID(str(workflow_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise WorkflowNotFound("Invalid upload session.") from exc

    def reset(self, workflow_id: str) -> Workflow:
        """Delete only this workflow's old directory and create a new one."""
        workflow_id = self._validate_id(workflow_id)

        with self._lock:
            old = self._workflows.pop(workflow_id, None)
            if old:
                shutil.rmtree(old.tmpdir, ignore_errors=True)

            workflow = Workflow(
                workflow_id=workflow_id,
                tmpdir=make_upload_tmpdir("biosimdb_submission_"),
            )
            self._workflows[workflow_id] = workflow
            return workflow

    def get(self, workflow_id: str | None) -> Workflow:
        """Return an active workflow or raise when it is absent/expired."""
        workflow_id = self._validate_id(workflow_id)

        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                raise WorkflowNotFound(
                    "This upload session no longer exists. Please extract again."
                )

            if time.time() - workflow.updated_at > self.ttl_seconds:
                self.delete(workflow_id)
                raise WorkflowNotFound(
                    "This upload session expired. Please extract again."
                )

            workflow.updated_at = time.time()
            return workflow

    def delete(self, workflow_id: str | None) -> None:
        """Delete only the directory belonging to one workflow ID."""
        try:
            workflow_id = self._validate_id(workflow_id)
        except WorkflowNotFound:
            return

        with self._lock:
            workflow = self._workflows.pop(workflow_id, None)
            if workflow:
                shutil.rmtree(workflow.tmpdir, ignore_errors=True)

    def cleanup_expired(self) -> int:
        """Delete abandoned workflow directories and return the count removed."""
        now = time.time()
        with self._lock:
            expired = [
                workflow_id
                for workflow_id, workflow in self._workflows.items()
                if now - workflow.updated_at > self.ttl_seconds
            ]

        for workflow_id in expired:
            self.delete(workflow_id)

        return len(expired)

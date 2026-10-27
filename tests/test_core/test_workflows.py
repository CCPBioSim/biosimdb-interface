import os
import uuid

import pytest

from biosimdb_interface.core.workflows import WorkflowNotFound, WorkflowStore


@pytest.fixture
def store(app, tmp_path):
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    with app.app_context():
        yield WorkflowStore(ttl_seconds=60)


def test_reset_creates_directory(store):
    workflow_id = str(uuid.uuid4())
    workflow = store.reset(workflow_id)
    assert os.path.isdir(workflow.tmpdir)
    assert workflow_id in workflow.tmpdir


def test_invalid_id_raises(store):
    with pytest.raises(WorkflowNotFound):
        store.get("not-a-uuid")


def test_unknown_id_raises(store):
    with pytest.raises(WorkflowNotFound):
        store.get(str(uuid.uuid4()))


def test_get_recovers_workflow_created_by_another_worker(store):
    workflow_id = str(uuid.uuid4())
    created = store.reset(workflow_id)

    other_worker = WorkflowStore(ttl_seconds=60)
    recovered = other_worker.get(workflow_id)

    assert recovered.tmpdir == created.tmpdir


def test_expired_workflow_is_deleted(store):
    workflow_id = str(uuid.uuid4())
    workflow = store.reset(workflow_id)
    workflow.updated_at -= 120

    with pytest.raises(WorkflowNotFound):
        store.get(workflow_id)
    assert not os.path.exists(workflow.tmpdir)


def test_delete_removes_directory(store):
    workflow = store.reset(str(uuid.uuid4()))
    store.delete(workflow.workflow_id)
    assert not os.path.exists(workflow.tmpdir)


def test_cleanup_expired_removes_only_expired(store):
    old = store.reset(str(uuid.uuid4()))
    new = store.reset(str(uuid.uuid4()))
    old.updated_at -= 120

    assert store.cleanup_expired() == 1
    assert not os.path.exists(old.tmpdir)
    assert os.path.isdir(new.tmpdir)

import uuid

import pytest


@pytest.fixture
def wid(app):
    wid = str(uuid.uuid4())
    yield wid
    with app.app_context():
        app.extensions["workflow_store"].delete(wid)


def test_full_upload_flow(app, client, wid):
    app.config["UPLOAD_CHUNK_SIZE"] = 4
    data = b"0123456789"

    init = client.post(
        "/uploads/init", json={"workflow_id": wid, "filename": "t.gro", "size": 10}
    ).get_json()
    assert init["total_chunks"] == 3

    for i in range(3):
        r = client.put(
            f"/uploads/{init['upload_id']}/chunks/{i}?workflow_id={wid}",
            data=data[i * 4 : i * 4 + 4],
            content_type="application/octet-stream",
        )
        assert r.status_code == 200

    r = client.post(f"/uploads/{init['upload_id']}/complete", json={"workflow_id": wid})
    assert r.get_json() == {"filename": "t.gro"}

    with app.app_context():
        tmpdir = app.extensions["workflow_store"].get(wid).tmpdir
    assert open(f"{tmpdir}/t.gro", "rb").read() == data


def test_invalid_workflow_rejected(client):
    r = client.post(
        "/uploads/init", json={"workflow_id": "nope", "filename": "a", "size": 1}
    )
    assert r.status_code == 400


def test_chunk_for_other_workflow_not_found(app, client, wid):
    init = client.post(
        "/uploads/init", json={"workflow_id": wid, "filename": "t.gro", "size": 4}
    ).get_json()
    other = str(uuid.uuid4())
    try:
        with app.app_context():
            app.extensions["workflow_store"].reset(other)
        r = client.put(
            f"/uploads/{init['upload_id']}/chunks/0?workflow_id={other}", data=b"abcd"
        )
        assert r.status_code == 404
    finally:
        with app.app_context():
            app.extensions["workflow_store"].delete(other)


def test_oversize_rejected(app, client, wid):
    app.config["MAX_UPLOAD_BYTES"] = 5
    r = client.post(
        "/uploads/init", json={"workflow_id": wid, "filename": "a", "size": 6}
    )
    assert r.status_code == 413

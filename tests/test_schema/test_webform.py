from biosimdb_interface.schema import webform


def test_get_simulation_metadata_caches_until_file_changes(monkeypatch, tmp_path):
    """Loads once per file modification time and reloads when it changes."""
    schema_path = tmp_path / "webform-schema.json"
    schema_path.write_text("{}")
    monkeypatch.setenv("WEBFORM_SCHEMA_PATH", str(schema_path))
    monkeypatch.setattr(webform, "_cache", {"schema": None, "mtime": None})

    mtime = [1.0]
    monkeypatch.setattr(webform.os.path, "getmtime", lambda path: mtime[0])

    loaded = []

    class FakeSchemaPopulator:
        def __init__(self, schema_path):
            self.schema_path = schema_path

        def load_schema(self):
            schema = {"load_number": len(loaded) + 1}
            loaded.append(schema)
            return schema

    monkeypatch.setattr(webform, "SchemaPopulator", FakeSchemaPopulator)

    first = webform.get_simulation_metadata()
    cached = webform.get_simulation_metadata()

    assert first == {"load_number": 1}
    assert cached is first
    assert len(loaded) == 1

    mtime[0] = 2.0
    reloaded = webform.get_simulation_metadata()

    assert reloaded == {"load_number": 2}
    assert len(loaded) == 2


def test_get_simulation_metadata_returns_empty_when_path_is_missing(monkeypatch):
    """Returns an empty schema if the configured path does not exist."""
    monkeypatch.setenv("WEBFORM_SCHEMA_PATH", "/path/that/does/not/exist.json")
    monkeypatch.setattr(webform, "_cache", {"schema": None, "mtime": None})

    assert webform.get_simulation_metadata() == {}

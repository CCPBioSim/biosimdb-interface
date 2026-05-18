import json, tempfile, os
from unittest.mock import patch
from biosimdb_interface.schema.helpers import SchemaPopulator

def test_load_schema_from_file():
    data = {"key": "value"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = f.name
    try:
        sp = SchemaPopulator(schema_path=path)
        result = sp.load_schema()
        assert result == data
    finally:
        os.unlink(path)

def test_main_prints_schema(capsys):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"a": 1}, f)
        path = f.name
    try:
        with patch("sys.argv", ["helpers.py", path]):
            from biosimdb_interface.schema.helpers import main
            main()
        captured = capsys.readouterr()
        assert '"a": 1' in captured.out
    finally:
        os.unlink(path)

def test_main_writes_output_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"b": 2}, f)
        in_path = f.name
    out_path = in_path + ".out.json"
    try:
        with patch("sys.argv", ["helpers.py", in_path, "--output", out_path]):
            from biosimdb_interface.schema.helpers import main
            main()
        with open(out_path) as f:
            assert json.load(f) == {"b": 2}
    finally:
        os.unlink(in_path)
        os.unlink(out_path)
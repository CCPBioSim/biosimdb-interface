from biosimdb_interface.form.utils import form_to_json, fill_invenio_metadata

def test_form_to_json_nested():
    data = {"simulation[1][name]": "test", "save": "1"}
    result = form_to_json(data)
    assert result == {"simulation": [{"name": "test"}]}

def test_form_to_json_skips_template():
    data = {"simulation[TEMPLATE][name]": "skip", "simulation[1][name]": "keep"}
    result = form_to_json(data)
    assert "TEMPLATE" not in str(result)

def test_form_to_json_vector_value():
    data = {"sim[1][vector_value]": "1.0, 2.0, 3.0"}
    result = form_to_json(data)
    assert result["sim"][0]["vector_value"] == [1.0, 2.0, 3.0]

def test_fill_invenio_metadata_returns_dict():
    result = fill_invenio_metadata({})
    assert isinstance(result, dict)
    assert "custom_fields" in result

def test_form_to_json_direct_list_assignment():
    """Numeric index as final path part sets list item directly."""
    from biosimdb_interface.form.utils import _set_nested
    d = {}
    _set_nested(d, ["items", "1"], "val")
    assert d == {"items": ["val"]}
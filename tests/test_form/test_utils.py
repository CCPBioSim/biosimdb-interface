from werkzeug.datastructures import ImmutableMultiDict

from biosimdb_interface.form.utils import fill_invenio_metadata, form_to_json


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


def test_form_to_json_multiselect_repeated_keys():
    data = ImmutableMultiDict(
        [
            ("analysis[method][]", "RMSD"),
            ("analysis[method][]", "DSSP"),
        ]
    )
    result = form_to_json(data)
    assert result == {"analysis": {"method": ["RMSD", "DSSP"]}}


def test_form_to_json_multiselect_drops_empty_placeholder():
    data = ImmutableMultiDict(
        [
            ("analysis[method][]", ""),
            ("analysis[method][]", "RMSD"),
            ("analysis[method][]", "DSSP"),
        ]
    )
    result = form_to_json(data)
    assert result == {"analysis": {"method": ["RMSD", "DSSP"]}}


def test_form_to_json_plain_dict_list_value_preserved():
    data = {"analysis[method][]": ["RMSD", "DSSP"]}
    result = form_to_json(data)
    assert result == {"analysis": {"method": ["RMSD", "DSSP"]}}


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

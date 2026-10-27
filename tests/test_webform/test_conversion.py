import pytest
from werkzeug.datastructures import ImmutableMultiDict

from biosimdb_interface.core.errors import FormConversionError
from biosimdb_interface.webform import conversion


@pytest.fixture
def typed_schema(monkeypatch):
    """Provide fields covering scalar and repeatable type hints."""
    monkeypatch.setattr(
        conversion,
        "get_simulation_metadata",
        lambda: {
            "simulation": {
                "fields": {
                    "count": {"typehint": "integer"},
                    "temperature": {"typehint": "float"},
                    "enabled": {"typehint": "boolean"},
                    "replicas": {
                        "multiple": True,
                        "fields": {"steps": {"typehint": "integer"}},
                    },
                }
            }
        },
    )


def test_typehint_map_includes_nested_repeatable_fields(typed_schema):
    """Maps type hints inside nested and repeatable schema fields."""
    result = conversion._get_typehint_map()

    assert result[("simulation", "count")] == "integer"
    assert result[("simulation", "replicas", "*", "steps")] == "integer"


def test_form_to_json_converts_typed_values(typed_schema):
    """Converts integer, float, boolean, and repeatable values."""
    result = conversion.form_to_json(
        {
            "simulation[count]": "12",
            "simulation[temperature]": "310.5",
            "simulation[enabled]": "yes",
            "simulation[replicas][1][steps]": "500",
        }
    )

    assert result == {
        "simulation": {
            "count": 12,
            "temperature": 310.5,
            "enabled": True,
            "replicas": [{"steps": 500}],
        }
    }


def test_parse_vector_rejects_non_numeric_row():
    """Reports which vector row contains a nonnumeric value."""
    with pytest.raises(ValueError, match="row 2"):
        conversion._parse_vector("1, 2; 3, nope", "simulation.vector_value")


def test_parse_vector_rejects_rows_with_different_lengths():
    """Requires each row in a matrix vector to have the same number of values."""
    with pytest.raises(ValueError, match="rows have different lengths"):
        conversion._parse_vector("1, 2; 3", "simulation.vector_value")


def test_form_to_json_collects_invalid_vector_error():
    """Raises a form conversion error when a vector value is malformed."""
    with pytest.raises(FormConversionError, match="not a comma-separated list"):
        conversion.form_to_json({"simulation[vector_value]": "1, invalid"})


def test_form_to_json_preserves_empty_vector_value():
    """Keeps an empty vector field as an empty string."""
    assert conversion.form_to_json({"simulation[vector_value]": ""}) == {
        "simulation": {"vector_value": ""}
    }


def test_form_to_json_collects_scalar_type_errors(typed_schema):
    """Reports invalid integer and float values together."""
    with pytest.raises(FormConversionError) as exc_info:
        conversion.form_to_json(
            {
                "simulation[count]": "many",
                "simulation[temperature]": "warm",
            }
        )

    assert len(exc_info.value.errors) == 2
    assert "simulation.count" in exc_info.value.errors[0]
    assert "simulation.temperature" in exc_info.value.errors[1]


def test_form_to_json_nested():
    data = {"simulation[1][name]": "test", "save": "1"}
    result = conversion.form_to_json(data)
    assert result == {"simulation": [{"name": "test"}]}


def test_form_to_json_skips_template():
    data = {"simulation[TEMPLATE][name]": "skip", "simulation[1][name]": "keep"}
    result = conversion.form_to_json(data)
    assert "TEMPLATE" not in str(result)


def test_form_to_json_vector_value():
    data = {"sim[1][vector_value]": "1.0, 2.0, 3.0"}
    result = conversion.form_to_json(data)
    assert result["sim"][0]["vector_value"] == [1.0, 2.0, 3.0]


def test_form_to_json_multiselect_repeated_keys():
    data = ImmutableMultiDict(
        [
            ("analysis[method][]", "RMSD"),
            ("analysis[method][]", "DSSP"),
        ]
    )
    result = conversion.form_to_json(data)
    assert result == {"analysis": {"method": ["RMSD", "DSSP"]}}


def test_form_to_json_multiselect_drops_empty_placeholder():
    data = ImmutableMultiDict(
        [
            ("analysis[method][]", ""),
            ("analysis[method][]", "RMSD"),
            ("analysis[method][]", "DSSP"),
        ]
    )
    result = conversion.form_to_json(data)
    assert result == {"analysis": {"method": ["RMSD", "DSSP"]}}


def test_form_to_json_plain_dict_list_value_preserved():
    data = {"analysis[method][]": ["RMSD", "DSSP"]}
    result = conversion.form_to_json(data)
    assert result == {"analysis": {"method": ["RMSD", "DSSP"]}}


def test_form_to_json_direct_list_assignment():
    """Numeric index as final path part sets list item directly."""
    from biosimdb_interface.webform.conversion import _set_nested

    d = {}
    _set_nested(d, ["items", "1"], "val")
    assert d == {"items": ["val"]}


def test_form_to_json_multiselect_single_value_stays_list():
    """A single selection from a multivalued HTML field remains a list."""
    result = conversion.form_to_json(
        {"stages[minimisation][1][minimisation_algorithm][]": "Steepest Descent"}
    )

    assert result == {
        "stages": {"minimisation": [{"minimisation_algorithm": ["Steepest Descent"]}]}
    }

#!/usr/bin/env python

import copy
import re

from biosimdb_interface.schema.invenio import INVENIO_DSMD_TEMPLATE, INVENIO_FORM_EMPTY
from biosimdb_interface.schema.webform import get_simulation_metadata


def fill_invenio_metadata(form_data):
    """Populate a blank Invenio record with form data.

    Args:
        form_data: Dictionary of parsed form values from form_to_json().

    Returns:
        dict: Invenio-compatible record dictionary with custom_fields populated.
    """
    invenio_data = copy.deepcopy(INVENIO_FORM_EMPTY)
    # invenio_data["custom_fields"]["dsmd"] = [form_data]
    # temporarily use dsmd template for testing
    invenio_data["custom_fields"]["dsmd"] = [INVENIO_DSMD_TEMPLATE]
    # add generated keywords
    # add generated subjects

    return invenio_data


def _set_nested(d, parts, value):
    """Recursively set a value in a nested dictionary using a list of key parts.

    Numeric parts are treated as 1-based list indices. Non-numeric parts
    are treated as dictionary keys.

    Args:
        d: Dictionary to set the value in (modified in place).
        parts: List of string key parts representing the path to the value.
        value: Value to set at the specified path.
    """
    key = parts[0]
    if len(parts) == 1:
        d[key] = value
        return
    next_part = parts[1]
    if next_part.isdigit():
        idx = int(next_part) - 1
        d.setdefault(key, [])
        while len(d[key]) <= idx:
            d[key].append({})
        _set_nested(d[key][idx], parts[2:], value) if len(parts) > 2 else d[
            key
        ].__setitem__(idx, value)
    else:
        d.setdefault(key, {})
        _set_nested(d[key], parts[1:], value)


def _build_typehint_map(fields, path_parts, result):
    """Recursively build a map of field path tuples to their typehint.

    Args:
        fields (dict): Dictionary of field definitions from the webform schema.
        path_parts (list[str]): Accumulated path segments leading to the current fields.
        result (dict): Dictionary modified in place mapping path tuples to typehint strings.
    """
    for field_name, field in fields.items():
        current = path_parts + [field_name]
        if field.get("typehint"):
            result[tuple(current)] = field["typehint"]
        if field.get("fields"):
            _build_typehint_map(field["fields"], current, result)
        if field.get("multiple"):
            _build_typehint_map(field.get("fields", {}), current + ["*"], result)


def _get_typehint_map():
    """Build a complete typehint map from the webform schema.

    Iterates over all sections and fields in ``simulation_metadata`` and
    delegates to :func:`_build_typehint_map` to populate the result.

    Returns:
        dict: Mapping of field path tuples (e.g. ``('composition', 'molecule_ID', '*', 'atom_count')``)
        to typehint strings (``'integer'``, ``'float'``, or ``'boolean'``).
        Numeric list indices are represented as ``'*'`` wildcards.
    """
    result = {}
    simulation_metadata = get_simulation_metadata()
    for section_key, section in simulation_metadata.items():
        fields = section.get("fields", {})
        _build_typehint_map(fields, [section_key], result)
    return result


def form_to_json(form):
    """Convert flat HTML form data into a nested dictionary.

    Parses bracket-notation field names (e.g. section[field][1][subfield])
    into nested dicts and lists. Skips submit/save keys and TEMPLATE entries.
    Splits vector_value fields from comma-separated strings into float lists.

    Args:
        form: Flat form data (ImmutableMultiDict or dict) from a POST request.

    Returns:
        dict: Nested dictionary of form values.
    """
    typehint_map = _get_typehint_map()
    data = {}
    for key, value in form.items():
        if key in ("save", "submit"):
            continue
        parts = re.findall(r"\w+", key)
        if not parts or "TEMPLATE" in parts:
            continue
        if parts[-1] == "vector_value" and isinstance(value, str) and value:
            value = [float(x.strip()) for x in value.split(",") if x.strip()]
        else:
            # build a schema-lookup key replacing numeric indices with '*'
            lookup = tuple(p if not p.isdigit() else "*" for p in parts)
            typehint = typehint_map.get(lookup) or typehint_map.get(tuple(parts))
            if value != "" and typehint:
                if typehint == "integer":
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        pass
                elif typehint == "float":
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        pass
                elif typehint == "boolean":
                    value = bool(value)
        _set_nested(data, parts, value)
    return data


def remove_empty_fields(d):
    """Recursively remove empty strings, None, empty dicts, and empty lists from a nested dict.

    Args:
        d: Nested dictionary to clean.

    Returns:
        dict: Cleaned dictionary with empty values removed.
    """
    if not isinstance(d, dict):
        return d
    cleaned = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = remove_empty_fields(v)
            if v:
                cleaned[k] = v
        elif isinstance(v, list):
            v = [remove_empty_fields(i) for i in v]
            v = [i for i in v if i not in (None, "", {}, [])]
            if v:
                cleaned[k] = v
        elif v not in (None, ""):
            cleaned[k] = v
    return cleaned

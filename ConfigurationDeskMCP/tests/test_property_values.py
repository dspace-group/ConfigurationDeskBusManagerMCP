from __future__ import annotations

from pydantic import TypeAdapter

from sources.models.property_values import StrictPropertyValue


def test_strict_property_value_preserves_numeric_and_bool_types():
    adapter = TypeAdapter(StrictPropertyValue)

    int_value = adapter.validate_python(1)
    float_value = adapter.validate_python(1.0)
    bool_value = adapter.validate_python(True)
    str_value = adapter.validate_python("1")

    assert int_value == 1
    assert isinstance(int_value, int)
    assert not isinstance(int_value, bool)
    assert float_value == 1.0
    assert isinstance(float_value, float)
    assert bool_value is True
    assert isinstance(bool_value, bool)
    assert str_value == "1"
    assert isinstance(str_value, str)


def test_strict_property_value_schema_publishes_numeric_before_boolean_types():
    adapter = TypeAdapter(StrictPropertyValue)

    schema = adapter.json_schema()

    assert schema["anyOf"] == [
        {"type": "integer"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "string"},
    ]

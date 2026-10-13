"""A deliberately small JSON Schema (draft 2020-12) validator: only the keywords manifest.schema.json uses.

Unknown keywords in the schema raise an error instead of being ignored, so the schema can never silently
claim a constraint this validator does not enforce.
"""

import re
from typing import Any, Dict, List

SUPPORTED_KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description",
    "type", "const", "enum", "required", "properties", "additionalProperties",
    "items", "minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum", "maximum",
}

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


class SchemaError(Exception):
    """The schema itself uses something this validator does not support."""


def validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable errors; empty means valid."""
    errors: List[str] = []
    _check(instance, schema, schema, "$", errors)
    return errors


def _resolve(ref: str, root: Dict[str, Any]) -> Dict[str, Any]:
    if not ref.startswith("#/$defs/"):
        raise SchemaError(f"only local $defs references are supported: {ref}")
    name = ref[len("#/$defs/"):]
    try:
        return root["$defs"][name]
    except KeyError:
        raise SchemaError(f"unresolved $ref {ref}") from None


def _check(value: Any, schema: Dict[str, Any], root: Dict[str, Any], path: str, errors: List[str]) -> None:
    unknown = set(schema) - SUPPORTED_KEYWORDS
    if unknown:
        raise SchemaError(f"unsupported schema keywords at {path}: {sorted(unknown)}")

    if "$ref" in schema:
        _check(value, _resolve(schema["$ref"], root), root, path, errors)

    expected = schema.get("type")
    if expected is not None and not _TYPES[expected](value):
        errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
        return

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match pattern {schema['pattern']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: allows at most {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(value):
                _check(item, schema["items"], root, f"{path}[{index}]", errors)

    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required property '{name}'")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in properties:
                _check(item, properties[name], root, f"{path}.{name}", errors)
            elif additional is False:
                errors.append(f"{path}: unexpected property '{name}'")
            elif isinstance(additional, dict):
                _check(item, additional, root, f"{path}.{name}", errors)

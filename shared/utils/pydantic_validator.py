from pydantic import BaseModel, ValidationError, TypeAdapter
from typing import Any, Dict, TypedDict


class ValidationResult:
    errors: list[Dict]
    valid_data: Dict[str, Any]

    def __init__(self, errors, valid_data):
        self.errors = errors
        self.valid_data = valid_data

class PartialValidationMixin:

    @classmethod
    def partial_validate(cls, data: Dict[str, Any]) -> ValidationResult:
        valid = {}
        errors = []

        # Validate each field independently using TypeAdapter
        for field_name, field in cls.model_fields.items():
            if field_name not in data:
                continue  # ignore missing fields

            adapter = TypeAdapter(field.annotation)

            try:
                value = adapter.validate_python(data[field_name])
                valid[field_name] = value
            except ValidationError as e:
                # Re-map errors to include field name
                for err in e.errors():
                    err["loc"] = (field_name,) + tuple(err.get("loc", ()))
                    errors.append(err)

        # Now run cross-field validators (model_validator)
        try:
            # Build the model without validation for other fields
            temp_model = cls.model_construct(**valid)
            full_model = cls.model_validate(temp_model)  # triggers model-level validators
            valid = full_model.model_dump()
        except ValidationError as e:
            errors.extend(e.errors())

        return ValidationResult(errors=errors, valid_data=valid)

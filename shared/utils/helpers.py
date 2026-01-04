import asyncio
from pydantic import BaseModel
from functools import wraps
from typing import get_origin, get_args, Union


def retry(max_retries=3, delay=1, on_failure=None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_retries:
                        if on_failure:
                            return await on_failure(*args, error=e, *kwargs)
                        raise e
                    await asyncio.sleep(delay)
        return wrapper
    return decorator



def get_base_type(annotation):
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[T] or T | None
    if origin is Union and len(args) == 2 and type(None) in args:
        return next(arg.__name__ for arg in args if arg is not type(None))

     # Builtins & classes
    if isinstance(annotation, type):
        return annotation.__name__

    # Fallback (typing objects)
    return str(annotation)

def is_field_optional(annotation) -> bool:
    origin = get_origin(annotation)
    args = get_args(annotation)

    return (
        origin is Union
        and type(None) in args
    )

def generate_field_description(model: BaseModel):
    required_fields = []
    optional_fields = []
    
    for field_name, field in model.model_fields.items():
        field_type = get_base_type(field.annotation)
        field_description = field.description
        is_optional = not field.is_required() # is_required() doesnt work if field is doesnt contain any default values
        is_optional = is_field_optional(field.annotation)
        if is_optional:
            optional_fields.append(f"- {field_name}: {field_type}, Description: {field_description}")
        else:
            required_fields.append(f"- {field_name}: {field_type}, Description: {field_description}")
    
    required_info = "\n".join(required_fields)
    optional_info = "\n".join(optional_fields)
    
    return f"## Required Information \n{required_info}\n\n## Optional Information - DONT Ask again if not provided with mandatory information. Assert safe default values for them\n{optional_info}"
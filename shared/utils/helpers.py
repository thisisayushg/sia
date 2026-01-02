import asyncio
from pydantic import BaseModel
from functools import wraps


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

def generate_field_description(model: BaseModel):
    required_fields = []
    optional_fields = []
    
    for field_name, field in model.model_fields.items():
        field_type = field.annotation
        field_description = field.description
        is_optional = field.is_required()
        
        if is_optional:
            optional_fields.append(f"- {field_name}: {field_type}, Description: {field_description}")
        else:
            required_fields.append(f"- {field_name}: {field_type}, Description: {field_description}")
    
    required_info = "\n".join(required_fields)
    optional_info = "\n".join(optional_fields)
    
    return f"## Required Information \n{required_info}\n\n## Optional Information - DONT Ask again if not provided with mandatory information. Assert safe default values for them\n{optional_info}"
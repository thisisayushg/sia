import asyncio
from pydantic import BaseModel
from functools import wraps
from typing import get_origin, get_args, Union
from langchain_core.messages import AIMessage, HumanMessage
from rapidfuzz import fuzz

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
            optional_fields.append(f"- {field_name}[{field_type}]: {field_description}. Consider {field.default} if not provided")
        else:
            required_fields.append(f"- {field_name}[{field_type}]: {field_description}. Consider {field.default} if not provided")
    
    required_info = "\n".join(required_fields)
    optional_info = "\n".join(optional_fields)
    
    return f"## Required Information \n{required_info}\n\n## Optional Information - DONT Ask again if not provided with mandatory information. Assert safe default values for them\n{optional_info}"


def describe_model(model: type[BaseModel], indent: int = 0) -> str:
    space = " " * indent
    result = "{\n"

    for field_name, field_info in model.model_fields.items():
        annotation = field_info.annotation
        description = field_info.description or ""

        # Handle list fields (like list[ScrapingResult])
        if get_origin(annotation) is list:
            inner_model = get_args(annotation)[0]
            result += f"{space}  '{field_name}': [\n"
            result += describe_model(inner_model, indent + 4)
            result += f"{space}  ]\n"
        else:
            result += f"{space}  '{field_name}': '{description}',\n"

    result += f"{space}}}\n"
    return result


def messages_to_dicts(messages):
    return [
        {
            "role": (
                "human" if isinstance(m, HumanMessage)
                else "ai" if isinstance(m, AIMessage)
                else "system"
            ),
            "content": m.content,
        }
        for m in messages
    ]

def merge_ner_locations(ner_results):
    merged_entities = []
    current_entity = None

    for token in ner_results:
        label = token["entity"]

        # Check if token is B-LOC
        if label == "B-LOC":
            # Save previous entity if exists
            if current_entity:
                merged_entities.append(current_entity)

            # Start new entity
            current_entity = {
                "entity": "LOC",
                "word": token["word"],
                "start": token["start"],
                "end": token["end"],
                "score": token["score"]
            }

        # Check if token is I-LOC and we already started a LOC
        elif label == "I-LOC" and current_entity:
            if not token['word'].startswith("##"):
                current_entity['word'] +=' '
            current_entity["word"] += token["word"].replace("##", "")
            current_entity["end"] = token["end"]
            current_entity["score"] = max(current_entity["score"], token["score"])

        else:
            # If different label, close current LOC
            if current_entity:
                merged_entities.append(current_entity)
                current_entity = None

    # Append last entity if exists
    if current_entity:
        merged_entities.append(current_entity)

    return merged_entities

def filter_similar_phrases(items, similarity_threshold=85):
    # Remove obvious noise like single-word "The"
    from nltk.corpus import stopwords

    items =  [i for i in items if i.lower() not in set(stopwords.words('english'))]

    unique = []

    for item in items:
        is_duplicate = False
        for existing in unique:
            similarity = fuzz.token_sort_ratio(item.lower(), existing.lower())
            if similarity >= similarity_threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(item)

    return unique
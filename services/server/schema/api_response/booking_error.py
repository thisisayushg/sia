from pydantic import BaseModel
from typing import Any

class ErrorObjects(BaseModel):
    loc: list[str]
    msg: str
    type: str

class BookingError(BaseModel):
    detail: list[ErrorObjects] | Any

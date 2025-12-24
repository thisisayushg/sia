from datetime import date
from pydantic import BaseModel, Field
from shared.utils.pydantic_validator import PartialValidationMixin
from typing import Annotated

class TravelBooking(PartialValidationMixin, BaseModel):
    number_of_adults: Annotated[int, Field(..., gt=0, description="Number of adult travelers")]
    check_in_date: Annotated[date, Field(..., description="Check-in date")]
    check_out_date: Annotated[date, Field(..., description="Check-out date")]
    budget_per_night: Annotated[float, Field(..., gt=0, description="Budget per night in INR")]
    location: Annotated[str, Field(..., description="Place or city or locality name for stay", min_length=1)]
    number_of_children: Annotated[int, Field(..., ge=1, description="Number of children")]
    reasoning: Annotated[str, Field(..., description="All the reasoning behind each of the extracted value. Also include current date in words in this reasoning")]

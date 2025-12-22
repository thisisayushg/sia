from datetime import date
from pydantic import BaseModel, Field
from shared.utils.pydantic_validator import PartialValidationMixin


class TravelBooking(PartialValidationMixin, BaseModel):
    number_of_adults: int = Field(..., gt=0, description="Number of adult travelers")
    check_in_date: date = Field(..., description="Check-in date")
    check_out_date: date = Field(..., description="Check-out date")
    budget_per_night: float = Field(..., gt=0, description="Budget per night in INR")
    location: str = Field(..., description="Place or city or locality name for stay", min_length=1)
    number_of_children: int = Field(..., ge=1, description="Number of children")
    reasoning: str = Field(..., description="All the reasoning behind each of the extracted value")

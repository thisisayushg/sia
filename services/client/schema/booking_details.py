from datetime import date
from pydantic import BaseModel, Field
from shared.utils.pydantic_validator import PartialValidationMixin
from typing import Annotated, Optional

class TravelBooking(PartialValidationMixin, BaseModel):
    number_of_adults: Annotated[int, Field(..., gt=0, description="Number of adult travelers")]
    check_in_date: Annotated[date, Field(..., description="Check-in date")]
    check_out_date: Annotated[date, Field(..., description="Check-out date")]
    budget_per_night: Annotated[float, Field(..., gt=0, description="Budget per night in INR")]
    location: Annotated[str, Field(..., description="Place or city or locality name for stay", min_length=1)]
    number_of_children: Annotated[int, Field(..., ge=1, description="Number of children")]
    reasoning: Annotated[str, Field(..., description="All the reasoning behind each of the extracted value. Also include current date in words in this reasoning")]

class DestinationRecommendation(PartialValidationMixin, BaseModel):
    budget_per_night: Annotated[float, Field(..., gt=0, description="Budget per night in INR")]
    purpose: Annotated[Optional[str], Field(None, description="Purpose of travel such as relaxation, adventure, culture, family time,")]
    duration: Annotated[Optional[int], Field(1, description="Duration of the travel including the transportation and stay (in number of days)")]
    trip_start: Annotated[date, Field(..., description="Expected start date of the trip")]
    trip_end: Annotated[date, Field(..., description="Expected end date of the trip")]
    start_location: Annotated[str, Field(..., description="Start location of the trip. Could be current location of the user as well.")]

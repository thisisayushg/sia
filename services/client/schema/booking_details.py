from datetime import date
from pydantic import BaseModel, Field
from shared.utils.pydantic_validator import PartialValidationMixin
from typing import Annotated, Optional, List
from .web_result import WebSearchResultCollection, WebSearchResult

class TravelBooking(PartialValidationMixin, BaseModel):
    number_of_adults: Annotated[int, Field(..., gt=0, description="Number of adult travelers")]
    check_in_date: Annotated[date, Field(..., description="Check-in date")]
    check_out_date: Annotated[date, Field(..., description="Check-out date")]
    budget_per_night: Annotated[float, Field(..., gt=0, description="Budget per night in INR")]
    location: Annotated[str, Field(..., description="Place or city or locality name for stay", min_length=1)]
    number_of_children: Annotated[int, Field(..., ge=1, description="Number of children")]
    season: Annotated[Optional[str], Field('', description="Season if specified by the user")]
    reasoning: Annotated[str, Field(..., description="All the reasoning behind each of the extracted value. Also include current date in words in this reasoning. This is to be populated by you and not user")]

class DestinationRecommendation(PartialValidationMixin, BaseModel):
    budget_per_night: Annotated[Optional[float], Field(None, gt=0, description="Budget per night in INR")]
    total_budget: Annotated[Optional[int], Field(None, gt=0, description="Total budget for the trip in INR")]
    purpose: Annotated[Optional[str], Field(None, description="Purpose of travel such as relaxation, adventure, culture, family time,")]
    duration: Annotated[Optional[int], Field(1, description="Duration of the travel including the transportation and stay (in number of days)")]
    season: Annotated[Optional[str], Field('', description="Season if specified by the user")]
    trip_start: Annotated[date, Field(..., description="Expected start date of the trip")]
    trip_end: Annotated[date, Field(..., description="Expected end date of the trip")]
    start_location: Annotated[Optional[str], Field('', description="Start location of the trip. Could be current location of the user as well.")]
    reasoning: Annotated[str, Field('', description="All the reasoning behind each of the extracted value. Also include current date in words in this reasoning.  This is to be populated by you and not user")]

    # @model_validator(mode="after")
    # def _validate_budget_info(self):
    #     if not hasattr(self, 'budget_per_night') and not hasattr(self, 'total_budget'):
    #         raise ValueError("Either total or budget per night is required")

class ExpenseBreakdown(BaseModel):
    travel_expense: str = Field('', description="Estimated cost for travel (e.g., flights, trains). Example: 'Approx. $600 (flight from New York)'")
    food_expense: str = Field('', description="Daily food expense range. Example: '$60-$90 per day'")
    activities_expense: str = Field('', description="Cost range for activities (e.g., tours, lessons). Example: '$80-$150 (surfing lessons, tours)'")
    stay: Optional[str] = Field(None, description="Nightly accommodation cost range. Example: '$180-$350 per night'")

class TravelMode(BaseModel):
    mode: str = Field('', description="Mode of travel (e.g., flight, train, bus). Example: 'Direct flight'")
    details: Optional[str] = Field(None, description="Additional details about the travel mode. Example: 'from New York (may have limited options)'")

class TravelDestination(BaseModel):
    name: str = Field(..., description="Name of the travel destination. Example: 'Sedona, Arizona'")
    expense_breakdown: ExpenseBreakdown = Field(..., description="Breakdown of expected expenses for the destination.")
    expected_weather: str = Field(..., description="Expected weather conditions during the visit.")
    travel_modes: List[TravelMode] = Field(..., description="List of available travel modes to reach the destination.")

class TravelDestinationRecommendations(BaseModel):
    destinations: List[TravelDestination]

from enum import Enum

class TravelPurpose(Enum):
    RELAXATION = 1
    FAMILY_TIME = 2
    ADVENTURE = 3

class TravelSearchResult(WebSearchResult):
    purpose: TravelPurpose = Field(description="The purpose of travel as given by the user")

class TravelSearchResultCollection(WebSearchResultCollection[TravelSearchResult]):
    pass
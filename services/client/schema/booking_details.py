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

from enum import StrEnum

class TravelPurpose(StrEnum):
    RELAXATION = 'RELAXATION'
    FAMILY_TIME = 'FAMILY_TIME'
    ADVENTURE = 'ADVENTURE'

class TravelSearchResult(WebSearchResult):
    purpose: Optional[TravelPurpose] = Field('', description="The purpose of travel as given by the user")

class TravelSearchResultCollection(WebSearchResultCollection):
    pass
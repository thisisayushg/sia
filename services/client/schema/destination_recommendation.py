from datetime import date, datetime, timedelta
from pydantic import BaseModel, Field
from shared.utils.pydantic_validator import PartialValidationMixin
from typing import Annotated, Optional, List


class DestinationRecommendation(PartialValidationMixin, BaseModel):
    budget_per_night: Annotated[Optional[float], Field(None, gt=0, description="Budget per night in INR")]
    total_budget: Annotated[Optional[int], Field(None, gt=0, description="Total budget for the trip in INR")]
    purpose: Annotated[Optional[str], Field(None, description="Purpose of travel such as relaxation, adventure, culture, family time,")]
    duration: Annotated[Optional[int], Field(1, description="Duration of the travel including the transportation and stay (in number of days)")]
    season: Annotated[Optional[str], Field('', description="Season if specified by the user")]
    trip_start: Annotated[date, Field(datetime.now().date(), description="Expected start date of the trip. Infer using date interpretation rules, if not provided")]
    trip_end: Annotated[date, Field((datetime.now() + timedelta(days=1)).date(), description="Expected end date of the trip. Infer using date interpretation rules, if not provided")]
    start_location: Annotated[Optional[str], Field('', description="Start location of the trip. Could be current location of the user as well.")]
    region: Annotated[Optional[str], Field('', description="A region like country, a continent, or a sub-region like North-East India specified by the user to recommend destinations within.")]
    reasoning: Annotated[str, Field('', description="All the reasoning behind each of the extracted value. Also include current date in words in this reasoning.  This is to be populated by you and not user")]

    # @model_validator(mode="after")
    # def _validate_budget_info(self):
    #     if not hasattr(self, 'budget_per_night') and not hasattr(self, 'total_budget'):
    #         raise ValueError("Either total or budget per night is required")

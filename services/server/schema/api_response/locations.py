from pydantic import BaseModel, Field, field_validator
from typing import Optional
from zoneinfo import available_timezones

class Location(BaseModel):
    city_ufi: Optional[int] = Field(None, description="Unique identifier for the city")
    label: str = Field(..., description="Full name of the city or landmark including the region, state and country")
    hotels: int = Field(..., description="Number of hotels available")
    nr_hotels: int = Field(..., description="Number of hotels available")
    latitude: float = Field(..., description="Latitude of the location")
    rtl: int = Field(..., description="RTL flag")
    longitude: float = Field(..., description="Longitude of the location")
    loc_type: Optional[str] = Field(None, alias="type",  description="Type of location")
    city_name: str = Field(..., description="Name of the city")
    dest_type: str = Field(..., description="Type of destination")
    timezone: Optional[str] = Field(None, description="Timezone of the location")
    dest_id: str = Field(..., description="Unique identifier for the destination")
    region: str = Field(..., description="Region of the location")
    name: str = Field(..., description="Name of the city or landmark")
    lc: str = Field(..., description="Language code")
    landmark_type: Optional[int] = Field(None,  description="Type of landmark")
    country: str = Field(..., description="Fully qualified name of the country of the location")


    @field_validator('timezone')
    def validate_timezone(cls, value):
        if value not in available_timezones():
            raise ValueError(f"Invalid timezone provided. Expected one of {available_timezones()}, found {value}")
        return value
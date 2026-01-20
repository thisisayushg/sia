from pydantic import BaseModel, Field
from typing import List, Dict

class ToolClassification(BaseModel):
    web_tools: List[str] = Field(default_factory=list, description="""
List containing name of the tools which could be useful for online/web activities and research. This includes tools like
web search tools, web crawling and scraping tools, etc.
        """)
    weather_tools: List[str] = Field(default_factory=list, description="""
List containing  Name of the Tools which can help assimilate weather related information like air quality, minimum and maximum temperatures,
weather forecast, wind speeds, precipitation, and historical weather data.
        """)
    map_tools: List[str] = Field(default_factory=list, description="""
List containing name of the tools which can help in mapping activities. The activities include, but are not limited to, 
finding distance between places, geocoding and reverse-geocoding, routing between cities/markers,
geographical area details like amenities, nearby amenities and public infrastructure details.                         
        """)
    
    hotel_stays_tools: List[str] = Field(default_factory=list, description="""
List containing Name of the Tools which can search properties available for guest stays, find details about specific hotels or homestays like AirBnbs.
Also, these tools can help in researching about hotels for guest reviews based on guest experiences.
        """)
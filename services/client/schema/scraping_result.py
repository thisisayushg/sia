from pydantic import BaseModel, Field
from typing import Generic, TypeVar

T = TypeVar("T")

class ScrapingResult(BaseModel):
    url: str = Field(description="URL/Link to the website")
    domain: str = Field(description="Domain of the website")
    title: str = Field(description="Title/Heading of the page")
    search_term: str = Field(description="Search term/ text which was searched on the web")
    content: str = Field(description="Content found after scraping the webpage. Include full content of extraction")

class ScrapingResultCollection(BaseModel):
    scraping_results: list[ScrapingResult] = Field("A collection of scraping result of each url")

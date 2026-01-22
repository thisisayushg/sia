from pydantic import BaseModel, Field
from typing import Generic, TypeVar

T = TypeVar("T")

class WebSearchResult(BaseModel):
    url: str = Field(description="URL/Link to the website")
    domain: str = Field(description="Domain of the website")
    title: str = Field(description="Title/Heading of the page")
    search_term: str = Field(description="Search term/ text which was searched on the web")

class WebSearchResultCollection(BaseModel, Generic[T]):
    search_results: list[T] = Field(description="A Collection of all web search results")
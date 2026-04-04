from pydantic import BaseModel, Field
from typing import Optional

class WebSearchResult(BaseModel):
    url: str = Field(description="URL/Link to the website")
    domain: Optional[str] = Field(description="Domain of the website")
    title: str = Field(description="Title/Heading of the page")
    search_term: Optional[str] = Field(description="Search term/ text which was searched on the web")

class WebSearchResultCollection(BaseModel):
    search_results: list[WebSearchResult] = Field(description="A Collection of all web search results")
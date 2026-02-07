from pydantic import BaseModel, Field


class NameExtractionResult(BaseModel):
    name: str =  Field('', description="Name of the place. Excluding names of regions with large geographical areas like a country, or a state. Exclude the names of hotels.")
    reasoning: str = Field('', description="Reason for choosing this name for extraction")

class NameExtractionResultCollection(BaseModel):
    extracted_names: list[NameExtractionResult] = Field(..., default_factory=list, description="List of extracted names from the webpage")

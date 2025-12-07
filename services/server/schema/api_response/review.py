from pydantic import BaseModel, Field
from typing import Optional, List


class StayedRoomInfo(BaseModel):
    room_id: int = Field(..., description="The unique identifier for the room")
    room_name: str = Field(..., description="The name of the room")
    checkin: str = Field(..., description="The check-in date of the stay in ISO format")
    num_nights: int = Field(..., description="The number of nights stayed")
    checkout: str = Field(..., description="The check-out date of the stay in ISO format")

class HotelReview(BaseModel):
    hotel_name: str = Field(..., description="The name of the hotelier", alias="hotelier_name")
    hotel_id: int = Field(..., description="The unique identifier for the hotel")
    is_incentivised: int = Field(..., description="Indicates if the hotel is incentivized")
    pros_translated: str = Field(..., description="Pros translated in the specified language")
    title_translated: str = Field(..., description="Title translated in the specified language")
    reviewer_photos: List[str] = Field(..., description="List of URLs to the reviewer's photos")
    pros: Optional[str] = Field(None, description="Pros of the stay")
    title: str = Field(..., description="Title of the review")
    is_moderated: int = Field(..., description="Indicates if the review is moderated")
    travel_purpose: str = Field(..., description="Purpose of the travel")
    countrycode: str = Field(..., description="Country code of the reviewer")
    tags: List[str] = Field(..., description="List of tags associated with the review")
    languagecode: str = Field(..., description="Language code of the review")
    stayed_room_info: StayedRoomInfo = Field(..., description="Information about the room stayed")
    anonymous: str = Field(..., description="Indicates if the reviewer is anonymous")
    hotelier_response_date: Optional[int] = Field(None, description="Timestamp of the hotelier's response")
    cons_translated: str = Field(..., description="Cons translated in the specified language")
    helpful_vote_count: int = Field(..., description="Number of helpful votes for the review")
    date: str = Field(..., description="Date and time when the review was submitted in ISO format")
    hotelier_response: str = Field(..., description="Response from the hotelier")
    user_new_badges: List[str] = Field(..., description="List of new badges received by the user")
    review_hash: str = Field(..., description="Hash of the review for uniqueness")
    average_score: float = Field(..., description="Average score of the review")
    review_id: int = Field(..., description="Unique identifier for the review")
    cons: Optional[str] = Field(None, description="Cons of the stay as a string")
    reviewng: int = Field(..., description="Indicates if the review is in the process of being reviewed")
    is_trivial: int = Field(..., description="Indicates if the review is considered trivial")


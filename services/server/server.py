import sys
import os

from typing import Set

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Or add current directory
sys.path.append(os.path.dirname(__file__))

from datetime import datetime
from shared.schema.sorting_methods import SortingMethods
from fastmcp import FastMCP
import subprocess
import requests
from datetime import date
from services.server.schema.api_response import BookingError, HotelReview, Hotel, DestinationType, Location
from typing import Annotated, Optional
from pydantic import Field, BaseModel, field_validator, model_validator
from jsonschema import validate
import os

base_url = "https://booking-com.p.rapidapi.com/v1"
headers = {
    "x-rapidapi-key": os.getenv("RAPID_BOOKING_API_KEY"),
    "x-rapidapi-host": "booking-com.p.rapidapi.com",
}
mcp = FastMCP("MyServer")


# @mcp.tool
def run_command_advanced(command, shell=False):
    """
    Execute a terminal command with more control.

    Args:
        command: String (if shell=True) or list of command and arguments
        shell: Whether to use shell execution

    Returns:
        dict with stdout, stderr, and return_code
    """
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=shell,
        )

        stdout, stderr = process.communicate(timeout=30)

        return {
            "stdout": stdout,
            "stderr": stderr,
            "return_code": process.returncode,
            "success": process.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        process.kill()
        return {
            "stdout": "",
            "stderr": "Command timed out and was killed",
            "return_code": -1,
            "success": False,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "return_code": -1, "success": False}


@mcp.tool
def _fetch_locations(place: str) -> list[Location]:
    """Fetch locations which have similar names to the given place name.
    This is a useful tool to get destination id along with other information
    about the locations with similar names.

    Args:
        place (str): The name of the place to search for locations.

    Returns:
        dict: JSON response containing the locations.
    """

    url = f"{base_url}/hotels/locations"

    querystring = {"name": place, "locale": "en-gb"}

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    result = []
    for item in response.json():
        item.pop("type")
        item.pop("b_max_los_data", "")
        item.pop("image_url", "")
        item.pop("roundtrip", "")
        item.pop("timezone", "")
        item.pop("cc1", "")
        result.append(Location(**item))
    return result


class SearchArgs(BaseModel):
    checkin_date: str = Field(
        ..., description="Check-out date for the stay in YYYY-MM-DD format"
    )
    checkout_date: str = Field(
        ..., description="Check-in date for the stay in YYYY-MM-DD format"
    )
    destination_id: Optional[str] = (
        Field(..., description="Internal ID of destination/place/location"),
    )
    num_children: int = Field(1, ge=1, description="Number of child occupants")
    num_rooms: int = Field(1, ge=1, description="Number of rooms preferred in total")
    num_adults: int = Field(1, description="Number of adult occupants")
    max_results: int = Field(
        5, description="The maximum number of stays to find in one go"
    )
    # order_by:    #     SortingMethods,
    #     Field(
    #         SortingMethods.POPULARITY, description="Order the results by one of the sorting methods"
    #     ),
    # ],
    dest_type: DestinationType = Field(
        DestinationType.CITY, description="Type of destination"
    )

    @field_validator("checkin_date", "checkout_date", mode="after")
    def validate_checkin_checkout(cls, value):
        _ = datetime.strptime(value, "%Y-%m-%d").date()
        if _ and _ < date.today():
            raise ValueError("Check-In and/or Check-Out date has already passed")
        return value

    # @field_validator('checkin_date', 'checkout_date', mode='before')
    # def convert_checkin_checkout(cls, value):
    #     value = datetime.strptime(value, "%Y-%m-%d").date()
    #     return value

    def model_post_init(self, context):
        self.checkin_date = datetime.strptime(self.checkin_date, "%Y-%m-%d").date()
        self.checkout_date = datetime.strptime(self.checkout_date, "%Y-%m-%d").date()


@mcp.tool
def _search_available_hotels(data: SearchArgs) -> list[Hotel] | BookingError:
    """Fetch available stays for specified dates and parameters.

    Args:
       data: A collection of parameters useful for filtering the available hotels

    Returns:
        list[dict]: JSON response containing available stays.

    """

    assert (
        data.checkout_date > data.checkin_date
    ), "Check-out date should be more than check-in date. Without checking in, check-out is not allowed"
    url = f"{base_url}/hotels/search"

    querystring = {
        "adults_number": data.num_adults,
        "children_number": data.num_children,
        "units": "metric",
        "page_number": "0",
        "checkin_date": data.checkin_date,
        "checkout_date": data.checkout_date,
        "categories_filter_ids": "class::2,class::4,free_cancellation::1",
        "children_ages": "5,0",
        "dest_type": data.dest_type,
        "dest_id": data.destination_id,
        "order_by": SortingMethods.POPULARITY,
        "include_adjacency": "true",
        "room_number": data.num_rooms,
        "filter_by_currency": "INR",
        "locale": "en-gb",
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)

        response.raise_for_status()
        response = response.json()
    except requests.HTTPError as err:
        if response.status_code == 422:
            return BookingError(**response.json())

    response = response.get("result", [])[: data.max_results]

    # Define a set of keys to remove
    keys_to_remove: Set[str] = {
        "review_nr",
        "review_score",
        "selected_review_topic",
        "review_recommendation",
        "review_score_word",
        "max_photo_url",
        "max_1440_photo_url",
        "native_ads_tracking",
        "native_ads_cpc",
        "block_ids",
        "in_best_district",
        "ufi",
        "timezone",
        "bwallet",
        "native_ad_id",
        "default_wishlist_name",
        "selected_review_topic",
        "class_is_estimated",
        "main_photo_id",
        "wishlist_count",
        "genius_discount_percentage",
    }

    # Remove the keys for each item in the response
    for item in response:
        for key in keys_to_remove:
            item.pop(key, None)

        # Remove specific nested keys
        if "composite_price_breakdown" in item:
            breakdown = item["composite_price_breakdown"]
            breakdown.pop("benefits", None)
            breakdown.pop("price_display_config", None)
            breakdown.pop("strikethrough_amount", None)
            breakdown.pop("all_inclusive_amount_hotel_currency", None)
            breakdown.pop("all_inclusive_amount", None)
            breakdown.pop("price_breakdown", None)

    try:
        _ = []
        for item in response:
            result = validate(item, Hotel.model_json_schema(mode="serialization"))
            if "composite_price_breakdown" in item:
                _.append(Hotel(**item))
        return _
    except Exception as e:
        return BookingError(detail=e)


@mcp.tool
def _fetch_review_scores(hotel_id: str):
    """Fetch review scores for a given hotel ID.

    Args:
        hotel_id (str): The ID of the hotel to fetch review scores for.

    Returns:
        dict: JSON response containing review scores.
    """
    url = f"{base_url}/hotels/review-scores"

    querystring = {"hotel_id": hotel_id, "locale": "en-gb"}

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    return response.json()


# @mcp.tool
def _fetch_hotel_description(hotel_id: str):
    """Fetch the description of a given hotel ID.

    Args:
        hotel_id (str): The ID of the hotel to fetch the description for.

    Returns:
        dict: JSON response containing the hotel description.
    """
    url = f"{base_url}/hotels/description"

    querystring = {"locale": "en-gb", "hotel_id": hotel_id}

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    return response.json()


# @mcp.tool
def _fetch_hotel_facilities(hotel_id: str):
    """Fetch the facilities of a given hotel ID.

    Args:
        hotel_id (str): The ID of the hotel to fetch facilities for.

    Returns:
        dict: JSON response containing the hotel facilities.
    """
    url = f"{base_url}/hotels/facilities"

    querystring = {"locale": "en-gb", "hotel_id": hotel_id}

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    return response.json()


@mcp.tool
def _fetch_hotel_reviews(hotel_id: str) -> list[HotelReview]:
    """Fetch reviews for a given hotel ID.

    Args:
        hotel_id (str): The ID of the hotel to fetch reviews for.

    Returns:
        dict: JSON response containing hotel reviews.
    """
    url = f"{base_url}/hotels/reviews"

    querystring = {
        "customer_type": "solo_traveller,review_category_group_of_friends",
        "locale": "en-gb",
        "language_filter": "en-gb,de,fr",
        "page_number": "0",
        "sort_type": "SORT_MOST_RELEVANT",
        "hotel_id": hotel_id,
    }

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    response = response.json()
    result = []
    keys_to_remove = {"author", "pros_translated", "title_translated", "reviewer_photos", "cons_translated", "is_trivial"}
    
    for item in response.get("result", []):
        # Remove non-essential information and specified keys
        for key in keys_to_remove:
            item.pop(key, None)
        item.get("stayed_room_info", {}).pop("photo", None)

        result.append(HotelReview(**item))
    return result


# @mcp.tool
def _fetch_hotel_room_list(
    hotel_id: str,
    checkin_date: date,
    checkout_date: date,
    adults_number_by_rooms: str,
    children_number_by_rooms: str,
):
    """Fetch the room list for a given hotel ID.

    Args:
        hotel_id (str): The ID of the hotel to fetch the room list for.
        checkin_date (date): The check-in date.
        checkout_date (date): The check-out date.
        adults_number_by_rooms (str): The number of adults per room.
        children_number_by_rooms (str): The number of children per room.

    Returns:
        dict: JSON response containing the room list.
    """
    url = f"{base_url}/hotels/room-list"

    querystring = {
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "locale": "en-gb",
        "units": "metric",
        "children_ages": "5,0,9",
        "adults_number_by_rooms": adults_number_by_rooms,
        "currency": "INR",
        "children_number_by_rooms": children_number_by_rooms,
        "hotel_id": hotel_id,
    }

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    return response.json()


# @mcp.tool
def _fetch_hotel_pictures(hotel_id: str):
    """Fetch the pictures for a given hotel ID.

    Args:
        hotel_id (str): The ID of the hotel to fetch pictures for.

    Returns:
        dict: JSON response containing the hotel pictures.
    """
    url = f"{base_url}/hotels/photos"

    querystring = {"hotel_id": hotel_id, "locale": "en-gb"}

    response = requests.get(url, headers=headers, params=querystring)

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    # Start an HTTP server on port 8000
    mcp.run(transport="http", host="127.0.0.1", port=8000)


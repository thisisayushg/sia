from enum import StrEnum


class DestinationType(StrEnum):
    CITY = "city"
    REGION = "region"
    LANDMARK = "landmark"
    DISTRICT = "district"
    HOTEL = "hotel"
    COUNTRY = "country"
    AIRPORT = "airport"
    LAT_LONG = "latlong"
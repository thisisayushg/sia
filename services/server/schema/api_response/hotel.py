from pydantic import BaseModel, Field
from typing import Any, Optional, Dict


class Amount(BaseModel):
    currency: str = Field(..., description="The currency of the amount")
    value: float = Field(..., description="The value of the amount")
    amount_unrounded: str = Field(
        ..., description="The unrounded amount in string format"
    )
    amount_rounded: str = Field(..., description="The rounded amount in string format")


class Base(BaseModel):
    kind: str = Field(..., description="The kind of the base")
    base_amount: Optional[float] = Field(
        None, description="The base amount (if applicable)"
    )


class Details(BaseModel):
    details: Optional[str] = Field(
        None, description="The details of the item (if applicable)"
    )


class Item(BaseModel):
    item_amount: Amount = Field(..., description="The amount of the item")
    name: str = Field(..., description="The name of the item")
    kind: str = Field(..., description="The kind of the item (charge or discount)")
    inclusion_type: Optional[str] = Field(
        None, description="The inclusion type of the item (if applicable)"
    )
    details: Optional[Details | str] = Field(
        None, description="The details of the item (if applicable)"
    )
    identifier: Optional[str] = Field(
        None, description="The identifier of the item (if applicable)"
    )
    base: Base = Field(..., description="The base details of the item")


class Benefit(BaseModel):
    details: str = Field(..., description="The details of the badge")
    badge_variant: str = Field(..., description="The variant of the badge")
    kind: str = Field(..., description="The kind of the badge")
    name: str = Field(..., description="The name of the badge")
    identifier: str = Field(..., description="The identifier of the badge")
    icon: Optional[str] = Field(
        None, description="The icon of the badge (if applicable)"
    )


class ChargesDetails(BaseModel):
    mode: str = Field(..., description="The mode of the charges details")
    amount: Dict = Field(..., description="The amount details")
    translated_copy: str = Field(
        ..., description="The translated copy of the charges details"
    )


class CompositePriceBreakdown(BaseModel):
    items: list[Item] = Field(
        description="Individual price components (e.g., base rate, taxes, discounts) that make up the full price breakdown."
    )

    price_display_config: Optional[list[Dict[str, Any]]] = Field(
        default=None,
        description="Configuration rules that determine how price items should be displayed to the user.",
    )

    gross_amount_hotel_currency: Amount = Field(
        description="Total gross amount expressed in the hotel's local currency before any discounts or adjustments."
    )

    strikethrough_amount: Optional[Amount] = Field(
        default=None,
        description="Original price before discounts, shown as a strikethrough value when a discount applies.",
    )

    discounted_amount: Optional[Amount] = Field(
        default=None,
        description="Total price after applying discounts but before adding taxes or additional charges.",
    )

    included_taxes_and_charges_amount: Optional[Amount] = Field(
        default=None,
        description="Total amount of taxes and charges that are included in the displayed price.",
    )

    excluded_amount: Optional[Amount] = Field(
        default=None,
        description="Amount of taxes or charges that are not included in the main price and may be paid separately at the property.",
    )

    gross_amount: Optional[Amount] = Field(
        default=None,
        description="Gross amount in the display currency, including all mandatory charges but before optional discounts.",
    )

    gross_amount_per_night: Optional[Amount] = Field(
        default=None,
        description="Gross amount divided by the number of nights, used for per-night price displays.",
    )

    benefits: Optional[list[Benefit]] = Field(
        default=None,
        description="List of benefits or perks included with the booking price (e.g., free breakfast, room upgrades)."
    )

    charges_details: Optional[ChargesDetails] = Field(
        default=None,
        description="Detailed breakdown of taxes, fees, and mandatory charges applied to the booking."
    )

    net_amount: Optional[Amount] = Field(
        default=None,
        description="Net payable amount after all discounts, taxes, and mandatory charges.",
    )

    all_inclusive_amount_hotel_currency: Optional[Amount] = Field(
        default=None,
        description="Final all-inclusive price in the hotel's local currency, covering all mandatory costs.",
    )

    all_inclusive_amount: Optional[Amount] = Field(
        default=None,
        description="Final all-inclusive price in the display currency, including taxes and charges.",
    )

    strikethrough_amount_per_night: Optional[Amount] = Field(
        default=None,
        description="Original, undiscounted price per night used for comparison or promotional display.",
    )

    charges: Optional[Dict] = Field(
        default=None,
        description="Dictionary containing raw charge components (e.g., tax categories, fees) associated with the booking."
    )


class Checkout(BaseModel):
    stay_from: str = Field(..., description="The checkout time from", alias="from")
    until: str = Field(..., description="The checkout time until")


class Bwallet(BaseModel):
    hotel_eligibility: int = Field(..., description="Hotel eligibility for Bwallet")


class PriceBreakdown(BaseModel):
    has_tax_exceptions: Optional[None] = Field(
        None, description="Whether there are tax exceptions"
    )
    gross_price: Optional[None] = Field(None, description="The gross price")
    has_fine_print_charges: Optional[None] = Field(
        None, description="Whether there are fine print charges"
    )
    currency: Optional[None] = Field(None, description="Currency of the price")
    sum_excluded_raw: Optional[None] = Field(None, description="Sum excluded raw")
    all_inclusive_price: Optional[None] = Field(None, description="All-inclusive price")
    has_incalculable_charges: Optional[None] = Field(
        None, description="Whether there are incalculable charges"
    )


class Checkin(BaseModel):
    stay_from: str = Field(..., description="The checkin time from", alias="from")
    until: str = Field(..., description="The checkin time until")


class Hotel(BaseModel):
    city: str = Field(..., description="City of the hotel")
    composite_price_breakdown: CompositePriceBreakdown = Field(
        None,
        description="Details of the price, the breakdown into individual components like taxes and base price and discount",
    )
    longitude: float = Field(..., description="The longitude of the hotel")
    is_geo_rate: str | int = Field("", description="Whether the rate is geographical")
    latitude: float = Field(..., description="The latitude of the hotel")
    updated_checkout: Optional[None] = Field(None, description="Updated checkout time")
    preferred_plus: int = Field(..., description="Preferred plus status")
    is_genius_deal: int = Field(..., description="Whether it is a Genius deal")
    review_nr: Optional[int] = Field(None, description="Number of reviews")
    # wishlist_count: int = Field(..., description="Wishlist count")
    is_mobile_deal: int = Field(..., description="Whether it is a mobile deal")
    address_trans: str = Field(..., description="Translated address")
    district: str = Field(..., description="District (empty)")
    address: str = Field(..., description="Address")
    url: str = Field(..., description="URL of the hotel")
    is_no_prepayment_block: int = Field(
        ..., description="Whether there is a no-prepayment block"
    )
    checkout: Checkout = Field(..., description="Checkout time details")
    hotel_id: int = Field(..., description="Hotel ID")
    country_trans: str = Field(..., description="Translated country")
    distance: str = Field(..., description="Distance from location")
    cc_required: int = Field(..., description="Whether credit card is required")
    hotel_name_trans: str = Field(..., description="Translated hotel name")
    # genius_discount_percentage: int = Field(..., description="Genius discount percentage")
    review_score: Optional[float] = Field(None, description="Review score")
    mobile_discount_percentage: float = Field(
        ..., description="Mobile discount percentage"
    )
    id: str = Field(..., description="Property card ID")
    # bwallet: Bwallet = Field(..., description="Bwallet eligibility details")
    # native_ad_id: str = Field(..., description="Native ad ID")
    countrycode: str = Field(..., description="Country code")
    district_id: int = Field(..., description="District ID")
    accommodation_type_name: str = Field(..., description="Accommodation type name")
    is_beach_front: int = Field(..., description="Whether it is beach front")
    # price_breakdown: PriceBreakdown = Field(..., description="Price breakdown details")
    property_cribs_availability: int = Field(
        ..., description="Property cribs availability"
    )
    children_not_allowed: int = Field(..., description="Children not allowed")
    has_free_parking: Optional[int] = Field(
        0, description="Whether there is free parking"
    )
    soldout: int = Field(..., description="Whether it is sold out")
    urgency_room_msg: Optional[str] = Field(None, description="Urgency room message")
    # in_best_district: int = Field(..., description="Whether it is in the best district")
    badges: list = Field(..., description="List of badges")
    city_name_en: str = Field(..., description="City name in English")
    preferred: int = Field(..., description="Preferred status")
    hotel_include_breakfast: Optional[int] = Field(
        0, description="Whether breakfast is included"
    )
    hotel_class: int = Field(..., description="Class of the hotel", alias="class")
    hotel_has_vb_boost: int = Field(..., description="Whether the hotel has VB boost")
    checkin: Checkin = Field(..., description="Checkin time details")
    is_tpi_exclusive_property: int = Field(
        ..., description="Whether it is a TPI exclusive property"
    )
    price_is_final: int = Field(..., description="Whether the price is final")
    is_smart_deal: int = Field(..., description="Whether it is a smart deal")
    updated_checkin: Optional[str] = Field(None, description="Updated checkin time")
    # block_ids: list = Field(..., description="List of block IDs")
    extended: int = Field(..., description="Whether the data is extended")
    cc1: str = Field(..., description="Country code")
    timezone: str = Field(None, description="Timezone")
    distances: list = Field(..., description="List of distances from the center")
    # ufi: int = Field(..., description="Unique ID for the unit")
    type: str = Field(..., description="Type of property card")
    city_in_trans: str = Field(..., description="Translated city name")
    # main_photo_id: int = Field(..., description="ID of the main photo")
    currencycode: str = Field(..., description="Currency code")
    hotel_facilities: str = Field(..., description="Facilities offered by the hotel")
    districts: str = Field(..., description="Districts of the hotel")
    # class_is_estimated: int = Field(..., description="Whether the class is estimated")
    matching_units_configuration: dict = Field(
        ..., description="Configuration of matching units"
    )
    # native_ads_cpc: int = Field(..., description="Native ads CPC")
    default_language: str = Field(..., description="Default language")
    distance_to_cc: str = Field(..., description="Distance to city center")
    main_photo_url: str = Field(..., description="URL of the main photo")
    zip: str = Field(..., description="ZIP code")
    cant_book: int = Field(..., description="Whether booking is cant be done")
    city_trans: str = Field(..., description="Translated city name")
    is_free_cancellable: int = Field(..., description="Whether it is free cancellable")
    crib_guaranteed: str | int = Field("", description="Whether a crib is guaranteed")
    distance_to_cc_formatted: Optional[str] = Field(
        None, description="Formatted distance to city center"
    )
    # selected_review_topic: Optional[str] = Field(None, description="Selected review topic")
    is_city_center: int = Field(..., description="Whether it is in the city center")
    review_recommendation: Optional[str] = Field(
        None, description="Review recommendation"
    )
    currency_code: str = Field(..., description="Currency code")
    accommodation_type: int = Field(..., description="Accommodation type")
    hotel_name: str = Field(..., description="Name of the hotel")
    min_total_price: float = Field(..., description="Minimum total price")
    # native_ads_tracking: str = Field(..., description="Native ads tracking")
    # review_score_word: Optional[str] = Field(None, description="Review score word")
    # default_wishlist_name: str = Field(..., description="Default wishlist name")
    # max_photo_url: str = Field(..., description="URL of the maximum photo")
    # max_1440_photo_url: str = Field(..., description="URL of the maximum 1440x1440 photo")


class HotelData(BaseModel):
    primary_count: int = Field(..., description="The primary count of hotels")
    count: int = Field(..., description="The count of hotels")
    room_distribution: list[Dict[str, Any]] = Field(
        ..., description="Provides how many adults and children are stayin"
    )
    map_bounding_box: Dict = Field(..., description="The bounding box of the map")
    total_count_with_filters: int = Field(
        ..., description="The total count of hotels with filters applied"
    )
    unfiltered_count: int = Field(..., description="The unfiltered count of hotels")
    extended_count: int = Field(..., description="The extended count of hotels")
    unfiltered_primary_count: int = Field(
        ..., description="The unfiltered primary count of hotels"
    )
    search_radius: int = Field(..., description="Search radius for hotels")
    sort: list[Dict[Any, Any]] = Field(
        ..., description="The sorting criteria for hotels"
    )
    result: list[Hotel] = Field(..., description="The list of hotels found")

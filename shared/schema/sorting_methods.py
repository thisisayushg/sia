from enum import Enum


class SortingMethods(Enum):
    DISTANCE = ("distance", "Distance from city centre")
    POPULARITY = ("popularity", "Popularity")
    BAYESIAN_REVIEW_SCORE = ("bayesian_review_score", "Guest review score")
    HOTEL_STAR_RATING_DESC = ("class_descending", "Hotel Star Rating descending from stars (5 to 0)")
    HOTEL_STAR_RATING_ASC = ("class_descending", "Hotel Star Rating ascending from stars (0 to 5)")
    PRICE_LOW_TO_HIGH = ("price", "Price (low to high)")
    RELEVANCE = ("SORT_MOST_RELEVANT", "Most relevant to least relevant to the search")
    RECENCY_DESC = ("SORT_RECENT_DESC", "Sort by the latest/most recent results to the oldest ones")
    RECENCY_ASC = ("SORT_RECENT_ASC", "Sort by the oldest results to the newest ones")

    def __init__(self, value, description=None):
        self._value_ = value
        self.description = description

    @property
    def desc(self):
        """Property to easily access the description."""
        return self.description
    
    def __repr__(self):
        return self.value
    
    def __str__(self):
        return self.value

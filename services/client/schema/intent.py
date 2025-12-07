from enum import Enum

class UserIntent(Enum):
    STAY_SEARCH = ("StaySearch", "Intent is to search for any hotel, homestay or similar")
    OTHER = ("Other", "Any other intent which cannot be classified among one of the above")

    
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

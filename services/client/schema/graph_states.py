from typing import Dict
from langgraph.graph import MessagesState
from ..schema.intent import UserIntent


class SupervisorState(MessagesState):
    intent: UserIntent = UserIntent.OTHER


class ElicitationState(MessagesState):
    requirements_gathered: Dict = {}
    intent: UserIntent = None


class RecommendationState(MessagesState):
    requirements_gathered: Dict = {}
    web_search_results = []

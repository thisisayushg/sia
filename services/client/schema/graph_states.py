from typing import Dict
from langgraph.graph import MessagesState
from ..schema.intent import UserIntent
from .scraping_result import ScrapingResult, ScrapingResultCollection


class SupervisorState(MessagesState):
    intent: UserIntent = UserIntent.OTHER


class ElicitationState(SupervisorState):
    requirements_gathered: Dict = {}


class RecommendationState(ElicitationState):
    requirements_gathered: Dict = {}
    scraping_results: ScrapingResultCollection = None
    web_search_results: list = []  # Type Annotation for each field in a GraphState is very important else it will not be injected in the state for next node, even if previous node returns a certain key
    recommendation: str = ''

import sys
import pathlib


project_dir = pathlib.Path(__file__).parents[2]
sys.path.append(project_dir)

import json
from langchain_core.messages import HumanMessage
from shared.utils.helpers import generate_field_description
from dotenv import load_dotenv
from shared.prompt_registry.stay_search import (
    GATHER_INFO_PROMPT,
    REQUIREMENT_GATHERING_INSTRUCTION,
    SEARCH_HOTELS_INSTRUCTION,
    TRAVELLER_INTERPRETATION_INSTRUCTION,
)
from shared.prompt_registry.common import (
    INFORMATION_EXTRACTION_INSTRUCTION,
)
from shared.prompt_registry.general import (
    JSON_RETURN_INSTRUCTION,
)

load_dotenv()
from langchain_core.globals import set_debug

set_debug(True)
from datetime import datetime
from typing import Dict, Literal
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import interrupt, Command
from langchain.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from ..schema.booking_details import DestinationRecommendation, TravelBooking
from ..schema.intent import UserIntent
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)
from langchain.agents import create_agent
from ..utils.middleware import handle_tool_errors
from ..schema.graph_states import ElicitationState


class StaySesarchSubgraph(StateGraph):
    def __init__(self, llm):
        self.llm = llm
        super().__init__(ElicitationState)

    async def gather_requirements(self, state: ElicitationState):
        if state["intent"] == UserIntent.STAY_SEARCH:
            response_model = TravelBooking
        elif state["intent"] == UserIntent.DESTINATION_RECOMMENDATION:
            response_model = DestinationRecommendation

        req_opt_info = generate_field_description(response_model)
        chat = ChatPromptTemplate(
            [
                SystemMessagePromptTemplate.from_template(
                    REQUIREMENT_GATHERING_INSTRUCTION
                ),
                HumanMessagePromptTemplate.from_template(GATHER_INFO_PROMPT),
            ]
        )

        chain = chat | self.llm

        response = await chain.ainvoke(
            {
                "gathered_info": state["requirements_gathered"],
                "information_description": req_opt_info,
            }
        )
        return {"messages": [response]}

    async def present_interrupt(self, state: ElicitationState):
        last_message = state["messages"][-1]
        user_input = interrupt(last_message)

        return {"messages": [HumanMessage(user_input)]}

    async def validate_requirements(
        self, state: ElicitationState
    ) -> Command[Literal["gather_requirements", END]]:
        prev_gathered_req = state.get("requirements_gathered", {})
        chat = ChatPromptTemplate(
            [
                SystemMessagePromptTemplate.from_template(
                    INFORMATION_EXTRACTION_INSTRUCTION
                    + TRAVELLER_INTERPRETATION_INSTRUCTION
                    + JSON_RETURN_INSTRUCTION
                ),
                MessagesPlaceholder(variable_name="chat_history"),
            ]
        )
        struct = {}
        if state["intent"] == UserIntent.STAY_SEARCH:
            response_model = TravelBooking
        elif state["intent"] == UserIntent.DESTINATION_RECOMMENDATION:
            response_model = DestinationRecommendation
        for field, field_info in response_model.model_fields.items():
            struct[field] = (
                f"{field_info.description}. Consider {'null' if field_info.default is None else field_info.default} if not provided"
            )
        struct = json.dumps(struct)

        chain = chat | self.llm | JsonOutputParser()

        response = await chain.ainvoke(
            {
                "chat_history": state["messages"],
                "now": datetime.now(),
                "structure": struct,
            }
        )
        validation_result = response_model.partial_validate(response)
        if validation_result.errors:
            return Command(
                update={
                    "messages": [AIMessage(json.dumps(response))],
                    "requirements_gathered": {
                        **prev_gathered_req,
                        **validation_result.valid_data,
                    },
                },
                goto="gather_requirements",
            )
        return {
            "messages": [AIMessage(json.dumps(response))],
            "requirements_gathered": {
                **prev_gathered_req,
                **validation_result.valid_data,
            },
        }

    def _create_elicitation_subgraph(self):
        eli_subgraph = StateGraph(ElicitationState)

        self._create_elicitation_nodes(eli_subgraph)
        self._connect_elicitation_nodes(eli_subgraph)
        return eli_subgraph.compile()

    def _create_elicitation_nodes(self, graph: StateGraph):
        graph.add_node("validate_requirements", self.validate_requirements)
        graph.add_node("gather_requirements", self.gather_requirements)
        graph.add_node("present_interrupt", self.present_interrupt)

    def _connect_elicitation_nodes(self, graph: StateGraph):
        graph.add_edge(START, "validate_requirements")
        graph.add_edge("gather_requirements", "present_interrupt")
        graph.add_edge("present_interrupt", "validate_requirements")
        # graph.add_edge("validate_requirements", END)

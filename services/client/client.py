from collections import defaultdict
import sys
import pathlib

from shared.prompt_registry.destination_recommendation import DESTINATION_DISCOVER_INSTRUCTION, DESTINATION_PROFILE_INSTRUCTION, WEB_SEARCH_INSTRUCTION

project_dir = pathlib.Path(__file__).parents[2]
sys.path.append(project_dir)

import asyncio
import json
from uuid import uuid4
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI
from shared.utils.helpers import generate_field_description
import os
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from shared.prompt_registry.stay_search import (
    GATHER_INFO_PROMPT,
    REQUIREMENT_GATHERING_INSTRUCTION,
    SEARCH_HOTELS_INSTRUCTION,
    TRAVELLER_INTERPRETATION_INSTRUCTION
)
from shared.prompt_registry.common import (
    INFORMATION_EXTRACTION_INSTRUCTION,
)
from shared.prompt_registry.general import (
    INFER_USER_INTENT,
    GENERAL_SYSTEM_PROMPT,
    JSON_RETURN_INSTRUCTION,
    TOOL_CLASSIFICATION_INSTRUCTION,
)

load_dotenv()
from langchain_core.globals import set_debug

set_debug(True)
from langgraph.checkpoint.memory import InMemorySaver
from datetime import datetime
from typing import Dict, List, Literal, TypedDict, Union
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.types import interrupt, Command
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from .schema.booking_details import DestinationRecommendation, TravelBooking, TravelSearchResultCollection
from .schema.intent import UserIntent
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
    PromptTemplate
)
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from .schema.tool_classification import ToolClassification
from langchain_core.rate_limiters import InMemoryRateLimiter

rate_limiter = InMemoryRateLimiter(
    requests_per_second=1,  # <-- Can only make a request once every 10 seconds!!
    check_every_n_seconds=0.2,  # Wake up every 100 ms to check whether allowed to make a request,
    max_bucket_size=10,  # Controls the maximum burst size.
)

class ElicitationState(MessagesState):
    requirements_gathered: Dict = {}
    intent: UserIntent = None

class RecommendationState(MessagesState):
    requirements_gathered: Dict = {}
    web_search_results = []



async def handle_failure(*args, error=None, **kwargs):
    request, _ = args
    toolmsg = ToolMessage(
            content=
            f"No data found. {str(error)}"
            "Please stop processing this request.",
            tool_call_id=request.tool_call["id"]
        )

    return Command(update={'messages': [toolmsg]}, goto=END)

@wrap_tool_call
# @retry(max_retries=1, delay=2, on_failure=handle_failure)
async def handle_tool_errors(request, handler):
    try:
        return await handler(request)
    except asyncio.CancelledError as e:
        return "Tool execution timed out or was cancelled"
    except Exception as e:
        toolmsg = ToolMessage(
                content=
                f"No data found. {str(e)}"
                "Please stop processing this request.",
                tool_call_id=request.tool_call["id"]
            )

        return Command(update={'messages': [toolmsg]}, goto=END)


class TravelMCPClient(StateGraph):
    def __init__(self):
        super().__init__(ElicitationState)
        self.llm = AzureChatOpenAI(
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_deployment=os.getenv("AZURE_DEPLOYMENT_ANME"),
            rate_limiter=rate_limiter
        )
        self.exit_stack = AsyncExitStack()

    async def connect_to_stdio_server(self, cmd: str, args: list):
        # Local stack for error isolation
        local_stack = AsyncExitStack()

        try:
            # Define the server params
            server_params = StdioServerParameters(command=cmd, args=args)
            # Create a transport context for STDIO
            transport_context = stdio_client(server_params)

            # Get read and write stream from transport context
            read, write = await local_stack.enter_async_context(transport_context)

            # Create client session with transport context
            session_ctx = ClientSession(read, write)

            # Get client session
            client_session = await local_stack.enter_async_context(session_ctx)

            # Initialize session
            await client_session.initialize()
            # Load the tools on this server
            tools = await load_mcp_tools(client_session)
            # SUCCESS: Transfer all cleanup callbacks to main exit_stack
            # This prevents local_stack from closing the connections
            self.exit_stack.push_async_exit(local_stack.pop_all())
        
            return tools
        
        except (asyncio.CancelledError, Exception) as e:
            # FAILURE: Clean up local resources only
            try:
                await local_stack.aclose()
            except Exception as cleanup_error:
                print(f"Cleanup error for {cmd}: {cleanup_error}")
            print(f"Server {cmd} failed: {e}")
            return []

    async def connect_to_server(self, server_url):
        # Local stack for error isolation
        local_stack = AsyncExitStack()

        try:
            # create client transport context for HTTP
            client_transport = streamablehttp_client(server_url)

            # Get the read and write streams for creating client session context
            read, write, _ = await local_stack.enter_async_context(
                client_transport
            )

            # Create client session context
            session_ctx = ClientSession(read, write)
            client_Session = await local_stack.enter_async_context(session_ctx)
            
            await client_Session.initialize()
            # Pass the session to langchain to load the tools from
            tools = await load_mcp_tools(session=client_Session)

            # SUCCESS: Transfer all cleanup callbacks to main exit_stack
            # This prevents local_stack from closing the connections
            self.exit_stack.push_async_exit(local_stack.pop_all())

            return tools
        except (asyncio.CancelledError, Exception) as e:
            # FAILURE: Clean up local resources only
            try:
                await local_stack.aclose()
            except Exception as cleanup_error:
                print(f"Cleanup error for {server_url}: {cleanup_error}")
            print(f"Server {server_url} failed. Please ensure that the service is running.")
            return []

    async def supervisor(self, state: MessagesState) -> Command[Literal['elicitation', 'general']]:
        chat = ChatPromptTemplate(
            [
                SystemMessagePromptTemplate.from_template(
                    INFER_USER_INTENT
                ),
                MessagesPlaceholder(variable_name="chat_history")
            ]
        )

        chain = chat | self.llm
        last_message = state['messages'][-1]

        assert isinstance(last_message, HumanMessage)
        intent_categories = ''
        for idx, i in enumerate(UserIntent, 1):
            intent_categories += f"{idx}. {i.value} : {i.description}\n"

        response = await chain.ainvoke(
            {
                "chat_history": [last_message],
                "intent_categories": intent_categories
            }
        )
        if response.content == UserIntent.OTHER.value:
            return Command(goto="general", update={})
        return Command(goto="elicitation", update={'intent': UserIntent(response.content)})
    
    async def general(self, state: MessagesState) -> Command[Literal[END]]:
        agent = create_agent(model=self.llm, tools=self.general_toolkit, system_prompt=GENERAL_SYSTEM_PROMPT.format(now=datetime.now()))
        last_message = state['messages'][-1]
        response = await agent.ainvoke(state)
        return Command(goto=END, update={'messages': response['messages']})
    
    async def gather_requirements(self, state: ElicitationState):
        if state['intent'] == UserIntent.STAY_SEARCH:
            response_model = TravelBooking
        elif state['intent'] == UserIntent.DESTINATION_RECOMMENDATION:
            response_model = DestinationRecommendation

        req_opt_info = generate_field_description(response_model)
        chat = ChatPromptTemplate(
            [
                SystemMessagePromptTemplate.from_template(
                    REQUIREMENT_GATHERING_INSTRUCTION
                ),
                HumanMessagePromptTemplate.from_template(GATHER_INFO_PROMPT)
            ]
        )

        chain = chat | self.llm

        response = await chain.ainvoke(
            {
                "gathered_info": state["requirements_gathered"],
                "information_description": req_opt_info
            }
        )
        return {'messages': [response]}

    async def present_interrupt(self, state: ElicitationState):
        last_message = state['messages'][-1]
        user_input = interrupt(last_message)

        return {'messages': [HumanMessage(user_input)]}

    async def validate_requirements(
        self, state: ElicitationState
    ) -> Command[Literal["gather_requirements", END]]:
        prev_gathered_req = state.get('requirements_gathered', {})
        chat = ChatPromptTemplate(
            [
                SystemMessagePromptTemplate.from_template(
                    INFORMATION_EXTRACTION_INSTRUCTION + TRAVELLER_INTERPRETATION_INSTRUCTION + JSON_RETURN_INSTRUCTION
                ),
                MessagesPlaceholder(variable_name="chat_history"),
            ]
        )
        struct = {}
        if state['intent'] == UserIntent.STAY_SEARCH:
            response_model = TravelBooking
        elif state['intent'] == UserIntent.DESTINATION_RECOMMENDATION:
            response_model = DestinationRecommendation
        for field, field_info in response_model.model_fields.items():
            struct[field] = f"{field_info.description}. Consider {'null' if field_info.default is None else field_info.default} if not provided"
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
                    'messages': [AIMessage(json.dumps(response))],
                    "requirements_gathered": {**prev_gathered_req, **validation_result.valid_data},
                },
                goto="gather_requirements",
            )
        if state['intent'] == UserIntent.DESTINATION_RECOMMENDATION:
            return Command(update={'messages': [AIMessage(json.dumps(response))], "requirements_gathered": {**prev_gathered_req, **validation_result.valid_data}}, goto="recommend_suitable_destination", graph=Command.PARENT)
        else:
            return Command(update={'messages': [AIMessage(json.dumps(response))]}, goto="check_stays", graph=Command.PARENT)
    
    async def _check_for_stays(self, state: ElicitationState):
        last_message = state['messages'][-1]
        agent = create_agent(model=self.llm, tools=self.booking_toolkit, system_prompt=SEARCH_HOTELS_INSTRUCTION,  middleware=[handle_tool_errors])
        try:
            response = await agent.ainvoke({'messages':[last_message]})
        except Exception as e:
            print(e)
        return response
    
    async def _perform_web_search(self, state: ElicitationState)->:
        last_message = state['messages'][-1]
        requirements_gathered = state['requirements_gathered']
        toolkit = self.tools_collection['web_tools'] + self.tools_collection['map_tools']
        system_prompt = WEB_SEARCH_INSTRUCTION.format(source_count = 5, user_preferences = requirements_gathered)
        for t in toolkit:
            print(t.name)
        agent = create_agent(model=self.llm, tools=toolkit, system_prompt=system_prompt,  middleware=[handle_tool_errors], response_format=TravelSearchResultCollection)
        response = await agent.ainvoke({'messages':[last_message]})
        if response.get("structured_response"):
            results: TravelSearchResultCollection = response['structured_response']
            return {'web_search_results': results.search_results}

        return {}
    
    def _parse_webpage(self, state: RecommendationState):
        web_search_results = state['web_search_results']

    def _md_conversion(self, state: ElicitationState):
        ...

    def _investigate_places(self, state: ElicitationState):
        ...
    
    def _create_recommendation_subgraph(self):
        destination_recommendation_subgraph = StateGraph(ElicitationState)
        self._create_recommendation_nodes(destination_recommendation_subgraph)
        self._connect_recommendation_nodes(destination_recommendation_subgraph)

    def _create_recommendation_nodes(self, graph: StateGraph):
        graph.add_node("perform_websearch", self._perform_web_search)
        graph.add_node("parse_webpage", self._parse_webpage)
        graph.add_node("convert_tro_markdown", self._md_conversion)
        graph.add_node("investigate_places", self._investigate_places)

    def _connect_recommendation_nodes(self, graph: StateGraph):
        graph.add_edge("perform_websearch", "parse_webpage")
        graph.add_edge("parse_webpage", "convert_to_markdown")
        graph.add_edge("convert_to_markdown", "investigate_places")
        graph.add_edge("investigate_places", END)

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

    def create_nodes(self):
        self.add_node("supervisor", self.supervisor)
        self.add_node("general",self.general)
        self.add_node("check_stays", self._check_for_stays)

        dest_recommendation_subgraph = self._create_recommendation_subgraph()
        self.add_node("recommend_suitable_destination", dest_recommendation_subgraph)

        eli_subgraph = self._create_elicitation_subgraph()
        self.add_node("elicitation", eli_subgraph)

    def connect_nodes(self):
        self.add_edge(START, "supervisor")
        self.add_edge("check_stays", END)
        self.add_edge("recommend_suitable_destination", END)

    async def connect_to_mcp_servers(self):
        self.general_toolkit, self.booking_toolkit = [], []
        tools = []
        tools.extend(
            await self.connect_to_server("http://localhost:8000/mcp")
        )
        
        # Tavily Search MCP Server
        tools.extend(
            await self.connect_to_server("http://localhost:2400/mcp")
        )

        # OpenWeather MCP Server
        tools.extend(
            await self.connect_to_server("http://localhost:3400/mcp")
        )

        # OpenStreet Map MCP Server
        tools.extend(
            await self.connect_to_server("http://localhost:4400/mcp")
        )

        # OpenBNB MCP Server
        tools.extend(
            await self.connect_to_server("http://localhost:5400/mcp")
        )
        struct = {}
        for field, field_info in ToolClassification.model_fields.items():
            if field_info.default_factory is not None:
                dfault = f"Consider {eval(field_info.default_factory.__name__)()} if not provided"
            else:
                dfault = f"Consider {'null' if field_info.default is None else field_info.default} if not provided"
            struct[field] = f"{field_info.description}. " + dfault
        struct = json.dumps(struct)
        prompt = PromptTemplate.from_template(TOOL_CLASSIFICATION_INSTRUCTION + JSON_RETURN_INSTRUCTION)

        chain =  prompt | self.llm |JsonOutputParser()
        response = chain.invoke({
            'tool_classes': '\n- '.join(ToolClassification.model_fields),
            'structure': struct,
            'tools':  '\n- '.join([f"{t.name}: {t.description.partition("Args:\n")[0]}" for t in tools])
        })
        response = ToolClassification.model_validate(response)
        self.tools_collection = defaultdict(list)
        for category, toolnames in response:
            for toolname in toolnames:
                for t in tools:
                    if t.name == toolname:
                        self.tools_collection[category].append(t)
                        break

    async def cleanup(self):
        await self.exit_stack.aclose()


async def main():
    try:
        travel_workflow = TravelMCPClient()
        await travel_workflow.connect_to_mcp_servers()
        travel_workflow.create_nodes()
        travel_workflow.connect_nodes()

        # Generate thread_id for tracking state across interrupts (HITL)
        thread_id = uuid4()
        config = {'configurable': {'thread_id': thread_id}}
        graph = travel_workflow.compile(checkpointer=InMemorySaver())

        conversation_history = []
        while True:
            query = input("\nHello. What is your query? \n")
            fresh_exec = True
            while True:
                if fresh_exec:
                    fresh_exec = False
                    graph_input = {"messages": [*conversation_history, HumanMessage(query)]}
                else:
                    graph_input = Command(resume=query)

                response = ''
                async for mode, chunk in graph.astream(
                        graph_input,
                        stream_mode=["messages", "updates"],
                        config=config,
                    ):
                    if mode == "messages":
                        message_chunk, metadata = chunk  # "messages" yields (message_chunk, metadata) [web:42]
                        if not isinstance(message_chunk, ToolMessage) and getattr(message_chunk, "content", None) and metadata['langgraph_node'] != 'supervisor':
                            print(message_chunk.content, end="", flush=True)

                    elif mode == "updates":
                        # "updates" yields dicts like {"node_name": {...}} [web:42]
                        # Interrupt info may appear in streamed state depending on version/config;
                        # so we look for it defensively in the update payload.
                        #
                        # Common patterns people see are:
                        # - {"__interrupt__": [...]}  (interrupts exposed in state)
                        # - {"some_node": {"__interrupt__": [...]}}
                        if "__interrupt__" in chunk:
                            interrupt_payload = chunk["__interrupt__"][0].value
                        else:
                            # search nested
                            for _, v in chunk.items():
                                if isinstance(v, dict) and "__interrupt__" in v:
                                    interrupt_payload = v["__interrupt__"][0].value

                        if "interrupt_payload" in locals() and interrupt_payload is not None:
                            # We can stop consuming the stream now; graph is paused and checkpointed.
                            query = input(interrupt_payload.content + "\n")
                            interrupt_payload = None
                            break
                else:
                    break

    except Exception as e:
        print(e)


if __name__ == "__main__":
    asyncio.run(main())

from collections import defaultdict
import sys
import pathlib


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
import os
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from shared.prompt_registry.general import (
    INFER_USER_INTENT,
    GENERAL_SYSTEM_PROMPT,
)

load_dotenv()
from langchain_core.globals import set_debug

# set_debug(True)
from shared.utils.helpers import messages_to_dicts
from langgraph.checkpoint.memory import InMemorySaver
from datetime import datetime
from typing import Dict, Literal
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt, Command
from langchain.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from .schema.intent import UserIntent
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate
)
from langchain.agents import create_agent
from langchain.messages import ToolMessage
from .schema.tool_classification import ToolClassification
from .utils.middleware import rate_limiter, handle_tool_errors
from .schema.graph_states import ElicitationState, SupervisorState
from .subgraphs.destination_recommendation import RecommendationSubgraph
from .subgraphs.stay_search import StaySesarchSubgraph
from shared.prompt_registry.stay_search import SEARCH_HOTELS_INSTRUCTION
from langfuse.langchain import CallbackHandler
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path
from shared.config import Config

langfuse_handler = CallbackHandler()
class TravelMCPClient(StateGraph):
    def __init__(self):
        super().__init__(SupervisorState)

        config = Config.load_config()
        if config.provider == 'azure' and config.service == 'openai':
            from langchain_openai import AzureChatOpenAI

            self.llm = AzureChatOpenAI(
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
                rate_limiter=rate_limiter
            )
        elif config.provider == 'azure' and config.service == 'model_inference':
            from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel

            self.llm = AzureAIChatCompletionsModel(
                endpoint=os.environ["AZURE_INFERENCE_ENDPOINT"],
                credential=os.environ["AZURE_INFERENCE_CREDENTIAL"],
                model=os.environ['AZURE_DEPLOYMENT_NAME'],
            )
        elif not config.provider and config.local_model_hosting_service == 'llamacpp':
            from langchain_community.chat_models import ChatLlamaCpp

            model_id = "LiquidAI/LFM2.5-1.2B-Instruct"
            model_path = str(Path.home() / "AppData/Local/llama.cpp/LiquidAI_LFM2.5-1.2B-Instruct-GGUF_LFM2.5-1.2B-Instruct-Q4_K_M.gguf")

            self.llm = ChatLlamaCpp(
                temperature=0,
                model_path=model_path,
                streaming=False,
                max_tokens=512,
                rope_freq_scale = 0.0,  # This is important parameter for ChatLlamaCPP; else the Llama models behave different than with Native LlamaCPP 
                rope_freq_base = 0.0,  # This is important parameter for ChatLlamaCPP; else the Llama models behave different than with Native LlamaCPP 
                n_batch=512,
                n_ctx = 5120
            )
        # Using ChatHuggingFace is the only way to invoke few models with correct/expected format of the model
        # Huggingface Pipeline.from_model_id() does not work, since behind the scene, it doesn't call
        # apply_chat_template() on the messages
        # self.llm =  ChatHuggingFace.from_model_id(
        #         model_id = model_id,
        #         task="text-generation",
        #         pipeline_kwargs={
        #             "max_new_tokens": 1000, 
        #             'temperature':0.2, 
        #             'top_p':0.1, 
        #             'do_sample':True, 
        #             'return_full_text': False,
        #             'top_p': 0.1,
        #             'repetition_penalty': 1.05
        #         }
        # )

        # self.llm = ChatHuggingFace(llm=llm)
        # self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.exit_stack = AsyncExitStack()
        self.tools_collection = ToolClassification()

    async def connect_to_stdio_server(self, cmd: str, args: list, env: dict):
        # Local stack for error isolation
        local_stack = AsyncExitStack()

        try:
            # Define the server params
            server_params = StdioServerParameters(command=cmd, args=args, env=env)
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
            },
            config={"callbacks": [langfuse_handler], 'metadata': {'langfuse_tags': ['infer_intent']}}
        )
        if response.content == UserIntent.OTHER.value:
            return Command(goto="general", update={})
        return Command(goto="elicitation", update={'intent': UserIntent(response.content)})
    
    async def general(self, state: MessagesState) -> Command[Literal[END]]:
        agent = create_agent(model=self.llm, tools=self.general_toolkit, system_prompt=GENERAL_SYSTEM_PROMPT.format(now=datetime.now()))
        last_message = state['messages'][-1]
        response = await agent.ainvoke(state)
        return Command(goto=END, update={'messages': response['messages']})

    async def _check_for_stays(self, state: ElicitationState):
        last_message = state['messages'][-1]
        agent = create_agent(model=self.llm, tools=self.booking_toolkit, system_prompt=SEARCH_HOTELS_INSTRUCTION,  middleware=[handle_tool_errors])
        try:
            response = await agent.ainvoke({'messages':[last_message]})
        except Exception as e:
            print(e)
        return response

    async def recommend_destination(self, state: ElicitationState):
        response = await self.dest_recommendation_subgraph.ainvoke(state)
        aimessage = AIMessage(content=response.get('investigation_report'))
        return {'messages': [aimessage]}

    async def collect_info(self, state: ElicitationState)->Command[Literal['check_stays', 'recommend_suitable_destination']]:
        response = await self.collect_info_subgraph.ainvoke(state)
        # Only send forward last message since it will be concatenated with existing state because of how Command operates
        last_message = response.get('messages')[-1]
        r = {**response, 'messages': messages_to_dicts([last_message])}

        if state['intent'] == UserIntent.STAY_SEARCH:
            return Command(update=r, goto="check_stays")
        if state['intent'] == UserIntent.DESTINATION_RECOMMENDATION:
            return Command(update=r, goto="recommend_suitable_destination")

    def create_nodes(self):
        self.add_node("supervisor", self.supervisor)
        self.add_node("general",self.general)
        self.add_node("check_stays", self._check_for_stays)

        rec_tools = self.tools_collection.web_tools + self.tools_collection.map_tools
        self.dest_recommendation_subgraph = RecommendationSubgraph(self.llm, toolkit=rec_tools)._create_recommendation_subgraph()
        self.add_node("recommend_suitable_destination", self.recommend_destination)

        self.collect_info_subgraph = StaySesarchSubgraph(self.llm)._create_elicitation_subgraph()
        self.add_node("elicitation", self.collect_info)

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

        await self._classify_tools(tools)
        self.general_toolkit = tools

    async def cleanup(self):
        await self.exit_stack.aclose()

    async def _classify_tools(self, tools: list):
        from torch import cuda, bfloat16, no_grad
        model_id = "LiquidAI/LFM2.5-1.2B-Instruct"

        device = "cuda" if cuda.is_available() else "cpu"

        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=bfloat16
        ).to(device)

        tokenizer = AutoTokenizer.from_pretrained(model_id)

        categories = ToolClassification.model_fields.keys()

        def classify_tool(tool_name, description):

            prompt = f"""
            Tool: {tool_name}
            Description: {description}

            Category:"""

            inputs = tokenizer(prompt, return_tensors="pt").to(device)

            with no_grad():
                outputs = model(**inputs)

            logits = outputs.logits[0, -1]

            scores = {}
            for cat in categories:
                token_id = tokenizer.encode(cat, add_special_tokens=False)[0]
                scores[cat] = logits[token_id].item()

            return max(scores, key=scores.get)        # Save in tools classified so far in previous batches

        classified_tools = defaultdict(list)
        for tool in tools:
            category = classify_tool(tool.name, tool.description)
            classified_tools[category].append(tool)

        self.tools_collection = ToolClassification.model_validate(classified_tools)

async def main():
    try:
        travel_workflow = TravelMCPClient()
        await travel_workflow.connect_to_mcp_servers()
        travel_workflow.create_nodes()
        travel_workflow.connect_nodes()

        # Generate thread_id for tracking state across interrupts (HITL)
        thread_id = uuid4()
        config: RunnableConfig = {'configurable': {'thread_id': thread_id}, 'max_concurrency': 2}
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

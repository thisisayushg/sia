import chainlit as cl
import asyncio
import streamlit as st
from langchain_openai.chat_models import ChatOpenAI
from client import TravelMCPClient, change_system_prompt
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from langchain.agents import create_agent
from shared.utils.prompt_registry import REQUIREMENT_GATHERING_INSTRUCTION
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from datetime import datetime
from uuid import uuid4
from langchain.agents.middleware import TodoListMiddleware
from typing import cast
from client import ElicitationState
from langchain_core.prompts import PromptTemplate


@cl.on_chat_start
async def setup():
    client = TravelMCPClient()
    try:
        toolkit = []
        tools = await client.connect_to_server("http://localhost:8000/mcp")
        toolkit.extend(tools)

        tools = await client.connect_to_stdio_server(
            cmd="npx", args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
        )
        toolkit.extend(tools)

        system_prompt = PromptTemplate.from_template(REQUIREMENT_GATHERING_INSTRUCTION)
        system_prompt = system_prompt.format(now=datetime.now())
        agent = create_agent(
            system_prompt=system_prompt,
            model=client.llm,
            tools=toolkit,
            checkpointer=InMemorySaver(),
            middleware=[change_system_prompt, TodoListMiddleware()],
        )
        client.agent = agent
        cl.user_session.set('agent', agent)
    except RuntimeWarning as w:
        # Check if the warning is regarding Cotourine was never awaited
        if str(w) == "Cotourine was never awaited!":
            print(w)
        else:
            ...
        client.cleanup()


@cl.on_message
async def on_message(msg: cl.Message):
    agent = cast(CompiledStateGraph, cl.user_session.get("agent"))
    config = {"configurable": {"thread_id": cl.context.session.id}}
    final_answer = cl.Message(content="")
    try:
        async for msg, metadata in agent.astream(
            {"messages": [HumanMessage(content=msg.content)]},
            stream_mode="messages",
            config=RunnableConfig(**config),
        ):
            if (
                msg.content
                and not isinstance(msg, HumanMessage)
                and not isinstance(msg, ToolMessage)
            ):
                await final_answer.stream_token(msg.content)
    except Exception as e:
        print(e)
    await final_answer.send()


if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    import os 

    os.environ['CHAINLIT_PORT'] = '2900'
    run_chainlit(__file__)
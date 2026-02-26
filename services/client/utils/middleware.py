import sys
import pathlib


project_dir = pathlib.Path(__file__).parents[2]
sys.path.append(project_dir)

import asyncio
from dotenv import load_dotenv

load_dotenv()
from langchain_core.globals import set_debug

set_debug(True)
from typing import Dict
from langgraph.graph import END, MessagesState
from langgraph.types import interrupt, Command
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from pydantic  import ValidationError
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain.tools import ToolException


rate_limiter = InMemoryRateLimiter(
    requests_per_second=1,  # <-- Can only make a request once every 10 seconds!!
    check_every_n_seconds=0.2,  # Wake up every 100 ms to check whether allowed to make a request,
    max_bucket_size=10,  # Controls the maximum burst size.
)

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
    except (ValidationError, ToolException) as e:
        if "unexpected keyword argument" in str(e).lower():
            toolmsg = ToolMessage(
                    content=
                    f"Check the parameters provided. Possibly, you need to review the tool description for arguments",
                    tool_call_id=request.tool_call["id"]
                )

            return toolmsg

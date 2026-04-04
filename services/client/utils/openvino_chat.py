import asyncio
import json
from typing import Any, Dict, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.prompt_values import StringPromptValue
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables.config import RunnableConfig
from transformers import AutoTokenizer
from pydantic import PydanticInvalidForJsonSchema
import openvino_genai as ov_genai

class OpenVINOGenAIChat(BaseChatModel):
    """LangChain wrapper for OpenVINO GenAI with native tool calling."""
    llm: Any = None
    model_path: str = ''
    device: str = 'GPU'
    tokenizer: Any = None
    tool_prompt: str = ''

    def __init__(self, model_path: str, device: str = "GPU", **kwargs):
        super().__init__(**kwargs)
        self.llm = ov_genai.LLMPipeline(model_path, device)
        self.tokenizer = self.llm.get_tokenizer()
        self.model_path = model_path
        self.device = device

    @property
    def _llm_type(self) -> str:
        return "openvino_genai"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to GenAI chat format."""
        chat = []

        if isinstance(messages, StringPromptValue):
            chat.append({'role': 'user', 'content': messages.text})
            return chat
        
        if hasattr(messages, 'messages'):
            messages = messages.messages
        for msg in messages:
            role = "system" if isinstance(msg, SystemMessage) else "user" if isinstance(msg, HumanMessage) else "assistant"
            
            if isinstance(msg, ToolMessage):
                role = "function"
                content = f"{msg.name}: {msg.content}"
            else:
                content = msg.content
                
            chat.append({"role": role, "content": content})
        return chat
        
    def _tool_specs(self, tools):
        tool_specs = []

        for tool in tools:
            # --- Get schema ---

            try:
                if hasattr(tool, 'model_json_schema'):
                    # This is likely a structured output schema
                    schema = tool.model_json_schema()
                    name = getattr(tool, "__name__", "structured_output")
                    description = getattr(tool, "__doc__", "")
                elif hasattr(tool, 'args_schema') and hasattr(tool.args_schema, 'model_json_schema'):
                    schema = tool.args_schema.model_json_schema()
                    name = getattr(tool, "name", tool.args_schema.__name__)
                    description = getattr(tool, "description", tool.args_schema.__doc__ or "")
                
                elif hasattr(tool, 'args_schema'):
                    schema = tool.args_schema
                    name = getattr(tool, "name", "unknown_tool")
                    description = getattr(tool, "description", "")
            except PydanticInvalidForJsonSchema:
                if hasattr(tool, 'args_schema'):
                    schema = tool.args_schema
                    name = getattr(tool, "name", "unknown_tool")
                    description = getattr(tool, "description", "")
                else:
                    raise AttributeError(f"Cannot get schema for tool: {tool}")

            # --- IMPORTANT: Use full schema, don't flatten ---
            parameters = {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", [])
            }

            tool_specs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters
                }
            })

        return tool_specs

    def bind_tools(self, tools: List[BaseTool], **kwargs) -> "OpenVINOGenAIChat":
        self._bound_tools = tools

        tool_specs = self._tool_specs(tools)
        self.tool_prompt = f"""
        You use tools via this format:
        {{tool_name}}
        {{"param1": "value"}}

        text

        Available tools:
        {json.dumps(tool_specs, indent=2)}
        """

        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any
    ) -> ChatResult:
        chat_history = self._convert_messages(messages)
        
        config = ov_genai.GenerationConfig(
            max_new_tokens=kwargs.get("max_new_tokens", 256),
            temperature=kwargs.get("temperature", 0.7),
            top_p=kwargs.get("top_p", 0.9),
            stop=stop or []
        )
        prompt = self.tokenizer.apply_chat_template(
            chat_history,
            add_generation_prompt=True,
            tools=self._tool_specs(self._bound_tools) if hasattr(self, '_bound_tools') else []
        )
        
        response = self.llm.generate(prompt, config)
        
        # Parse tool calls (GenAI native format)
        tool_calls = []
        if hasattr(self, '_bound_tools'):
            tool_calls = self._parse_genai_tools(response)
            content = response if not tool_calls else ""
        else:
            content = response
        
        ai_msg = AIMessage(content=content, tool_calls=tool_calls)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def _parse_genai_tools(self, text: str) -> List[Dict]:
        """Parse OpenVINO GenAI tool call format."""
        # GenAI returns structured: {"function_call": {"name": "...", "arguments": {...}}}
        import re
        import uuid
        if not text.lstrip().startswith('<tool_call>') and text.rstrip().endswith('</tool_call>'):
            text = '<tool_call>\n' + text
        
        tool_calls = []
        
        # Pattern matches complete <tool_call> blocks
        pattern = r'<tool_call>\s*\n\s*(\{.*?\})\s*\n\s*</tool_call>'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                # Parse the JSON object inside
                tool_json = json.loads(match.strip())
                
                tool_call = {
                    "name": tool_json.get("name"),
                    "args": tool_json.get("arguments", {}),
                    "id": tool_json.get("id") or f"call_{str(uuid.uuid4())[:8]}"
                }
                
                if tool_call["name"]:  # Valid tool call
                    tool_calls.append(tool_call)
                    
            except json.JSONDecodeError:
                # Skip malformed JSON
                continue
        
        return tool_calls

    def invoke(self, input: List[BaseMessage], config: Optional[RunnableConfig] = None, **kwargs) -> AIMessage:
        result = self._generate(input, **kwargs)
        return result.generations[0].message

    async def ainvoke(self, input: List[BaseMessage], config: Optional[RunnableConfig] = None, **kwargs) -> AIMessage:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: self._generate(input, **kwargs))
        return result.generations[0].message

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_path": self.model_path, "device": self.device}

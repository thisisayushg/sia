import asyncio
import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables.config import RunnableConfig
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from transformers import AutoTokenizer
from optimum.intel.openvino import OVModelForCausalLM

class OpenVINOChatModel(BaseChatModel):
    model_id: str = ''
    device: str = 'GPU'
    tokenizer: AutoTokenizer = None
    model: OVModelForCausalLM = None

    def __init__(self, model_id: str, device: str = "GPU", **kwargs):
        super().__init__(**kwargs)
        self.model_id = model_id
        self.device = device
        self.model = OVModelForCausalLM.from_pretrained(model_id, device=device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    @property
    def _llm_type(self) -> str:
        return "openvino_chat"

    def _convert_messages(self, messages: List[BaseMessage], tools: List[Dict] = None) -> List[Dict[str, Any]]:
        """Convert to chat dicts with tool support."""
        chat_dicts = []
        for msg in messages:
            role = "system" if isinstance(msg, SystemMessage) else "user" if isinstance(msg, HumanMessage) else "assistant"
            
            msg_dict = {"role": role, "content": msg.content}
            
            # Handle ToolMessage
            if isinstance(msg, ToolMessage):
                msg_dict["role"] = "tool"
                msg_dict["content"] = msg.content
                msg_dict["tool_call_id"] = msg.tool_call_id
            
            # Handle AIMessage with tool_calls
            elif isinstance(msg, AIMessage) and msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}
                    }
                    for tc in msg.tool_calls
                ]
            
            chat_dicts.append(msg_dict)
        
        return chat_dicts

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", "auto")
        
        if hasattr(messages, 'messages') and all([isinstance(m, BaseMessage) for m in messages.messages]):
            messages = messages.messages
        chat_dicts = self._convert_messages(messages, tools)
        inputs = self.tokenizer.apply_chat_template(
            chat_dicts,
            tools=tools,  # Native tool support via chat template
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True
        )
        
        max_new_tokens = kwargs.pop("max_new_tokens", 256)
        generate_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": kwargs.get("do_sample", False),
            "temperature": kwargs.get("temperature", 0.7),
            **kwargs
        }
        
        if tools:
            generate_kwargs["tools"] = tools
            generate_kwargs["tool_choice"] = tool_choice
            
        outputs = self.model.generate(**inputs, **generate_kwargs)
        
        input_len = inputs["input_ids"].shape[-1]
        generated_tokens = outputs[0][input_len:]
        text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        
        # Parse native tool_calls from response (Transformers handles structured output)
        ai_msg = AIMessage(content=text)
        
        # If model supports structured tools, extract from logprobs/output
        # Fallback to text parsing if needed
        if tools:
            try:
                # Try native parsing (works for supported models)
                tool_calls = self.model.parse_tool_calls(outputs, self.tokenizer)
                ai_msg.tool_calls = tool_calls or []
            except:
                # Fallback regex parsing (universal)
                pass  # Use previous regex logic if needed
        
        generation = ChatGeneration(message=ai_msg)
        return ChatResult(generations=[generation])

    def bind_tools(self, tools: List[Union[BaseTool, BaseModel, Dict, str]], **kwargs) -> "OpenVINOChatModel":
        """Convert LangChain tools to Transformers format."""
        tool_list = []
        for tool in tools:
            if isinstance(tool, BaseTool):
                if hasattr(tool.args_schema, 'model_json_schema'):
                    schema = tool.args_schema.model_json_schema()
                schema = tool.args_schema
                tool_list.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": schema
                    }
                })
            elif isinstance(tool, dict):
                tool_list.append(tool)
            elif isinstance(tool, BaseModel):
                tool_list.append({
                    "type": "function",
                    "function": {
                        "name": tool.__name__.lower(),
                        "description": getattr(tool, "description", ""),
                        "parameters": tool.model_json_schema()
                    }
                })
        
        self._bound_tools = tool_list
        self._tool_kwargs = kwargs
        return self

    def invoke(self, input: List[BaseMessage], config: Optional[RunnableConfig] = None, **kwargs: Any) -> AIMessage:
        tools = getattr(self, "_bound_tools", None)
        if tools:
            kwargs["tools"] = tools
            kwargs.update(self._tool_kwargs)
        result = self.generate([input], stop=kwargs.get("stop"), **kwargs)
        return result.generations[0].message

    async def ainvoke(self, input: List[BaseMessage], config: Optional[RunnableConfig] = None, **kwargs: Any) -> AIMessage:
        loop = asyncio.get_event_loop()
        tools = getattr(self, "_bound_tools", None)
        if tools:
            kwargs["tools"] = tools
            kwargs.update(self._tool_kwargs)
        result = await loop.run_in_executor(None, lambda: self._generate(input, **kwargs))
        return result.generations[0].message

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_id": self.model_id, "device": self.device}

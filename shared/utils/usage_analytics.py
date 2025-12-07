from typing import Any, Dict, List
from langchain_core.callbacks.base import BaseCallbackHandler


class UsageAnalytics(BaseCallbackHandler):
    """Callback handler to track token usage for AzureChatOpenAI calls."""
    
    def __init__(self):
        """Initialize the usage analytics tracker."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
        self.usage_history = []
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Run when LLM starts running."""
        self.call_count += 1
    
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        # Extract token usage from response
        if hasattr(response, 'llm_output') and response.llm_output:
            token_usage = response.llm_output.get('token_usage', {})
            
            prompt = token_usage.get('prompt_tokens', 0)
            completion = token_usage.get('completion_tokens', 0)
            total = token_usage.get('total_tokens', 0)
            
            # Update totals
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_tokens += total
            
            # Store individual call information
            self.usage_history.append({
                'call_number': self.call_count,
                'prompt_tokens': prompt,
                'completion_tokens': completion,
                'total_tokens': total
            })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of token usage."""
        return {
            'total_calls': self.call_count,
            'total_tokens': self.total_tokens,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'average_tokens_per_call': self.total_tokens / self.call_count if self.call_count > 0 else 0
        }
    
    def reset(self):
        """Reset all counters."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.call_count = 0
        self.usage_history = []


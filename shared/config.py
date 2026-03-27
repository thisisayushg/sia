from pydantic import BaseModel, Field, model_validator
from typing import Optional
from enum import Enum
from pathlib import Path
from yaml import safe_load
import os


class LocalModelHostingService(str, Enum):
    LLAMACPP = "llamacpp"
    HUGGINGFACE = "hf"
    OPENVINO = "openvino"

class ServiceType(str, Enum):
    MODEL_INFERENCE = "model_inference"
    OPENAI = "openai"

class Provider(str, Enum):
    AZURE = "azure"

class Config(BaseModel):
    local_model_path: str = Field(default='', description="Path to local model")
    local_model_hosting_service: Optional[LocalModelHostingService] = Field(default=None)
    model_id: Optional[str] = Field(default=None, description="Model identifier")
    
    provider: Optional[Provider] = Field(default=None)
    service: Optional[ServiceType] = Field(default=None)
    
    enable_llm_tracing: bool = Field(default=False)

    @model_validator(mode='after')
    def validate_model_config(self):
        local_path = self.local_model_path.strip()
        hosting = self.local_model_hosting_service
        model_id = self.model_id or ''
        
        # Local model requires hosting service
        if local_path and hosting is None:
            raise ValueError("local_model_path requires local_model_hosting_service")
            
        # model_id and local_model_path are mutually exclusive
        if local_path and model_id:
            raise ValueError("local_model_path and model_id should not be provided together")
            
        # Provider config incompatible with model config
        if (self.provider or self.service) and (local_path or model_id):
            raise ValueError("provider/service incompatible with model_id/local_model_path")
        
        if model_id and self.local_model_hosting_service != LocalModelHostingService.HUGGINGFACE:
            raise ValueError("model_id is only required with Huggingface models")
        
        # Provider and service must be used together
        if bool(self.provider) != bool(self.service):
            raise ValueError("provider and service must be used together")
        
        if self.service == ServiceType.MODEL_INFERENCE:
            assert os.getenv('AZURE_INFERENCE_ENDPOINT') is not None
            assert os.getenv('AZURE_INFERENCE_CREDENTIAL') is not None
            assert os.getenv('AZURE_DEPLOYMENT_NAME') is not None
            
        elif self.service == ServiceType.OPENAI:
            assert os.getenv('AZURE_OPENAI_API_VERSION') is not None
            assert os.getenv('AZURE_DEPLOYMENT_NAME') is not None
            assert os.getenv('AZURE_OPENAI_ENDPOINT') is not None
            assert os.getenv('AZURE_OPENAI_API_KEY') is not None

        if self.enable_llm_tracing:
            assert os.getenv('LANGFUSE_SECRET_KEY') is not None
            assert os.getenv('LANGFUSE_PUBLIC_KEY') is not None
            assert os.getenv('LANGFUSE_BASE_URL') is not None
        return self

    @classmethod
    def load_config(cls):
        with open(r'shared/config.yaml') as file:
            content = safe_load(file)
        return cls.model_validate(content)  # Pydantic v2 handles YAML via JSON

# Usage example:
config = Config.load_config()

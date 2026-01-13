# -*- coding: utf-8 -*-
"""Fixed version of AgentScopeEmbedding to handle async calls properly.

This module provides a fixed wrapper class that correctly handles async 
embedding model calls in existing event loops, avoiding the asyncio.run()
issue that causes vector=None errors.
"""
import asyncio
from typing import Any, List, Literal, Union, Optional

from mem0.embeddings.base import EmbeddingBase
from mem0.configs.embeddings.base import BaseEmbedderConfig
from pydantic import BaseModel, Field, field_validator

# 修复版本：添加 agentscope_fixed 到支持列表
class FixedEmbedderConfig(BaseModel):
    provider: str = Field(
        description="Provider of the embedding model (e.g., 'ollama', 'openai')",
        default="openai",
    )
    config: Optional[dict] = Field(description="Configuration for the specific embedding model", default={})

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        supported_providers = [
            "openai",
            "ollama",
            "huggingface",
            "azure_openai",
            "gemini",
            "vertexai",
            "together",
            "lmstudio",
            "langchain",
            "aws_bedrock",
            "fastembed",
            "agentscope_fixed",  # 添加这一行
        ]
        if provider in supported_providers:
            return v
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")

class FixedAgentScopeEmbedding(EmbeddingBase):
    """Fixed wrapper for the AgentScope Embedding model.
    
    This class fixes two critical issues in the original AgentScopeEmbedding:
    1. Async call handling in existing event loops
    2. Correct extraction of embedding vectors from response objects
    """
    
    def __init__(self, config: BaseEmbedderConfig | None = None):
        """Initialize the FixedAgentScopeEmbedding wrapper.
        
        Args:
            config: Configuration object containing the AgentScope embedding model
        """
        super().__init__(config)
        
        if self.config.model is None:
            raise ValueError("`model` parameter is required")
            
        from agentscope.embedding import EmbeddingModelBase
        if not isinstance(self.config.model, EmbeddingModelBase):
            raise ValueError("`model` must be an instance of EmbeddingModelBase")
            
        self.agentscope_model = self.config.model

    def embed(
        self,
        text: Union[str, List[str]],
        memory_action: Literal["add", "search", "update"] | None = None,
    ) -> List[float]:
        """Get the embedding for the given text using AgentScope.
        
        This fixed version properly handles async calls in existing event loops
        and correctly extracts the embedding vector from the response.
        
        Args:
            text: The text to embed.
            memory_action: The type of embedding to use.
            
        Returns:
            The embedding vector as a list of floats.
        """
        try:
            # Convert single text to list for AgentScope embedding model
            text_list = [text] if isinstance(text, str) else text
            
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self._async_call(text_list),
                    loop
                )
                response = future.result(timeout=30)  # 30 second timeout
            except RuntimeError:
                # No running loop, we can use asyncio.run safely
                response = asyncio.run(self._async_call(text_list))

            # 🔥 CRITICAL FIX: Extract the actual embedding vector
            # response.embeddings[0] is an Embedding object
            # We need .embedding attribute to get the vector
            if hasattr(response, 'embeddings') and len(response.embeddings) > 0:
                embedding_obj = response.embeddings[0]
                if hasattr(embedding_obj, 'embedding'):
                    vector = embedding_obj.embedding
                else:
                    # Fallback: assume the object itself is the vector
                    vector = embedding_obj
                    
                if vector is None:
                    raise ValueError("Extracted embedding vector is None")
                    
                # Ensure it's a list of floats
                if isinstance(vector, list):
                    return vector
                else:
                    # Convert other iterable types to list
                    return list(vector)
            else:
                raise ValueError(f"Could not extract embeddings from response: {type(response)}")
                
        except Exception as e:
            raise RuntimeError(
                f"Error generating embedding using fixed agentscope model: {str(e)}"
            ) from e
    
    async def _async_call(self, text_list: List[str]) -> Any:
        """Async helper method to call the AgentScope embedding model."""
        return await self.agentscope_model(text_list)
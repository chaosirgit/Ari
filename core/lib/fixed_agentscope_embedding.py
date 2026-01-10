# -*- coding: utf-8 -*-
"""Fixed version of AgentScopeEmbedding to handle async calls properly.

This module provides a fixed wrapper class that correctly handles async 
embedding model calls in existing event loops, avoiding the asyncio.run()
issue that causes vector=None errors.
"""
import asyncio
from typing import Any, List, Literal, Union

from agentscope.memory._mem0_utils import AgentScopeEmbedding


class FixedAgentScopeEmbedding(AgentScopeEmbedding):
    """Fixed wrapper for the AgentScope Embedding model.
    
    This class fixes the issue where asyncio.run() is used in an already
    running event loop, which can cause embedding calls to fail or return
    incorrect results (like None vectors).
    
    Instead of using asyncio.run(), this implementation properly handles
    async calls in existing event loops.
    """
    
    def embed(
        self,
        text: Union[str, List[str]],
        memory_action: Literal["add", "search", "update"] | None = None,
    ) -> List[float]:
        """Get the embedding for the given text using AgentScope.
        
        This fixed version properly handles async calls in existing event loops.
        
        Args:
            text: The text to embed.
            memory_action: The type of embedding to use.
            
        Returns:
            The embedding vector.
        """
        try:
            # Convert single text to list for AgentScope embedding model
            text_list = [text] if isinstance(text, str) else text
            
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self.agentscope_model(text_list),
                    loop
                )
                response = future.result(timeout=30)  # 30 second timeout
            except RuntimeError:
                # No running loop, we can use asyncio.run safely
                async def _async_call():
                    return await self.agentscope_model(text_list)
                response = asyncio.run(_async_call())

            # Extract the embedding vector from the first Embedding object
            # response.embeddings is a list of Embedding objects
            # Each Embedding object has an 'embedding' attribute containing the vector
            if hasattr(response, 'embeddings') and len(response.embeddings) > 0:
                embedding = response.embeddings[0]
            else:
                # If response is already the vector, use it directly
                embedding = response
                
            if embedding is None:
                raise ValueError("Failed to extract embedding from response")
            return embedding
            
        except Exception as e:
            raise RuntimeError(
                f"Error generating embedding using fixed agentscope model: {str(e)}"
            ) from e
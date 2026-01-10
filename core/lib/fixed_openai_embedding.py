# -*- coding: utf-8 -*-
"""Fixed version of OpenAITextEmbedding to handle sync calls properly."""

import asyncio
from typing import List, Union, Optional
from agentscope.embedding import OpenAITextEmbedding as OriginalOpenAITextEmbedding


class FixedOpenAITextEmbedding(OriginalOpenAITextEmbedding):
    """Fixed wrapper for OpenAITextEmbedding that ensures synchronous behavior.
    
    This class wraps the original OpenAITextEmbedding and ensures that
    all calls are properly handled in both sync and async contexts.
    """
    
    def __call__(
        self,
        text: Union[str, List[str]],
        **kwargs: Optional[dict],
    ) -> List[List[float]]:
        """Get embeddings for the given text.
        
        Ensures proper handling of async calls in sync context.
        """
        try:
            # Try to get running loop
            loop = asyncio.get_running_loop()
            # We're in async context, use run_coroutine_threadsafe
            future = asyncio.run_coroutine_threadsafe(
                self._async_call(text, **kwargs),
                loop
            )
            return future.result(timeout=30)
        except RuntimeError:
            # No running loop, we can call directly
            return asyncio.run(self._async_call(text, **kwargs))
    
    async def _async_call(
        self,
        text: Union[str, List[str]],
        **kwargs: Optional[dict],
    ) -> List[List[float]]:
        """Internal async call method."""
        # Call the parent's async method if available
        # If not, call the sync method
        try:
            if hasattr(super(), '__call__'):
                # Check if parent call is async
                result = super().__call__(text, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                else:
                    return result
            else:
                # Fallback to direct API call
                return await self._direct_api_call(text, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Error in fixed embedding call: {str(e)}") from e
    
    async def _direct_api_call(
        self,
        text: Union[str, List[str]],
        **kwargs: Optional[dict],
    ) -> List[List[float]]:
        """Direct API call to OpenAI embedding endpoint."""
        import openai
        
        # Prepare the client
        client_kwargs = getattr(self, 'client_kwargs', {})
        api_key = getattr(self, 'api_key', None)
        
        if api_key:
            client_kwargs['api_key'] = api_key
            
        client = openai.AsyncOpenAI(**client_kwargs)
        
        model_name = getattr(self, 'model_name', 'text-embedding-ada-002')
        
        if isinstance(text, str):
            text = [text]
            
        response = await client.embeddings.create(
            input=text,
            model=model_name,
            **kwargs
        )
        
        return [item.embedding for item in response.data]
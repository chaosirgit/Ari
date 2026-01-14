from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
import requests
from typing import Optional
import config
from config import logger


def _tavily_search_sync(query: str, max_results: int = 5) -> str:
    """
    Synchronous helper function to perform Tavily search and return results as string.

    Args:
        query (str): The search query
        max_results (int): Maximum number of results to return

    Returns:
        str: The search results as a formatted string
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")

    # Get API key from config
    api_key = config.TAVILY_API_KEY
    if not api_key:
        raise ValueError("Tavily API key is required. Ensure config.TAVILY_API_KEY is set.")

    try:
        logger.info(f"Performing Tavily search for query: {query}")

        # Tavily API endpoint
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",  # 可以调整为 "advanced" 如果需要
            "include_answer": True,  # 是否包含 AI 生成的答案
            "max_results": max_results
        }

        response = requests.post(url, json=payload)
        response.raise_for_status()

        # Parse JSON response
        results = response.json()

        # Format results as readable string
        formatted_results = "Tavily Search Results:\n"
        if "answer" in results:
            formatted_results += f"AI Answer: {results['answer']}\n\n"

        for idx, result in enumerate(results.get("results", []), 1):
            formatted_results += f"Result {idx}:\n"
            formatted_results += f"Title: {result.get('title', 'N/A')}\n"
            formatted_results += f"URL: {result.get('url', 'N/A')}\n"
            formatted_results += f"Content: {result.get('content', 'N/A')}\n\n"

        logger.info(f"Successfully performed search for: {query}")
        return formatted_results.strip()

    except requests.RequestException as e:
        logger.error(f"Failed to search with Tavily: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing Tavily search: {e}")
        raise


async def tavily_search(
        query: str,
        max_results: Optional[int] = 5
) -> ToolResponse:
    """Perform a search using Tavily API and return the results.

    Args:
        query (`str`):
            The search query string.
        max_results (`int`, optional):
            Maximum number of results to return. Defaults to 5.

    Returns:
        `ToolResponse`:
            The tool response containing the search results or an error message.
    """
    try:
        if max_results is None:
            max_results = 5

        results = _tavily_search_sync(query, int(max_results))
        return ToolResponse(
            metadata={"status": "success"},
            content=[TextBlock(text=results, type="text")]
        )

    except ValueError as e:
        return ToolResponse(
            metadata={"status": "error"},
            content=[TextBlock(text=f"Invalid parameter: {str(e)}", type="text")]
        )
    except requests.RequestException as e:
        return ToolResponse(
            metadata={"status": "error"},
            content=[TextBlock(text=f"Failed to perform search: {str(e)}", type="text")]
        )
    except Exception as e:
        return ToolResponse(
            metadata={"status": "error"},
            content=[TextBlock(text=f"Unexpected error during search: {str(e)}", type="text")]
        )

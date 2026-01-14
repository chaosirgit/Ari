from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _fetch_web_content_sync(url: str, timeout: int = 10) -> str:
    """
    Synchronous helper function to fetch and extract text content from web page.
    
    Args:
        url (str): The URL to fetch
        timeout (int): Request timeout in seconds
        
    Returns:
        str: The cleaned text content of the web page
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    
    try:
        logger.info(f"Fetching content from: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML and extract text
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        logger.info(f"Successfully fetched content from: {url}")
        return text
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing content from {url}: {e}")
        raise

async def fetch_web_content(
    url: str,
    timeout: Optional[int] = 10
) -> ToolResponse:
    """Fetch and extract text content from a web page.
    
    Args:
        url (`str`):
            The URL to fetch content from.
        timeout (`int`, optional):
            Request timeout in seconds. Defaults to 10.
            
    Returns:
        `ToolResponse`:
            The tool response containing the extracted text content or an error message.
    """
    try:
        if timeout is None:
            timeout = 10
            
        content = _fetch_web_content_sync(url, int(timeout))
        return ToolResponse(
            metadata = {"status": "success"},
            content = [TextBlock(text=content, type="text")]
        )
        
    except ValueError as e:
        return ToolResponse(
            metadata = {"status": "error"},
            content = [TextBlock(text=f"Invalid URL parameter: {str(e)}", type="text")]
        )
    except requests.RequestException as e:
        return ToolResponse(
            metadata = {"status": "error"},
            content = [TextBlock(text=f"Failed to fetch URL '{url}': {str(e)}", type="text")]
        )
    except Exception as e:
        return ToolResponse(
            metadata={"status":"error"},
            content=[TextBlock(text=f"Unexpected error fetching URL '{url}': {str(e)}",type="text")]
        )
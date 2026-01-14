from agentscope.message import TextBlock
from agentscope.tool import ToolResponse, view_text_file
import json
import re
from typing import Union, List, Optional


def _parse_ranges(ranges: Union[List[int], str, None]) -> Optional[List[int]]:
    """Parse ranges parameter from various input formats.
    
    Supports:
    - None: return None (view entire file)
    - List[int]: [1, 100] or [-100, -1]
    - str: "1,100", "1-100", "[1,100]", "[-100,-1]"
    """
    if ranges is None:
        return None
    
    if isinstance(ranges, list):
        if len(ranges) != 2:
            raise ValueError("Ranges list must contain exactly 2 integers")
        return [int(ranges[0]), int(ranges[1])]
    
    if isinstance(ranges, str):        # Remove whitespace
        ranges_clean = ranges.strip()
        
        # Try JSON format first (handles [1,100] and [-100,-1])
        try:
            parsed = json.loads(ranges_clean)
            if isinstance(parsed, list) and len(parsed) == 2:
                return [int(parsed[0]), int(parsed[1])]
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        
        # Try dash format: "1-100"
        if '-' in ranges_clean and ',' not in ranges_clean:
            parts = ranges_clean.split('-')
            if len(parts) == 2:
                try:
                    return [int(parts[0].strip()), int(parts[1].strip())]
                except ValueError:
                    pass
        
        # Try comma format: "1,100"  
        if ',' in ranges_clean:
            parts = ranges_clean.split(',')
            if len(parts) == 2:
                try:
                    return [int(parts[0].strip()), int(parts[1].strip())]
                except ValueError:
                    pass
    
    raise ValueError(f"Unsupported ranges format: {ranges}")


async def ex_view_text_file(
    file_path: str, 
    ranges: Union[List[int], str, None] = None
) -> ToolResponse:
    """View the file content in the specified range with line numbers. If `ranges` is not provided, the entire file will be returned.

    Args:
        file_path (`str`):
            The target file path.
        ranges:
            The range of lines to be viewed. Supports multiple formats:
            - List[int]: [1, 100] (lines 1 to 100 inclusive)
            - str: "1,100", "1-100", "[1,100]", or "[-100,-1]" (last 100 lines)
            - None: view entire file

    Returns:
        `ToolResponse`:
            The tool response containing the file content or an error message.
    """
    try:
        parsed_ranges = _parse_ranges(ranges) if ranges is not None else None
        result = await view_text_file(file_path, parsed_ranges)
        return result
    except ValueError as e:
        return ToolResponse(
            metadata={"status":"error"},
            content=[TextBlock(type="text",text=f"Invalid ranges parameter: {str(e)}")]
        )
    except Exception as e:
        # Let the original tool handle file-related errors
        try:
            result = await view_text_file(file_path, None)
            return result
        except Exception:
            return ToolResponse(
                metadata = {"status": "error"},
                content = [TextBlock(type="text", text=f"Error viewing file '{file_path}': {str(e)}")]
            )
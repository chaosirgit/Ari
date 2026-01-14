from agentscope.message import TextBlock
from agentscope.tool import ToolResponse, write_text_file
import json
import os
from typing import Union, List, Optional


def _parse_ranges(ranges: Union[List[int], str, None]) -> Optional[List[int]]:
    """Parse ranges parameter from various input formats."""
    if ranges is None:
        return None
    
    if isinstance(ranges, list):
        if len(ranges) == 0:
            return None
        return ranges
    
    if isinstance(ranges, str):
        ranges = ranges.strip()
        if not ranges:
            return None
        
        # Try JSON format first
        try:
            parsed = json.loads(ranges)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Try comma-separated format: "1,100" or "1,2,3"
        if ',' in ranges:
            try:
                parts = [int(x.strip()) for x in ranges.split(',')]
                return parts
            except ValueError:
                pass
        
        # Try range format: "1-100"
        if '-' in ranges and ranges.count('-') == 1:
            try:
                start, end = ranges.split('-')
                return [int(start.strip()), int(end.strip())]
            except ValueError:
                pass
    
    raise ValueError(f"Unsupported ranges format: {ranges}")


async def ex_write_text_file(
    file_path: str,
    content: str,
    ranges: Union[List[int], str, None] = None,
) -> ToolResponse:
    """Create/Replace/Overwrite content in a text file. When `ranges` is provided, the content will be replaced in the specified range. Otherwise, the entire file (if exists) will be overwritten.

    Args:
        file_path (`str`):
            The target file path.
        content (`str`):
            The content to be written.
        ranges (`list[int] | str | None`, defaults to `None`):
            The range of lines to be replaced. Supported formats:
            - List: [1, 100]
            - JSON string: "[1, 100]"
            - Range string: "1-100"
            - Comma-separated: "1,100"
            If `None`, the entire file will be overwritten.

    Returns:
        `ToolResponse`:
            The tool response containing the result of the writing operation.
    """
    try:
        parsed_ranges = _parse_ranges(ranges)
        result = await write_text_file(file_path, content, parsed_ranges)
        return result
    except Exception as e:
        return ToolResponse(
            metadata={"status":"error"},
            content=[TextBlock(type="text",text=f"Failed to write file '{file_path}': {str(e)}")]
        )
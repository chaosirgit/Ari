from agentscope.tool import ToolResponse, write_text_file
import json


async def ex_write_text_file(
    file_path: str,
    content: str,
    ranges: None | str | list[int] = None,
) -> ToolResponse:
    """Create/Replace/Overwrite content in a text file. When `ranges` is provided, the content will be replaced in the specified range. Otherwise, the entire file (if exists) will be overwritten.

    Args:
        file_path (`str`):
            The target file path.
        content (`str`):
            The content to be written.
        ranges (`list[int] | None`, defaults to `None`):
            The range of lines to be replaced. If `None`, the entire file will
            be overwritten.

    Returns:
        `ToolResponse`:
            The tool response containing the result of the writing operation.
    """
    if isinstance(ranges, str):
        ranges = json.loads(ranges)
    result = await write_text_file(file_path, content, ranges)
    return result
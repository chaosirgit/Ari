from agentscope.tool import ToolResponse, view_text_file
import json


async def ex_view_text_file(file_path: str, ranges: list[int] | str | None = None) -> ToolResponse:
    """View the file content in the specified range with line numbers. If `ranges` is not provided, the entire file will be returned.

    Args:
        file_path (`str`):
            The target file path.
        ranges:
            The range of lines to be viewed (e.g. lines 1 to 100: [1, 100]), inclusive. If not provided, the entire file will be returned. To view the last 100 lines, use [-100, -1].

    Returns:
        `ToolResponse`:
            The tool response containing the file content or an error message.
    """
    if isinstance(ranges, str):
        ranges = json.loads(ranges)
    result = await view_text_file(file_path, ranges)
    return result
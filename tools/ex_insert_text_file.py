from agentscope.tool import ToolResponse, insert_text_file


async def ex_insert_text_file(
    file_path: str,
    content: str,
    line_number: int | str,
) -> ToolResponse:
    """Insert the content at the specified line number in a text file.

    Args:
        file_path (`str`):
            The target file path.
        content (`str`):
            The content to be inserted.
        line_number (`int`):
            The line number at which the content should be inserted, starting
            from 1. If exceeds the number of lines in the file, it will be
            appended to the end of the file.

    Returns:
        `ToolResponse`:
            The tool response containing the result of the insertion operation.
    """
    if isinstance(line_number, str):
        line_number = int(line_number)
    result = await insert_text_file(file_path, content, line_number)
    return result
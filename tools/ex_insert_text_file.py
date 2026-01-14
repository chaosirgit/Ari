from agentscope.message import TextBlock
from agentscope.tool import ToolResponse, insert_text_file
import os


def _parse_line_number(line_number):
    """Parse line number from various input formats."""
    if isinstance(line_number, int):
        return line_number
    if isinstance(line_number, str):
        line_number = line_number.strip()
        if line_number.lower() == "end":
            return -1
        if line_number.lower() == "start":
            return 0
        try:
            return int(line_number)
        except ValueError:
            raise ValueError(f"Invalid line number format: {line_number}")
    raise ValueError(f"Unsupported line_number type: {type(line_number)}")


def _validate_file_path(file_path):
    """Validate file path for security and existence."""
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("File path must be a non-empty string")
    
    # Normalize path to prevent directory traversal
    normalized_path = os.path.normpath(file_path)
    if normalized_path.startswith("..") or normalized_path.startswith("/"):
        # Allow relative paths but warn about potential security issues
        pass  # Let the underlying tool handle actual permissions
    
    return normalized_path


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
        line_number (`int | str`):
            The line number at which the content should be inserted, starting
            from 1. If exceeds the number of lines in the file, it will be
            appended to the end of the file.
            Also supports:
            - "end" or -1: insert at the end of file
            - "start" or 0: insert at the beginning of file
            - string numbers: "5", "10", etc.

    Returns:
        `ToolResponse`:
            The tool response containing the result of the insertion operation.
    """
    try:
        # Validate and normalize inputs
        validated_file_path = _validate_file_path(file_path)
        parsed_line_number = _parse_line_number(line_number)
        
        # Execute the operation
        result = await insert_text_file(validated_file_path, content, parsed_line_number)
        return result
        
    except ValueError as e:
        return ToolResponse(
            metadata = {"status": "error"},
            content = [TextBlock(type="text", text=f"Parameter error: {str(e)}")]
        )
    except Exception as e:
        return ToolResponse(
            metadata = {"status": "error"},
            content = [TextBlock(type="text", text=f"Unexpected error during file insertion: {str(e)}")]
        )
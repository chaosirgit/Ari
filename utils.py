"""
Utility functions for the Ari project.
"""
import json
from typing import Any


def extract_json_from_response(response_content: Any) -> str:
    """
    从各种格式的响应中提取 JSON 字符串。

    Args:
        response_content: LLM 响应内容（可能是 Sequence, list, dict, str）

    Returns:
        str: 清洗后的 JSON 字符串
    """
    text_content = ""

    # 1. 提取文本内容
    if isinstance(response_content, (list, tuple)):
        # 处理序列格式的响应（Sequence[TextBlock | ...]）
        for item in response_content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    text_content += item.get('text', '')
            elif hasattr(item, 'type') and item.type == 'text':
                # 如果是对象而非字典
                text_content += getattr(item, 'text', '')
    elif isinstance(response_content, dict):
        if response_content.get('type') == 'text':
            text_content = response_content.get('text', '')
        else:
            # 如果已经是字典，可能就是 JSON 数据
            return json.dumps(response_content)
    elif isinstance(response_content, str):
        text_content = response_content
    else:
        text_content = str(response_content)

    # 2. 清洗文本
    text_content = text_content.strip()

    # 3. 移除 Markdown 代码块标记
    if text_content.startswith('```'):
        lines = text_content.split('\n')
        # 移除第一行（```json 或 ```）
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        # 移除最后的 ``` 行
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text_content = '\n'.join(lines)

    return text_content.strip()


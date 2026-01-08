"""
Ari 深色主题配色方案
遵循深色主题的美学配色方案
"""
from textual.theme import Theme


class AriDarkTheme(Theme):
    """Ari 深色主题"""
    
    def __init__(self) -> None:
        super().__init__(
            name="ari_dark",
            # 主要颜色
            primary="#61afef",      # 主要强调色（蓝色）
            secondary="#c678dd",    # 次要强调色（紫色）  
            warning="#e5c07b",      # 警告色（黄色）
            error="#e06c75",        # 错误色（红色）
            success="#98c379",      # 成功色（绿色）
            accent="#56b6c2",       # 强调色（青色）
            
            # 背景色
            background="#282c34",   # 主背景色（深灰蓝）
            surface="#2c323c",      # 表面背景色（稍亮）
            panel="#323844",        # 面板背景色
            
            # 文字颜色
            foreground="#abb2bf",   # 主文字色（浅灰）
            
            # 暗色主题
            dark=True,
            
            # 其他可选参数
            luminosity_spread=0.15,
            text_alpha=0.95,
            
            # 自定义变量（可选）
            variables={
                "border-color": "#4b5263",
                "border-focus-color": "#61afef",
                "disabled-color": "#5c6370"
            }
        )
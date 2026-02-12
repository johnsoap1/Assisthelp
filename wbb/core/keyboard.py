# wbb/core/keyboard.py
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def ikb(rows=None, row_width=2):
    """
    rows: list of dicts for buttons
    Example: [{"text": "Button", "url": "https://..."}]
    """
    if not rows:
        return None
    
    lines = []
    for row in rows:
        if isinstance(row, list):
            line = []
            for button in row:
                btn = InlineKeyboardButton(
                    button.get("text", ""),
                    callback_data=button.get("callback_data"),
                    url=button.get("url"),
                    switch_inline_query=button.get("switch_inline_query"),
                    switch_inline_query_current_chat=button.get("switch_inline_query_current_chat")
                )
                line.append(btn)
            lines.append(line)
        else:
            btn = InlineKeyboardButton(
                row.get("text", ""),
                callback_data=row.get("callback_data"),
                url=row.get("url"),
                switch_inline_query=row.get("switch_inline_query"),
                switch_inline_query_current_chat=row.get("switch_inline_query_current_chat")
            )
            lines.append([btn])
    
    return InlineKeyboardMarkup(lines)

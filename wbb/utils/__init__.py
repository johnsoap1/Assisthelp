# wbb/utils/__init__.py
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def paginate_modules(page_n, module_dict, prefix, chat=None):
    """Create pagination for module list"""
    if not isinstance(page_n, int):
        page_n = int(page_n)

    modules = sorted(
        [
            {"name": key, "text": module_dict[key].__MODULE__}
            for key in module_dict.keys()
        ],
        key=lambda x: x["text"]
    )

    pairs = list(zip(modules[::2], modules[1::2]))
    
    if len(modules) % 2 == 1:
        pairs.append((modules[-1],))

    max_pages = len(pairs)
    
    modulo_page = page_n % max_pages

    buttons = []
    for pair in pairs[modulo_page * 3:(modulo_page + 1) * 3]:
        button_row = []
        for module in pair:
            button_row.append(
                InlineKeyboardButton(
                    module["text"],
                    callback_data=f"{prefix}_module({module['name']})"
                )
            )
        buttons.append(button_row)

    # Navigation buttons
    nav_buttons = []
    if modulo_page > 0:
        nav_buttons.append(
            InlineKeyboardButton("◀️", callback_data=f"{prefix}_prev({modulo_page})")
        )
    nav_buttons.append(
        InlineKeyboardButton("🏠", callback_data=f"{prefix}_home({modulo_page})")
    )
    if modulo_page < max_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton("▶️", callback_data=f"{prefix}_next({modulo_page})")
        )
    
    if nav_buttons:
        buttons.append(nav_buttons)

    return buttons

"""
Text formatting helpers for bot outputs.
"""

def bold(text: str) -> str:
    """Make text bold in Markdown."""
    return f"**{text}**"

def section(title: str, body: dict = None, indent: int = 0) -> str:
    """Create a formatted section with title and body."""
    spaces = " " * indent
    text = f"\n{spaces}{bold(title)}\n"

    if body:
        for key, value in body.items():
            text += f"{spaces}  • {key}: {value}\n"

    return text

# Width constant
w = " "

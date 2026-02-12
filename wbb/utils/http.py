# wbb/utils/http.py
"""HTTP utilities for bot."""
import aiohttp
from typing import Optional, Dict, Any


async def get(url: str, **kwargs) -> Dict[str, Any]:
    """Make GET request."""
    from wbb import aiohttpsession
    
    async with aiohttpsession.get(url, **kwargs) as resp:
        return await resp.json()


async def post(url: str, **kwargs) -> str:
    """Make POST request."""
    from wbb import aiohttpsession
    
    async with aiohttpsession.post(url, **kwargs) as resp:
        return await resp.text()


async def head(url: str, **kwargs) -> aiohttp.ClientResponse:
    """Make HEAD request."""
    from wbb import aiohttpsession
    
    return await aiohttpsession.head(url, **kwargs)

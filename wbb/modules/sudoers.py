# wbb/modules/sudoers.py
import platform
import psutil
import time
from pyrogram import filters
from wbb import app, bot_start_time

@app.on_message(filters.command("stats"))
async def stats(_, message):
    stats_text = await bot_sys_stats()
    await message.reply(stats_text)

async def bot_sys_stats():
    """Get bot system statistics"""
    uptime = time.time() - bot_start_time
    uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime))
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    
    stats = f"""
**System Statistics**

**Uptime:** {uptime_str}
**CPU:** {cpu}%
**RAM:** {ram}%
**Disk:** {disk}%
**Platform:** {platform.system()} {platform.release()}
**Python:** {platform.python_version()}
"""
    return stats

__MODULE__ = "Stats"
__HELP__ = """
**System Statistics**

Get bot system information.

Commands:
- /stats - Show system stats
"""

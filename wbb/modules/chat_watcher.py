"""
Chat Watcher Module - Tracks users and leaves blacklisted chats
"""
from wbb import app
from wbb.utils.dbfunctions import (
    blacklisted_chats,
)
from wbb.utils.filter_groups import chat_watcher_group


@app.on_message(group=chat_watcher_group)
async def chat_watcher_func(_, message):
    """Track users and leave blacklisted chats."""
    try:
        # Track users - automatically handled by chat_members table
        # await add_served_user(user_id)  # Removed - not needed

        chat_id = message.chat.id
        if not chat_id:
            return

        # Check if chat is blacklisted
        blacklisted_chats_list = await blacklisted_chats()
        if chat_id in blacklisted_chats_list:
            # Leave blacklisted chat
            return await app.leave_chat(chat_id)

    except Exception as e:
        # Log errors but don't crash
        print(f"[chat_watcher] Error in chat {message.chat.id}: {e}")

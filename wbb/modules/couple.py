"""
Shipper Module - Enhanced Couple Detection 💖

Features:
- Deterministic love percentage per day
- Themed ship messages based on compatibility
- Anti-self-ship protection
- Reply context support
- Command aliases
- Easter eggs and variety
"""
import random
from datetime import datetime, timedelta

import pytz
from pyrogram import enums, filters

from wbb import app
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import get_couple, save_couple

__MODULE__ = "Shipper 💖"
__HELP__ = """
**Shipper Commands:**
- `/detect_gay` - Choose Couple of the Day 💖
- `/ship` - Ship two random users
- `/couple` - Choose Couple of the Day 💖
- `/love` - Ship two random users

Features:
✅ Deterministic love percentage
✅ Themed messages based on compatibility
✅ Reply context support
✅ Anti-self-ship protection
✅ Easter eggs and variety
"""

# ------------------ Ship Messages ------------------ #
SHIP_MESSAGES = {
    "legendary": [
        "👑 LEGENDARY SHIP — pedo approved.",
        "💍 Wedding bells incoming!",
        "🌟 Pedo connection detected",
        "💎 Gooner level compatibility",
    ],
    "hot": [
        "🔥 This chat can't handle this heat.",
        "💋 Someone's blushing right now.",
        "🌶️ Spicy energy alert!",
        "💘 Hearts racing fast!",
    ],
    "cute": [
        "🥰 Soft launch incoming.",
        "💞 Adorable energy detected.",
        "🌸 Cherry blossom vibes!",
        "🦋 Butterfly feelings!",
    ],
}

EASTER_EGGS = [
    "🤡 This ship was sponsored by chaos.",
    "🚨 I'm gonna cum…",
    "🧿 Two fags!",
    "🎭 Plot twist incoming!",
    "🎪 Circus has arrived!",
]

VIBE_EMOJIS = ["💖", "🔥", "💘", "💞", "❤️‍🔥", "🌹", "✨"]

# ------------------ Love Calculator ------------------ #
def love_percentage(chat_id: int, c1_id: int, c2_id: int) -> int:
    """Calculate deterministic love percentage (50-100%)."""
    seed = f"{chat_id}{c1_id}{c2_id}{today_date()}"
    random.seed(seed)
    return random.randint(50, 100)

# ------------------ Date Utilities ------------------ #
IST = pytz.timezone("Asia/Kolkata")

def today_date():
    return datetime.now(IST).strftime("%d/%m/%Y")

def tomorrow_date():
    return (datetime.now(IST) + timedelta(days=1)).strftime("%d/%m/%Y")

# ------------------ Command Handler ------------------ #
@app.on_message(filters.command(["detect_gay", "ship", "couple", "love"]))
@capture_err
async def couple(_, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        return await message.reply_text("This command only works in groups.")

    m = await message.reply("🔍 Detecting the couple of the day...")

    try:
        chat_id = message.chat.id
        existing_couple = await get_couple(chat_id, today_date())

        if existing_couple:
            # Couple already chosen
            c1_id = int(existing_couple["c1_id"])
            c2_id = int(existing_couple["c2_id"])
            c1_user = await app.get_users(c1_id)
            c2_user = await app.get_users(c2_id)
            c1_name = c1_user.first_name
            c2_name = c2_user.first_name

            message_text = (
                f"💞 **Couple of the Day:**\n"
                f"[{c1_name}](tg://openmessage?user_id={c1_id}) + "
                f"[{c2_name}](tg://openmessage?user_id={c2_id}) = ❤️\n\n"
                f"__New couple can be chosen at 12AM {tomorrow_date()}__"
            )
            return await m.edit(message_text)

        # No couple yet, choose new couple
        try:
            members = [
                member async for member in app.get_chat_members(chat_id)
                if not member.user.is_bot and not member.user.is_deleted
            ]
        except Exception as e:
            print(f"[ERROR] Failed to get chat members for couple detection in chat {chat_id}: {e}")
            return await m.edit("❌ Could not access chat members for couple detection.")

        if len(members) < 2:
            return await m.edit("❌ Not enough eligible users to choose a couple.")

        # Reply context support
        if message.reply_to_message and message.reply_to_message.from_user:
            c1_user = message.reply_to_message.from_user
            others = [m for m in members if m.user.id != c1_user.id]
            if not others:
                return await m.edit("❌ Not enough other users to ship with.")
            c2_user = random.choice(others).user
        else:
            # Anti-self-ship protection
            while True:
                c1_user, c2_user = random.sample(members, 2)
                if c1_user.user.id != c2_user.user.id:
                    break

        c1_mention = c1_user.user.mention
        c2_mention = c2_user.user.mention

        # Calculate love percentage
        percent = love_percentage(chat_id, c1_user.user.id, c2_user.user.id)
        
        # Choose themed message based on percentage
        if random.randint(1, 50) == 1:  # 1-in-50 easter egg
            fun_msg = random.choice(EASTER_EGGS)
        elif percent > 90:
            fun_msg = random.choice(SHIP_MESSAGES["legendary"])
        elif percent > 75:
            fun_msg = random.choice(SHIP_MESSAGES["hot"])
        else:
            fun_msg = random.choice(SHIP_MESSAGES["cute"])
        
        # Random vibe emoji
        emoji = random.choice(VIBE_EMOJIS)

        couple_text = (
            f"{emoji} **Couple of the Day** {emoji}\n"
            f"{c1_mention} + {c2_mention} = ❤️\n\n"
            f"💘 **Love Meter:** `{percent}%`\n"
            f"{fun_msg}\n"
            f"__New couple at 12AM {tomorrow_date()}__"
        )
        await m.edit(couple_text)

        # Save selected couple
        await save_couple(chat_id, today_date(), {
            "c1_id": c1_user.user.id,
            "c2_id": c2_user.user.id
        })

    except Exception as e:
        print(f"[ERROR] /detect_gay: {e}")
        await m.edit("❌ Something went wrong while detecting the couple.")

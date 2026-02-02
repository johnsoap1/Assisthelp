"""
Premium Karma System with Leaderboards, Titles, and Achievements
"""
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pyrogram import filters
from pyrogram.types import Message

from wbb import app
from wbb.core.decorators.errors import capture_err
from wbb.core.decorators.permissions import adminsOnly
from wbb.core.sections import section
from wbb.utils.dbfunctions import (
    alpha_to_int,
    get_karma,
    get_karmas,
    int_to_alpha,
    is_karma_on,
    karma_off,
    karma_on,
    update_karma,
)
from wbb.utils.filter_groups import karma_negative_group, karma_positive_group
from wbb.utils.functions import get_specific_usernames

__MODULE__ = "Premium Karma"
__HELP__ = """**Premium Karma System**

**Voting:**
• Reply with: +, +1, thanks, thankyou, thank you, agree, pro, cool, good, nice, awesome, great, excellent, brilliant, amazing, perfect, 👍
• Reply with: -, -1, disagree, bad, worst, not cool, terrible, awful, poor, 👎

**Commands:**
• `/karma` - Check karma leaderboard (top 15 users)
• `/karma` (reply) - Check specific user's karma
• `/mykarma` - Check your own karma stats
• `/karma_stats` - Detailed chat karma statistics
• `/karma_rank` - Check your rank in the chat
• `/karma_title` - Check available titles
• `/karma_history` - View recent karma changes (last 10)
• `/karma_top` [day/week/month] - Top gainers in time period
• `/karma_reset @username` - Reset user's karma (Admin only)
• `/karma_set @username [amount]` - Set user's karma (Admin only)
• `/karma_toggle [ENABLE|DISABLE]` - Toggle karma system

**Titles System:**
Earn prestigious titles based on your karma:
• 🌟 Legendary Pedo (1000+)
• 💎 Diamond Gooner (750+)
• 👑 Elite Pedo (500+)
• ⭐ Premium Pedo (300+)
• 🔥 Master Bater(150+)
• ✨ Rising Pedo (75+)
• 🎯 Jorker (30+)
• 🌱 Gooner (1+)
• ⚫ No Title (0)
• ⚠️ Controversial (<0)

**Achievements:**
• 🎖️ First Vote - Cast your first vote
• 🏆 Top 10 - Enter top 10 leaderboard
• 💯 Century - Reach 100 karma
• 🔮 Mystical Gooner- Reach 500 karma
• 👹 Dark Lord - Reach -100 karma
"""

# Extended regex patterns for more expressions
regex_upvote = r"^(\+{1,3}|\+1|thx|tnx|tq|ty|thankyou|thank you|thanx|thanks|pro|cool|good|nice|agree|agreed|i agree|based|awesome|great|excellent|brilliant|amazing|perfect|👍|\+\+ .+)$"
regex_downvote = r"^(-{1,3}|-1|not cool|disagree|i disagree|i dont agree|i don't agree|worst|bad|terrible|awful|poor|cringe|👎|-+ .+)$"


# Title system
TITLES = {
    1000: "🌟 Legendary Pedo",
    750: "💎 Diamond Gooner",
    500: "👑 Premium Pedo",
    300: "⭐ Master",
    150: "🔥 Master Bater",
    75: "✨ Rising Pedo",
    30: "🎯 Jorker",
    1: "🌱 Gooner",
    0: "⚫ Faggot",
    -999: "⚠️ Controversial"
}


def get_title(karma: int) -> str:
    """Get title based on karma points"""
    for threshold in sorted(TITLES.keys(), reverse=True):
        if karma >= threshold:
            return TITLES[threshold]
    return TITLES[-999]


def get_rank_emoji(rank: int) -> str:
    """Get emoji for rank position"""
    rank_emojis = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }
    return rank_emojis.get(rank, f"#{rank}")


async def get_user_rank(chat_id: int, user_id: int) -> Optional[int]:
    """Get user's rank in the chat"""
    try:
        karma = await get_karmas(chat_id)
        if not karma:
            return None
        
        karma_list = []
        for i in karma:
            try:
                uid = await alpha_to_int(i)
                user_karma = karma[i]["karma"]
                karma_list.append((uid, user_karma))
            except:
                continue
        
        karma_list.sort(key=lambda x: x[1], reverse=True)
        
        for idx, (uid, _) in enumerate(karma_list, 1):
            if uid == user_id:
                return idx
        return None
    except:
        return None


async def log_karma_change(chat_id: int, user_id: int, change: int, by_user_id: int):
    """Log karma changes for history tracking"""
    try:
        history_key = f"karma_history_{chat_id}"
        history = await get_karma(chat_id, history_key) or {"history": []}
        
        entry = {
            "user_id": user_id,
            "change": change,
            "by_user_id": by_user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        history_list = history.get("history", [])
        history_list.insert(0, entry)
        history_list = history_list[:50]  # Keep last 50 entries
        
        await update_karma(chat_id, history_key, {"history": history_list})
    except:
        pass


@app.on_message(
    filters.text
    & filters.group
    & filters.incoming
    & filters.reply
    & filters.regex(regex_upvote, re.IGNORECASE)
    & ~filters.via_bot
    & ~filters.bot,
    group=karma_positive_group,
)
@capture_err
async def upvote(_, message: Message):
    if not await is_karma_on(message.chat.id):
        return
    if not message.reply_to_message.from_user:
        return
    if not message.from_user:
        return
    if message.reply_to_message.from_user.id == message.from_user.id:
        return await message.reply_text("❌ You cannot vote for yourself!")
    
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    voter_id = message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    
    # Get current karma
    current_karma = await get_karma(chat_id, await int_to_alpha(user_id))
    if current_karma:
        karma = current_karma["karma"] + 1
    else:
        karma = 1
    
    # Update karma
    await update_karma(chat_id, await int_to_alpha(user_id), {"karma": karma})
    
    # Log the change
    await log_karma_change(chat_id, user_id, 1, voter_id)
    
    # Get title and rank
    title = get_title(karma)
    rank = await get_user_rank(chat_id, user_id)
    rank_text = f"Rank: {get_rank_emoji(rank)}" if rank and rank <= 10 else f"Rank: #{rank}" if rank else ""
    
    # Check for achievements
    achievements = []
    if karma == 1:
        achievements.append("🎖️ First Karma!")
    elif karma == 100:
        achievements.append("💯 Century Club!")
    elif karma == 500:
        achievements.append("🔮 Mystic Achievement!")
    elif karma == 1000:
        achievements.append("🌟 Legendary Status!")
    
    response = f"⬆️ **Karma Increased!**\n\n"
    response += f"👤 {user_mention}\n"
    response += f"📊 **Points:** {karma} (+1)\n"
    response += f"🏅 **Title:** {title}\n"
    if rank_text:
        response += f"🎯 {rank_text}\n"
    if achievements:
        response += f"\n✨ {' '.join(achievements)}"
    
    await message.reply_text(response)


@app.on_message(
    filters.text
    & filters.group
    & filters.incoming
    & filters.reply
    & filters.regex(regex_downvote, re.IGNORECASE)
    & ~filters.via_bot
    & ~filters.bot,
    group=karma_negative_group,
)
@capture_err
async def downvote(_, message: Message):
    if not await is_karma_on(message.chat.id):
        return
    if not message.reply_to_message.from_user:
        return
    if not message.from_user:
        return
    if message.reply_to_message.from_user.id == message.from_user.id:
        return await message.reply_text("❌ You cannot vote for yourself!")
    
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    voter_id = message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    
    # Get current karma
    current_karma = await get_karma(chat_id, await int_to_alpha(user_id))
    if current_karma:
        karma = current_karma["karma"] - 1
    else:
        karma = -1
    
    # Update karma
    await update_karma(chat_id, await int_to_alpha(user_id), {"karma": karma})
    
    # Log the change
    await log_karma_change(chat_id, user_id, -1, voter_id)
    
    # Get title and rank
    title = get_title(karma)
    rank = await get_user_rank(chat_id, user_id)
    rank_text = f"Rank: {get_rank_emoji(rank)}" if rank and rank <= 10 else f"Rank: #{rank}" if rank else ""
    
    # Check for negative achievements
    achievements = []
    if karma == -100:
        achievements.append("👹 Dark Lord!")
    
    response = f"⬇️ **Karma Decreased!**\n\n"
    response += f"👤 {user_mention}\n"
    response += f"📊 **Points:** {karma} (-1)\n"
    response += f"🏅 **Title:** {title}\n"
    if rank_text:
        response += f"🎯 {rank_text}\n"
    if achievements:
        response += f"\n✨ {' '.join(achievements)}"
    
    await message.reply_text(response)


@app.on_message(filters.command("karma") & filters.group)
@capture_err
async def command_karma(_, message: Message):
    chat_id = message.chat.id
    
    if not message.reply_to_message:
        m = await message.reply_text("📊 Analyzing Karma Leaderboard...")
        
        try:
            karma = await get_karmas(chat_id)
            if not karma:
                return await m.edit("📭 No karma data available for this chat.")
            
            karma_dicc = {}
            for i in karma:
                if i.startswith("karma_history"):
                    continue
                try:
                    user_id = await alpha_to_int(i)
                    user_karma = karma[i]["karma"]
                    karma_dicc[str(user_id)] = user_karma
                except Exception as e:
                    print(f"[KARMA] Error processing user {i}: {e}")
                    continue
            
            if not karma_dicc:
                return await m.edit("📭 No karma data available for this chat.")
            
            karma_sorted = sorted(
                karma_dicc.items(),
                key=lambda item: item[1],
                reverse=True
            )
            
            leaderboard = "🏆 **KARMA LEADERBOARD** 🏆\n\n"
            
            displayed = 0
            for idx, (user_id_str, karma_count) in enumerate(karma_sorted[:15], 1):
                user_id_int = int(user_id_str)
                
                # Try to get user info directly from Telegram
                try:
                    user = await app.get_users(user_id_int)
                    if user.username:
                        display_name = f"@{user.username}"
                    elif user.first_name:
                        display_name = user.first_name
                    else:
                        display_name = f"User {user_id_int}"
                except:
                    display_name = f"User {user_id_int}"
                
                title = get_title(karma_count)
                rank_emoji = get_rank_emoji(idx)
                
                leaderboard += f"{rank_emoji} **{display_name}**\n"
                leaderboard += f"   ├ 📊 Points: **{karma_count}**\n"
                leaderboard += f"   └ 🏅 {title}\n\n"
                displayed += 1
            
            if displayed == 0:
                return await m.edit("📭 No valid users found with karma.")
            
            leaderboard += f"💬 Chat: **{message.chat.title}**\n"
            leaderboard += f"👥 Total Users: **{len(karma_dicc)}**"
            
            await m.edit(leaderboard)
            
        except Exception as e:
            print(f"[KARMA] Leaderboard error: {e}")
            import traceback
            traceback.print_exc()
            await m.edit(f"❌ Error: {str(e)}")
    
    else:
        if not message.reply_to_message.from_user:
            return await message.reply_text("❌ Anonymous users have no karma.")
        
        user_id = message.reply_to_message.from_user.id
        user_mention = message.reply_to_message.from_user.mention
        
        try:
            karma_data = await get_karma(chat_id, await int_to_alpha(user_id))
            karma_value = karma_data["karma"] if karma_data else 0
            title = get_title(karma_value)
            rank = await get_user_rank(chat_id, user_id)
            
            response = f"📊 **Karma Profile**\n\n"
            response += f"👤 {user_mention}\n"
            response += f"📈 **Points:** {karma_value}\n"
            response += f"🏅 **Title:** {title}\n"
            if rank:
                response += f"🎯 **Rank:** {get_rank_emoji(rank) if rank <= 3 else f'#{rank}'}"
            
            await message.reply_text(response)
        except Exception as e:
            await message.reply_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command("mykarma") & filters.group)
@capture_err
async def my_karma(_, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    try:
        karma_data = await get_karma(chat_id, await int_to_alpha(user_id))
        karma_value = karma_data["karma"] if karma_data else 0
        title = get_title(karma_value)
        rank = await get_user_rank(chat_id, user_id)
        
        # Calculate next title threshold
        next_threshold = None
        for threshold in sorted(TITLES.keys(), reverse=True):
            if karma_value < threshold:
                next_threshold = threshold
        
        response = f"📊 **Your Karma Profile**\n\n"
        response += f"👤 {user_mention}\n"
        response += f"📈 **Points:** {karma_value}\n"
        response += f"🏅 **Title:** {title}\n"
        if rank:
            response += f"🎯 **Rank:** {get_rank_emoji(rank) if rank <= 3 else f'#{rank}'}\n"
        if next_threshold:
            points_needed = next_threshold - karma_value
            response += f"\n🎯 **Next Title:** {TITLES[next_threshold]}\n"
            response += f"📍 **Points Needed:** {points_needed}"
        
        await message.reply_text(response)
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command("karma_stats") & filters.group)
@capture_err
async def karma_stats(_, message: Message):
    chat_id = message.chat.id
    m = await message.reply_text("📊 Calculating statistics...")
    
    try:
        karma = await get_karmas(chat_id)
        if not karma:
            return await m.edit("📭 No karma data available.")
        
        total_users = 0
        total_karma = 0
        positive_karma = 0
        negative_karma = 0
        max_karma = float('-inf')
        min_karma = float('inf')
        
        for i in karma:
            if i.startswith("karma_history"):
                continue
            try:
                user_karma = karma[i]["karma"]
                total_users += 1
                total_karma += user_karma
                if user_karma > 0:
                    positive_karma += 1
                elif user_karma < 0:
                    negative_karma += 1
                max_karma = max(max_karma, user_karma)
                min_karma = min(min_karma, user_karma)
            except:
                continue
        
        avg_karma = total_karma / total_users if total_users > 0 else 0
        neutral_karma = total_users - positive_karma - negative_karma
        
        stats = f"📊 **KARMA STATISTICS**\n\n"
        stats += f"💬 **Chat:** {message.chat.title}\n\n"
        stats += f"👥 **Total Users:** {total_users}\n"
        stats += f"📈 **Total Karma:** {total_karma}\n"
        stats += f"📊 **Average Karma:** {avg_karma:.1f}\n\n"
        stats += f"✅ **Positive Users:** {positive_karma}\n"
        stats += f"⚫ **Neutral Users:** {neutral_karma}\n"
        stats += f"❌ **Negative Users:** {negative_karma}\n\n"
        stats += f"🔝 **Highest Karma:** {max_karma}\n"
        stats += f"🔻 **Lowest Karma:** {min_karma}"
        
        await m.edit(stats)
    except Exception as e:
        await m.edit(f"❌ Error: {str(e)}")


@app.on_message(filters.command("karma_rank") & filters.group)
@capture_err
async def karma_rank(_, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    try:
        rank = await get_user_rank(chat_id, user_id)
        karma_data = await get_karma(chat_id, await int_to_alpha(user_id))
        karma_value = karma_data["karma"] if karma_data else 0
        
        if not rank:
            return await message.reply_text("❌ You don't have any karma yet!")
        
        # Get total users
        karma = await get_karmas(chat_id)
        total_users = sum(1 for k in karma if not k.startswith("karma_history"))
        
        response = f"🎯 **Your Ranking**\n\n"
        response += f"👤 {user_mention}\n"
        response += f"📊 **Karma:** {karma_value}\n"
        response += f"🏆 **Rank:** {get_rank_emoji(rank) if rank <= 3 else f'#{rank}'}\n"
        response += f"👥 **Out of:** {total_users} users\n"
        response += f"📈 **Top {(rank/total_users*100):.1f}%**"
        
        await message.reply_text(response)
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command("karma_title") & filters.group)
@capture_err
async def karma_title(_, message: Message):
    titles_text = "🏅 **KARMA TITLES**\n\n"
    
    for threshold in sorted(TITLES.keys(), reverse=True):
        if threshold == -999:
            titles_text += f"{TITLES[threshold]} - Below 0\n"
        else:
            titles_text += f"{TITLES[threshold]} - {threshold}+ points\n"
    
    titles_text += "\n💡 Keep earning karma to unlock higher titles!"
    
    await message.reply_text(titles_text)


@app.on_message(filters.command(["karma_reset"]) & filters.group)
@adminsOnly("can_change_info")
@capture_err
async def karma_reset(_, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a user's message to reset their karma.")
    
    if not message.reply_to_message.from_user:
        return await message.reply_text("❌ Cannot reset karma for anonymous users.")
    
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    
    await update_karma(chat_id, await int_to_alpha(user_id), {"karma": 0})
    await message.reply_text(f"✅ Reset karma for {user_mention} to 0.")


@app.on_message(filters.command(["karma_set"]) & filters.group)
@adminsOnly("can_change_info")
@capture_err
async def karma_set(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/karma_set [amount]` (reply to a user)")
    
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a user's message.")
    
    if not message.reply_to_message.from_user:
        return await message.reply_text("❌ Cannot set karma for anonymous users.")
    
    try:
        amount = int(message.command[1])
    except ValueError:
        return await message.reply_text("❌ Please provide a valid number.")
    
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    user_mention = message.reply_to_message.from_user.mention
    
    await update_karma(chat_id, await int_to_alpha(user_id), {"karma": amount})
    title = get_title(amount)
    
    await message.reply_text(
        f"✅ Set karma for {user_mention}\n"
        f"📊 **New Points:** {amount}\n"
        f"🏅 **Title:** {title}"
    )


@app.on_message(filters.command("karma_toggle") & ~filters.private)
@adminsOnly("can_change_info")
@capture_err
async def karma_toggle(_, message: Message):
    usage = "**Usage:**\n/karma_toggle [ENABLE|DISABLE]"
    if len(message.command) != 2:
        return await message.reply_text(usage)
    
    chat_id = message.chat.id
    state = message.command[1].lower()
    
    if state == "enable":
        await karma_on(chat_id)
        await message.reply_text("✅ **Karma System Enabled**\n\nUsers can now give and receive karma!")
    elif state == "disable":
        await karma_off(chat_id)
        await message.reply_text("❌ **Karma System Disabled**\n\nKarma voting is now disabled.")
    else:
        await message.reply_text(usage)

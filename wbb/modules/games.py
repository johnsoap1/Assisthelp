import asyncio
import random
from datetime import datetime, timedelta
from pytz import timezone

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

from wbb import SUDOERS_SET, app, BOT_ID

# Custom filter to ignore bot's own messages
def is_not_bot(_, __, message: Message) -> bool:
    return message.from_user is not None and message.from_user.id != BOT_ID

# Create filter instance
not_bot = filters.create(is_not_bot)

"""
Games Module - Fixed Version

Key Fixes:
- Fixed spamming issues by adding proper return statements
- Resolved async errors with track_game_stat function
- Improved filter handling for both groups and private chats
"""

__MODULE__ = "Games & Shipper "
__HELP__ = """
 **Telegram Games & Dice**

**Dice Commands:**
- `/dice` - Roll a dice 
- `/dart` - Throw a dart 
- `/basketball` - Shoot a basketball 
- `/football` - Kick a football 
- `/bowling` - Bowl a ball 
- `/slot` - Spin slot machine 

**Interactive Games:**
- `/rps` - Rock Paper Scissors game
- `/coinflip` - Flip a coin
- `/8ball <question>` - Magic 8-ball
- `/lucky` - Test your luck (1-100)
- `/spin` - Spin the wheel of fortune

**Shipper Commands:**
- `/detect_gay` - Ship two random users
- `/ship` - Ship two random users
- `/couple` - Ship two random users
- `/love` - Ship two random users
- `/gamestats` - Show your game statistics
- `/leaderboard` - Show top players

**Multiplayer:**
- `/challenge @user <game>` - Challenge someone (reply to their message)
- Accept/Decline via buttons

**Game Stats:**
- `/gamestats` - View your game statistics
- `/leaderboard` - View top players

**Features:**
✅ All Telegram native dice/emojis
✅ Interactive games with buttons
✅ Multiplayer challenges
✅ Statistics tracking
✅ Sudo users always win dice rolls 🎲6️⃣
"""

# Store active challenges and stats (in-memory)
active_challenges = {}
game_stats = {}

# Dice emoji mapping
DICE_EMOJIS = {
    "dice": "🎲",
    "dart": "🎯",
    "basketball": "🏀",
    "football": "⚽",
    "bowling": "🎳",
    "slot": "🎰"
}

# Game results for slots
SLOT_VALUES = {
    1: "BAR BAR BAR",
    2: "GRAPE GRAPE GRAPE",
    3: "LEMON LEMON LEMON",
    4: "SEVEN SEVEN SEVEN (Jackpot!)",
    22: "BAR BAR GRAPE",
    43: "BAR BAR LEMON",
    64: "BAR BAR SEVEN (Big Win!)"
}

# ============= HELPER FUNCTIONS =============

def track_game_stat(user_id: int, game: str, value: int):
    """Track game statistics (synchronous - NO AWAIT)."""
    if user_id not in game_stats:
        game_stats[user_id] = {}
    
    if game not in game_stats[user_id]:
        game_stats[user_id][game] = {"count": 0, "total": 0, "best": 0}
    
    game_stats[user_id][game]["count"] += 1
    game_stats[user_id][game]["total"] += value
    game_stats[user_id][game]["best"] = max(game_stats[user_id][game]["best"], value)


# ============= DICE GAMES =============

# Cooldown tracking to prevent spam
last_command = {}
COOLDOWN = 2  # seconds

@app.on_message(filters.command("dice") & not_bot)
async def throw_dice(client, message: Message):
    """Roll a dice - Sudo users always get 6."""
    # Delete the command message to prevent processing it again
    try:
        await message.delete()
    except:
        pass
        
    if not message.from_user:
        return
    
    # Check cooldown
    user_id = message.from_user.id
    current_time = time.time()
    if user_id in last_command and (current_time - last_command[user_id]) < COOLDOWN:
        return
    last_command[user_id] = current_time
    
    is_sudo = user_id in SUDOERS_SET
    c = message.chat.id
    
    if not is_sudo:
        # Normal user - just send once and return
        m = await client.send_dice(c, "🎲")
        track_game_stat(user_id, "dice", m.dice.value)
        return
    
    # Sudo user - keep rolling until 6
    m = await client.send_dice(c, "🎲")
    attempts = 0
    while m.dice.value != 6 and attempts < 20:
        await asyncio.sleep(0.5)
        try:
            await m.delete()
        except:
            pass
        m = await client.send_dice(c, "🎲")
        attempts += 1
    
    track_game_stat(user_id, "dice", m.dice.value)


@app.on_message(filters.command("dart") & not_bot)
async def throw_dart(client, message: Message):
    """Throw a dart - Sudo users always hit bullseye."""
    # Delete the command message to prevent processing it again
    try:
        await message.delete()
    except:
        pass
        
    if not message.from_user:
        return
    
    # Check cooldown
    user_id = message.from_user.id
    current_time = time.time()
    if user_id in last_command and (current_time - last_command[user_id]) < COOLDOWN:
        return
    last_command[user_id] = current_time
    
    is_sudo = user_id in SUDOERS_SET
    c = message.chat.id
    
    if not is_sudo:
        # Normal user - just send once and return
        m = await client.send_dice(c, "🎯")
        track_game_stat(user_id, "dart", m.dice.value)
        return
    
    # Sudo user - keep rolling until bullseye (6)
    m = await client.send_dice(c, "🎯")
    attempts = 0
    while m.dice.value != 6 and attempts < 20:
        await asyncio.sleep(0.5)
        try:
            await m.delete()
        except:
            pass
        m = await client.send_dice(c, "🎯")
        attempts += 1
    
    track_game_stat(user_id, "dart", m.dice.value)


@app.on_message(filters.command("basketball") & not_bot)
async def shoot_basketball(client, message: Message):
    """Shoot a basketball - Sudo users always score."""
    # Delete the command message to prevent processing it again
    try:
        await message.delete()
    except:
        pass
        
    if not message.from_user:
        return
    
    is_sudo = message.from_user.id in SUDOERS_SET
    c = message.chat.id
    
    if not is_sudo:
        # Normal user - just send once and return
        m = await client.send_dice(c, "🏀")
        track_game_stat(message.from_user.id, "basketball", m.dice.value)
        return  # CRITICAL: Stop here
    
    # Sudo user - keep trying until score (4 or 5)
    m = await client.send_dice(c, "🏀")
    attempts = 0
    while m.dice.value < 4 and attempts < 20:
        await asyncio.sleep(0.5)
        try:
            await m.delete()
        except:
            pass
        m = await client.send_dice(c, "🏀")
        attempts += 1
    
    track_game_stat(message.from_user.id, "basketball", m.dice.value)


@app.on_message(filters.command("football") & not_bot)
async def kick_football(client, message: Message):
    """Kick a football - Sudo users always score."""
    if not message.from_user:
        return
    
    is_sudo = message.from_user.id in SUDOERS_SET
    c = message.chat.id
    
    if not is_sudo:
        # Normal user - just send once and return
        m = await client.send_dice(c, "⚽")
        track_game_stat(message.from_user.id, "football", m.dice.value)
        return  # CRITICAL: Stop here
    
    # Sudo user - keep trying until goal (3-5)
    m = await client.send_dice(c, "⚽")
    attempts = 0
    while m.dice.value < 3 and attempts < 20:
        await asyncio.sleep(0.5)
        try:
            await m.delete()
        except:
            pass
        m = await client.send_dice(c, "⚽")
        attempts += 1
    
    track_game_stat(message.from_user.id, "football", m.dice.value)


@app.on_message(filters.command("bowling") & not_bot)
async def bowl_ball(client, message: Message):
    """Bowl a ball - Sudo users always get strike."""
    if not message.from_user:
        return
    
    is_sudo = message.from_user.id in SUDOERS_SET
    c = message.chat.id
    
    if not is_sudo:
        # Normal user - just send once and return
        m = await client.send_dice(c, "🎳")
        track_game_stat(message.from_user.id, "bowling", m.dice.value)
        return  # CRITICAL: Stop here
    
    # Sudo user - keep trying until strike (6)
    m = await client.send_dice(c, "🎳")
    attempts = 0
    while m.dice.value != 6 and attempts < 20:
        await asyncio.sleep(0.5)
        try:
            await m.delete()
        except:
            pass
        m = await client.send_dice(c, "🎳")
        attempts += 1
    
    track_game_stat(message.from_user.id, "bowling", m.dice.value)


@app.on_message(filters.command("slot") & not_bot)
async def spin_slot(client, message: Message):
    """Spin slot machine - Sudo users always win jackpot."""
    # Delete the command message to prevent processing it again
    try:
        await message.delete()
    except:
        pass
        
    if not message.from_user:
        return
        
    # Check cooldown
    user_id = message.from_user.id
    current_time = time.time()
    if user_id in last_command and (current_time - last_command[user_id]) < COOLDOWN:
        return
    last_command[user_id] = current_time
    
    is_sudo = user_id in SUDOERS_SET
    c = message.chat.id
    
    if not is_sudo:
        # Normal user - send once
        m = await client.send_dice(c, "🎰")
        track_game_stat(user_id, "slot", m.dice.value)
        
        # Wait for slot animation to complete (slots take ~3 seconds)
        await asyncio.sleep(3)
        
        # Now show result
        result = SLOT_VALUES.get(m.dice.value, "No win this time 😔")
        await message.reply_text(f"🎰 **Result:** {result}")
        return  # CRITICAL: Stop here
    
    # Sudo user - keep trying until jackpot (64)
    m = await client.send_dice(c, "🎰")
    attempts = 0
    while m.dice.value != 64 and attempts < 30:
        await asyncio.sleep(3.5)  # Wait for full animation
        try:
            await m.delete()
        except:
            pass
        m = await client.send_dice(c, "🎰")
        attempts += 1
    
    await asyncio.sleep(3)
    await message.reply_text(f"🎰 **Result:** {SLOT_VALUES.get(m.dice.value, 'Jackpot! 🎉')}")
    track_game_stat(user_id, "slot", m.dice.value)


# ============= INTERACTIVE GAMES =============

@app.on_message(filters.command("rps") & not_bot)
async def rock_paper_scissors(client, message: Message):
    """Play Rock Paper Scissors."""
    if not message.from_user:
        return
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🪨 Rock", callback_data="rps_rock"),
            InlineKeyboardButton("📄 Paper", callback_data="rps_paper"),
            InlineKeyboardButton("✂️ Scissors", callback_data="rps_scissors")
        ]
    ])
    
    await message.reply_text(
        "🎮 **Rock Paper Scissors**\n\n"
        "Choose your move:",
        reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(r"^rps_"))
async def rps_callback(client, callback: CallbackQuery):
    """Handle RPS game callback."""
    if not callback.from_user or callback.from_user.id == BOT_ID:
        return
    
    choice = callback.data.split("_")[1]
    choices = ["rock", "paper", "scissors"]
    bot_choice = random.choice(choices)
    
    emoji_map = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
    
    # Determine winner
    if choice == bot_choice:
        result = "🤝 **It's a tie!**"
        track_game_stat(callback.from_user.id, "rps_tie", 1)
    elif (choice == "rock" and bot_choice == "scissors") or \
         (choice == "paper" and bot_choice == "rock") or \
         (choice == "scissors" and bot_choice == "paper"):
        result = "🎉 **You win!**"
        track_game_stat(callback.from_user.id, "rps_win", 1)
    else:
        result = "😢 **You lose!**"
        track_game_stat(callback.from_user.id, "rps_lose", 1)
    
    try:
        await callback.message.edit_text(
            f"🎮 **Rock Paper Scissors**\n\n"
            f"You chose: {emoji_map[choice]}\n"
            f"I chose: {emoji_map[bot_choice]}\n\n"
            f"{result}"
        )
    except MessageNotModified:
        pass
    
    await callback.answer()


@app.on_message(filters.command("coinflip") & not_bot)
async def coin_flip(client, message: Message):
    """Flip a coin."""
    if not message.from_user:
        return
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟡 Heads", callback_data="coin_heads"),
            InlineKeyboardButton("⚪️ Tails", callback_data="coin_tails")
        ]
    ])
    
    await message.reply_text(
        "🪙 **Coin Flip**\n\n"
        "Call it!",
        reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(r"^coin_"))
async def coin_callback(client, callback: CallbackQuery):
    """Handle coin flip callback."""
    if not callback.from_user or callback.from_user.id == BOT_ID:
        return
    
    choice = callback.data.split("_")[1]
    result = random.choice(["heads", "tails"])
    
    if choice == result:
        outcome = "🎉 **You guessed right!**"
        track_game_stat(callback.from_user.id, "coinflip_win", 1)
    else:
        outcome = "❌ **Wrong guess!**"
        track_game_stat(callback.from_user.id, "coinflip_lose", 1)
    
    try:
        await callback.message.edit_text(
            f"🪙 **Coin Flip**\n\n"
            f"You chose: {choice.title()}\n"
            f"Result: **{result.title()}**\n\n"
            f"{outcome}"
        )
    except MessageNotModified:
        pass
    
    await callback.answer()


@app.on_message(filters.command("8ball") & not_bot)
async def magic_8ball(client, message: Message):
    """Magic 8-ball answers with equal positive/neutral/negative responses."""
    # Delete the command message to prevent processing it again
    try:
        await message.delete()
    except:
        pass
        
    if not message.from_user:
        return
    
    if len(message.command) < 2:
        return await message.reply_text(
            "🔮 **Magic 8-Ball**\n\n"
            "Ask me a yes/no question!\n"
            "Example: `/8ball Will I win the lottery?`"
        )
    
    question = message.text.split(None, 1)[1]
    
    # Positive responses
    positive = [
        "🟢 Yes, definitely!",
        "🟢 It is certain.",
        "🟢 Without a doubt.",
        "🟢 Yes, absolutely!",
        "🟢 You may rely on it.",
        "🟢 Definitely yes!",
        "🟢 For sure!",
        "🟢 Absolutely, yes!",
        "🟢 It's a sure thing!",
        "🟢 No doubt about it!",
        "🟢 You can count on it!",
        "🟢 It's looking good!",
        "🟢 Most certainly!",
        "🟢 Indubitably!",
        "🟢 You bet!"
    ]
    
    # Neutral responses
    neutral = [
        "🟡 Reply hazy, try again.",
        "🟡 Ask again later.",
        "🟡 Better not tell you now.",
        "🟡 Cannot predict now.",
        "🟡 Concentrate and ask again.",
        "🟡 The future is unclear.",
        "🟡 It's uncertain.",
        "🟡 I can't say for sure.",
        "🟡 The signs are mixed.",
        "🟡 It could go either way.",
        "🟡 The answer is unclear.",
        "🟡 The stars don't say.",
        "🟡 The outlook is hazy.",
        "🟡 I need more information.",
        "🟡 The answer is not clear."
    ]
    
    # Negative responses
    negative = [
        "🔴 Don't count on it.",
        "🔴 My reply is no.",
        "🔴 My sources say no.",
        "🔴 Outlook not so good.",
        "🔴 Very doubtful.",
        "🔴 Not likely.",
        "🔴 I don't think so.",
        "🔴 The signs say no.",
        "🔴 It's not looking good.",
        "🔴 I wouldn't bet on it.",
        "🔴 That seems unlikely.",
        "🔴 The answer is no.",
        "🔴 I have my doubts.",
        "🔴 The odds are against it.",
        "🔴 Chances are slim."
    ]
    
    # Combine all responses for equal distribution
    all_responses = positive + neutral + negative
    answer = random.choice(all_responses)
    
    # Format the response
    response = (
        f"🔮 **Magic 8-Ball**\n\n"
        f"**Question:** {question[:100]}\n\n"
        f"**Answer:** {answer}"
    )
    
    await message.reply_text(response)
    track_game_stat(message.from_user.id, "8ball", 1)


@app.on_message(filters.command("lucky") & not_bot)
async def lucky_number(client, message: Message):
    """Test your luck."""
    if not message.from_user:
        return
    
    number = random.randint(1, 100)
    
    if number >= 90:
        result = "🌟 **AMAZING!** You're incredibly lucky today!"
    elif number >= 75:
        result = "✨ **Great!** You're quite lucky!"
    elif number >= 50:
        result = "😊 **Good!** Above average luck!"
    elif number >= 25:
        result = "😐 **Okay.** Average luck."
    else:
        result = "😢 **Unlucky.** Better luck next time!"
    
    await message.reply_text(
        f"🍀 **Luck Test**\n\n"
        f"Your luck score: **{number}/100**\n\n"
        f"{result}"
    )
    
    track_game_stat(message.from_user.id, "lucky", number)


@app.on_message(filters.command("spin") & not_bot)
async def spin_wheel(client, message: Message):
    """Spin the wheel of fortune."""
    if not message.from_user:
        return
    
    prizes = [
        ("💎", "Diamond", 1000),
        ("🏆", "Trophy", 500),
        ("🎁", "Gift", 250),
        ("⭐", "Star", 100),
        ("🪙", "Coin", 50),
        ("🎈", "Balloon", 10),
        ("💔", "Nothing", 0),
    ]
    
    msg = await message.reply_text("🎡 **Spinning the wheel...**")
    await asyncio.sleep(2)
    
    prize = random.choice(prizes)
    emoji, name, points = prize
    
    await msg.edit_text(
        f"🎡 **Wheel of Fortune**\n\n"
        f"You won: {emoji} **{name}**\n"
        f"Points: **{points}**"
    )
    
    track_game_stat(message.from_user.id, "spin_points", points)


# ============= MULTIPLAYER CHALLENGES =============

@app.on_message(filters.command("challenge") & filters.group & not_bot)
async def challenge_user(client, message: Message):
    """Challenge another user to a game."""
    if not message.from_user:
        return
    
    if not message.reply_to_message:
        return await message.reply_text(
            "❌ Reply to someone's message to challenge them!\n\n"
            "Example: Reply to a message and type `/challenge dice`"
        )
    
    if not message.reply_to_message.from_user:
        return await message.reply_text("❌ Cannot challenge this user!")
    
    if len(message.command) < 2:
        return await message.reply_text(
            "**Available games:**\n"
            "• dice\n• dart\n• basketball\n• football\n• bowling\n• slot\n\n"
            "Example: `/challenge dice`"
        )
    
    game = message.command[1].lower()
    if game not in DICE_EMOJIS:
        return await message.reply_text(
            f"❌ Invalid game: `{game}`\n\n"
            "Choose from: dice, dart, basketball, football, bowling, slot"
        )
    
    challenger = message.from_user
    challenged = message.reply_to_message.from_user
    
    if challenged.id == challenger.id:
        return await message.reply_text("❌ You can't challenge yourself!")
    
    if challenged.is_bot:
        return await message.reply_text("❌ You can't challenge a bot!")
    
    # Create challenge
    challenge_id = f"{challenger.id}_{challenged.id}_{int(datetime.now().timestamp())}"
    active_challenges[challenge_id] = {
        "challenger": challenger.id,
        "challenged": challenged.id,
        "game": game,
        "status": "pending",
        "created": datetime.now()
    }
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"accept_{challenge_id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"decline_{challenge_id}")
        ]
    ])
    
    await message.reply_text(
        f"🎮 **Game Challenge!**\n\n"
        f"[{challenger.first_name}](tg://user?id={challenger.id}) challenged "
        f"[{challenged.first_name}](tg://user?id={challenged.id})\n"
        f"Game: **{game.title()}** {DICE_EMOJIS[game]}\n\n"
        f"{challenged.first_name}, do you accept?",
        reply_markup=keyboard
    )


@app.on_callback_query(filters.regex(r"^accept_"))
async def accept_challenge(client, callback: CallbackQuery):
    """Accept a game challenge."""
    if not callback.from_user or callback.from_user.id == BOT_ID:
        return
    
    challenge_id = callback.data.split("_", 1)[1]
    
    if challenge_id not in active_challenges:
        return await callback.answer("❌ Challenge expired!", show_alert=True)
    
    challenge = active_challenges[challenge_id]
    
    if callback.from_user.id != challenge["challenged"]:
        return await callback.answer("❌ This challenge is not for you!", show_alert=True)
    
    if challenge["status"] != "pending":
        return await callback.answer("❌ Challenge already completed!", show_alert=True)
    
    # Start the game
    challenge["status"] = "active"
    game = challenge["game"]
    emoji = DICE_EMOJIS[game]
    
    try:
        await callback.message.edit_text(
            f"🎮 **Challenge Accepted!**\n\n"
            f"Game: **{game.title()}** {emoji}\n"
            f"Get ready..."
        )
    except MessageNotModified:
        pass
    
    await callback.answer()
    await asyncio.sleep(1)
    
    # Send dice for both players
    msg1 = await client.send_dice(callback.message.chat.id, emoji)
    await asyncio.sleep(1)
    msg2 = await client.send_dice(callback.message.chat.id, emoji)
    
    await asyncio.sleep(4)  # Wait for animation
    
    # Determine winner
    challenger_score = msg1.dice.value
    challenged_score = msg2.dice.value
    
    try:
        challenger_user = await client.get_users(challenge["challenger"])
        challenged_user = await client.get_users(challenge["challenged"])
        
        if challenger_score > challenged_score:
            winner = f"[{challenger_user.first_name}](tg://user?id={challenger_user.id})"
            result = "🏆 **Winner!**"
        elif challenged_score > challenger_score:
            winner = f"[{challenged_user.first_name}](tg://user?id={challenged_user.id})"
            result = "🏆 **Winner!**"
        else:
            winner = "Nobody"
            result = "🤝 **It's a tie!**"
        
        await callback.message.reply_text(
            f"🎮 **Challenge Results**\n\n"
            f"[{challenger_user.first_name}](tg://user?id={challenger_user.id}): **{challenger_score}**\n"
            f"[{challenged_user.first_name}](tg://user?id={challenged_user.id}): **{challenged_score}**\n\n"
            f"{result}\n"
            f"Winner: {winner}"
        )
    except Exception as e:
        print(f"[Challenge] Error getting users: {e}")
        await callback.message.reply_text(
            f"🎮 **Challenge Results**\n\n"
            f"Player 1: **{challenger_score}**\n"
            f"Player 2: **{challenged_score}**"
        )
    
    # Remove challenge
    if challenge_id in active_challenges:
        del active_challenges[challenge_id]


@app.on_callback_query(filters.regex(r"^decline_"))
async def decline_challenge(client, callback: CallbackQuery):
    """Decline a game challenge."""
    if not callback.from_user or callback.from_user.id == BOT_ID:
        return
    
    challenge_id = callback.data.split("_", 1)[1]
    
    if challenge_id not in active_challenges:
        return await callback.answer("❌ Challenge expired!", show_alert=True)
    
    challenge = active_challenges[challenge_id]
    
    if callback.from_user.id != challenge["challenged"]:
        return await callback.answer("❌ This challenge is not for you!", show_alert=True)
    
    try:
        await callback.message.edit_text(
            f"❌ **Challenge Declined**\n\n"
            f"[{callback.from_user.first_name}](tg://user?id={callback.from_user.id}) declined the challenge."
        )
    except MessageNotModified:
        pass
    
    await callback.answer()
    
    if challenge_id in active_challenges:
        del active_challenges[challenge_id]


# ============= STATISTICS =============

@app.on_message(filters.command("gamestats") & not_bot)
async def show_game_stats(client, message: Message):
    """Show user's game statistics."""
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    if user_id not in game_stats or not game_stats[user_id]:
        return await message.reply_text(
            "📊 **Game Statistics**\n\n"
            "You haven't played any games yet!\n"
            "Try `/dice`, `/dart`, `/rps` or other games."
        )
    
    stats = game_stats[user_id]
    text = f"📊 **Game Statistics for {message.from_user.first_name}**\n\n"
    
    for game, data in sorted(stats.items()):
        count = data["count"]
        total = data["total"]
        best = data["best"]
        avg = total / count if count > 0 else 0
        
        text += f"**{game.replace('_', ' ').title()}:**\n"
        text += f"  Played: {count} times\n"
        
        if best > 0:
            text += f"  Best: {best}\n"
            text += f"  Average: {avg:.1f}\n"
        
        text += "\n"
    
    await message.reply_text(text[:4096])  # Telegram message limit


@app.on_message(filters.command("leaderboard") & not_bot)
async def show_leaderboard(client, message: Message):
    """Show top players."""
    if not message.from_user:
        return
    
    if not game_stats:
        return await message.reply_text(
            "📊 **Leaderboard**\n\n"
            "No games played yet!"
        )
    
    # Calculate total games for each user
    user_totals = {}
    for user_id, stats in game_stats.items():
        total_games = sum(data["count"] for data in stats.values())
        user_totals[user_id] = total_games
    
    # Sort by total games
    sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    
    text = "🏆 **Leaderboard - Top Players**\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (user_id, total) in enumerate(sorted_users, 1):
        try:
            user = await client.get_users(user_id)
            name = user.first_name[:20]  # Limit name length
        except Exception:
            name = f"User {user_id}"
        
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} **{name}**: {total} games\n"
    
    await message.reply_text(text)

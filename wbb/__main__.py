import asyncio
import importlib
import re
import signal
import subprocess
from contextlib import closing, suppress

from pyrogram import filters, idle
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from uvloop import install

from wbb import (
    BOT_NAME,
    BOT_USERNAME,
    LOG_GROUP_ID,
    aiohttpsession,
    app,
    log,
)
from wbb.core.keyboard import ikb
from wbb.modules import ALL_MODULES
from wbb.modules.sudoers import bot_sys_stats
from wbb.utils import paginate_modules
from wbb.utils.constants import MARKDOWN
from wbb.utils.dbfunctions import clean_restart_stage, get_rules
from wbb.utils.functions import extract_text_and_keyb

loop = asyncio.get_event_loop()

HELPABLE = {}


def update_ytdlp():
    """Update yt-dlp automatically when bot starts."""
    try:
        print("🔄 Updating yt-dlp...")
        result = subprocess.run(["yt-dlp", "-U"], check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"yt-dlp update output: {result.stdout.strip()}")
        print("✅ yt-dlp update completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to update yt-dlp: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr.strip()}")
    except FileNotFoundError:
        print("⚠️ yt-dlp not found, skipping update")
    except Exception as e:
        print(f"❌ Unexpected error updating yt-dlp: {e}")

# Update yt-dlp on bot startup
update_ytdlp()


async def start_bot():
    global HELPABLE

    # Create a shutdown event
    shutdown_event = asyncio.Event()

    # Modify signal handler to set the event instead of stopping the loop
    def signal_handler():
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    for module in ALL_MODULES:
        imported_module = importlib.import_module("wbb.modules." + module)
        if (
            hasattr(imported_module, "__MODULE__")
            and imported_module.__MODULE__
        ):
            imported_module.__MODULE__ = imported_module.__MODULE__
            if (
                hasattr(imported_module, "__HELP__")
                and imported_module.__HELP__
            ):
                HELPABLE[
                    imported_module.__MODULE__.replace(" ", "_").lower()
                ] = imported_module
    bot_modules = ""
    j = 1
    for i in ALL_MODULES:
        if j == 4:
            bot_modules += "|{:<15}|\n".format(i)
            j = 0
        else:
            bot_modules += "|{:<15}".format(i)
        j += 1
    print("+===============================================================+")
    print("|                              WBB                              |")
    print("+===============+===============+===============+===============+")
    print(bot_modules)
    print("+===============+===============+===============+===============+")
    log.info(f"BOT STARTED AS {BOT_NAME}!")

    restart_data = await clean_restart_stage()

    try:
        log.info("Sending online status")
        if restart_data:
            await app.edit_message_text(
                restart_data["chat_id"],
                restart_data["message_id"],
                "**Restarted Successfully**",
            )

        else:
            await app.send_message(LOG_GROUP_ID, "Bot started!")
    except Exception:
        pass

    # Use idle() with the shutdown event
    try:
        await idle()
    except asyncio.CancelledError:
        pass

    # Wait for shutdown event
    await shutdown_event.wait()

    # Close aiohttp session before stopping clients
    await aiohttpsession.close()
    log.info("Stopping clients")
    await app.stop()
    log.info("Bot stopped gracefully")


home_keyboard_pm = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                text="Commands ❓", 
                callback_data="bot_commands"
            ),
            InlineKeyboardButton(
                text="System Stats 🖥",
                callback_data="stats_callback",
            )
        ],
        [
            InlineKeyboardButton(
                text="Add Me To Your Group 🎉",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=new",
            )
        ],
    ]
)

home_text_pm = (
    f"Hey there! My name is {BOT_NAME}. I can manage your "
    + "group with lots of useful features, feel free to "
    + "add me to your group."
)

keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                text="Help ❓",
                url=f"https://t.me/{BOT_USERNAME}?start=help",
            ),
            InlineKeyboardButton(
                text="Repo 🛠",
                url="https://github.com/thehamkercat/WilliamButcherBot",
            ),
        ],
        [
            InlineKeyboardButton(
                text="System Stats 💻",
                callback_data="stats_callback",
            ),
            InlineKeyboardButton(
                text="Support 👨",
                url="https://t.me/WBBSupport"
            ),
        ],
    ]
)


FED_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "Fed Owner Commands", callback_data="fed_owner"
            ),
            InlineKeyboardButton(
                "Fed Admin Commands", callback_data="fed_admin"
            ),
        ],
        [
            InlineKeyboardButton("User Commands", callback_data="fed_user"),
        ],
        [
            InlineKeyboardButton("Back", callback_data="help_back"),
        ],
    ]
)


@app.on_message(filters.command("start"))
async def start(_, message):
    if message.chat.type != ChatType.PRIVATE:
        return await message.reply(
            "Pm Me For More Details.", reply_markup=keyboard
        )
    if len(message.text.split()) > 1:
        user = await app.get_users(message.from_user.id)
        name = (message.text.split(None, 1)[1]).lower()
        match = re.match(r"rules_(.*)", name)
        if match:
            chat_id = match.group(1)
            user_id = message.from_user.id
            chat = await app.get_chat(int(chat_id))
            text = f"**The rules for `{chat.title}` are:\n\n**"
            rules = await get_rules(int(chat_id))
            if rules:
                text = text + rules
                if "{chat}" in text:
                    text = text.replace("{chat}", chat.title)
                if "{name}" in text:
                    text = text.replace("{name}", user.mention)
                keyb = None
                if re.findall(r"\[.+\,.+\]", text):
                    text, keyb = extract_text_and_keyb(ikb, text)
                await app.send_message(user_id, text=text, reply_markup=keyb)
            else:
                return await app.send_message(
                    user_id,
                    "The group admins haven't set any rules for this chat yet. "
                    "This probably doesn't mean it's lawless though...!",
                )
        if name == "mkdwn_help":
            await message.reply(
                MARKDOWN,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        elif "_" in name:
            module = name.split("_", 1)[1]
            text = (
                f"Here is the help for **{HELPABLE[module].__MODULE__}**:\n"
                + HELPABLE[module].__HELP__
            )
            if module == "federation":
                return await message.reply(
                    text=text,
                    reply_markup=FED_MARKUP,
                    disable_web_page_preview=True,
                )
            await message.reply(
                text,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("back", callback_data="help_back")]]
                ),
                disable_web_page_preview=True,
            )
        elif name == "help":
            text, keyb = await help_parser(message.from_user.first_name)
            await message.reply(
                text,
                reply_markup=keyb,
            )
    else:
        await message.reply(
            home_text_pm,
            reply_markup=home_keyboard_pm,
        )
    return


@app.on_message(filters.command("help"))
async def help_command(_, message):
    if message.chat.type != ChatType.PRIVATE:
        if len(message.command) >= 2:
            name = (message.text.split(None, 1)[1]).replace(" ", "_").lower()
            if str(name) in HELPABLE:
                key = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Click here",
                                url=f"t.me/{BOT_USERNAME}?start=help_{name}",
                            )
                        ],
                    ]
                )
                await message.reply(
                    f"Click on the below button to get help about {name}",
                    reply_markup=key,
                )
            else:
                await message.reply(
                    "PM Me For More Details.", reply_markup=keyboard
                )
        else:
            await message.reply(
                "Pm Me For More Details.", reply_markup=keyboard
            )
    else:
        if len(message.command) >= 2:
            name = (message.text.split(None, 1)[1]).replace(" ", "_").lower()
            if str(name) in HELPABLE:
                text = (
                    f"Here is the help for **{HELPABLE[name].__MODULE__}**:\n"
                    + HELPABLE[name].__HELP__
                )
                await message.reply(text, disable_web_page_preview=True)
            else:
                text, help_keyboard = await help_parser(
                    message.from_user.first_name
                )
                await message.reply(
                    text,
                    reply_markup=help_keyboard,
                    disable_web_page_preview=True,
                )
        else:
            text, help_keyboard = await help_parser(
                message.from_user.first_name
            )
            await message.reply(
                text, reply_markup=help_keyboard, disable_web_page_preview=True
            )
    return


async def help_parser(name, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    return (
        """Hello {first_name}, My name is {bot_name}.
I'm a group management bot with some useful features.
You can choose an option below, by clicking a button.
Also you can ask anything in Support Group.
""".format(
            first_name=name,
            bot_name=BOT_NAME,
        ),
        keyboard,
    )


@app.on_callback_query(filters.regex("bot_commands"))
async def commands_callbacc(_, CallbackQuery):
    text, keyboard = await help_parser(CallbackQuery.from_user.mention)
    await app.send_message(
        CallbackQuery.message.chat.id,
        text=text,
        reply_markup=keyboard,
    )

    await CallbackQuery.message.delete()


@app.on_callback_query(filters.regex("stats_callback"))
async def stats_callbacc(_, CallbackQuery):
    text = await bot_sys_stats()
    await app.answer_callback_query(CallbackQuery.id, text, show_alert=True)


@app.on_callback_query(filters.regex(r"help_(.*?)"))
async def help_button(client, query):
    home_match = re.match(r"help_home\((.+?)\)", query.data)
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    create_match = re.match(r"help_create", query.data)
    top_text = f"""
Hello {query.from_user.first_name}, My name is {BOT_NAME}.
I'm a group management bot with some useful features.
You can choose an option below, by clicking a button.
Also you can ask anything in Support Group.

General command are:
 - /start: Start the bot
 - /help: Give this message
 """
    if mod_match:
        module = (mod_match.group(1)).replace(" ", "_")
        text = (
            "{} **{}**:\n".format(
                "Here is the help for", HELPABLE[module].__MODULE__
            )
            + HELPABLE[module].__HELP__
        )
        if module == "federation":
            return await query.message.edit(
                text=text,
                reply_markup=FED_MARKUP,
                disable_web_page_preview=True,
            )
        await query.message.edit(
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("back", callback_data="help_back")]]
            ),
            disable_web_page_preview=True,
        )
    elif home_match:
        await app.send_message(
            query.from_user.id,
            text=home_text_pm,
            reply_markup=home_keyboard_pm,
        )
        await query.message.delete()
    elif prev_match:
        curr_page = int(prev_match.group(1))
        await query.message.edit(
            text=top_text,
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(curr_page - 1, HELPABLE, "help")
            ),
            disable_web_page_preview=True,
        )

    elif next_match:
        next_page = int(next_match.group(1))
        await query.message.edit(
            text=top_text,
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(next_page + 1, HELPABLE, "help")
            ),
            disable_web_page_preview=True,
        )

    elif back_match:
        await query.message.edit(
            text=top_text,
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(0, HELPABLE, "help")
            ),
            disable_web_page_preview=True,
        )

    elif create_match:
        text, keyboard = await help_parser(query)
        await query.message.edit(
            text=text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    return await client.answer_callback_query(query.id)


if __name__ == "__main__":
    install()

    try:
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        log.info("Received keyboard interrupt")
    finally:
        log.info("Shutting down...")
        # Log pending tasks for debugging
        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if pending_tasks:
            log.warning(f"Found {len(pending_tasks)} pending tasks during shutdown")
            for task in pending_tasks[:5]:  # Log first 5 tasks
                log.warning(f"Pending task: {task}")
        
        # Cancel all tasks with timeout
        for task in pending_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to finish cancelling with shorter timeout
        if pending_tasks:
            try:
                loop.run_until_complete(asyncio.wait_for(
                    asyncio.gather(*pending_tasks, return_exceptions=True), 
                    timeout=3.0
                ))
            except asyncio.TimeoutError:
                log.warning("Some tasks did not cancel within timeout - forcing shutdown")
            except Exception as e:
                log.error(f"Error during task cancellation: {e}")
        
        # Close aiohttp session if it exists (synchronous close)
        try:
            if 'aiohttpsession' in globals() and hasattr(aiohttpsession, 'close'):
                loop.run_until_complete(aiohttpsession.close())
        except Exception as e:
            log.warning(f"Error closing aiohttp session: {e}")
        
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        log.info("Shutdown complete")

# wbb/utils/functions.py
import re
from datetime import datetime, timedelta
from pyrogram.enums import MessageEntityType
from pyrogram.errors import UsernameInvalid


def extract_text_and_keyb(ikb_func, text):
    """Extract inline keyboard buttons from text"""
    keyboard = []
    
    # Pattern: [Button Text, url/callback_data]
    pattern = r'\[([^\[\]]+)\s*,\s*([^\[\]]+)\]'
    
    matches = re.finditer(pattern, text)
    
    for match in matches:
        button_text = match.group(1).strip()
        button_data = match.group(2).strip()
        
        button = {}
        button['text'] = button_text
        
        if button_data.startswith('http'):
            button['url'] = button_data
        else:
            button['callback_data'] = button_data
        
        keyboard.append([button])
        text = text.replace(match.group(0), '')
    
    if keyboard:
        return text.strip(), ikb_func(keyboard)
    return text.strip(), None


async def extract_userid(message, text: str):
    """
    NOT TO BE USED OUTSIDE THIS FILE
    """
    from wbb import app

    def is_int(text: str):
        try:
            int(text)
        except ValueError:
            return False
        return True

    text = text.strip()

    if is_int(text):
        return int(text)

    entities = message.entities
    app = message._client
    if len(entities) < 2:
        return (await app.get_users(text)).id
    entity = entities[1]
    if entity.type == MessageEntityType.MENTION:
        return (await app.get_users(text)).id
    if entity.type == MessageEntityType.TEXT_MENTION:
        return entity.user.id
    return None


async def extract_user_and_reason(message, sender_chat=False):
    from wbb import app

    args = message.text.strip().split()
    text = message.text
    user = None
    reason = None

    try:
        if message.reply_to_message:
            reply = message.reply_to_message
            # if reply to a message and no reason is given
            if not reply.from_user:
                if (
                    reply.sender_chat
                    and reply.sender_chat != message.chat.id
                    and sender_chat
                ):
                    id_ = reply.sender_chat.id
                else:
                    return None, None
            else:
                id_ = reply.from_user.id

            if len(args) < 2:
                reason = None
            else:
                reason = text.split(None, 1)[1]
            return id_, reason

        # if not reply to a message and no reason is given
        if len(args) == 2:
            user = text.split(None, 1)[1]
            return await extract_userid(message, user), None

        # if reason is given
        if len(args) > 2:
            user, reason = text.split(None, 2)[1:]
            return await extract_userid(message, user), reason

        return user, reason

    except UsernameInvalid:
        return "", ""


async def extract_user(message):
    return (await extract_user_and_reason(message))[0]


async def time_converter(message, time_value: str):
    from wbb import app

    unit = ["m", "h", "d"]  # m == minutes | h == hours | d == days
    check_unit = "".join(list(filter(time_value[-1].lower().endswith, unit)))
    currunt_time = datetime.now()
    time_digit = time_value[:-1]
    if not time_digit.isdigit():
        return await message.reply_text("Incorrect time specified")
    if check_unit == "m":
        temp_time = currunt_time + timedelta(minutes=int(time_digit))
    elif check_unit == "h":
        temp_time = currunt_time + timedelta(hours=int(time_digit))
    elif check_unit == "d":
        temp_time = currunt_time + timedelta(days=int(time_digit))
    else:
        return await message.reply_text("Incorrect time specified.")
    return temp_time


async def check_format(ikb, raw_text: str):
    keyb = re.findall(r"\[.+\,.+\]", raw_text)
    if keyb and not "~" in raw_text:
        raw_text = raw_text.replace("button=", "\n~\nbutton=")
        return raw_text
    if "~" in raw_text and keyb:
        if not extract_text_and_keyb(ikb, raw_text):
            return ""
        else:
            return raw_text
    else:
        return raw_text


async def get_data_and_name(replied_message, message):
    """Extract data and name from message for filters/notes."""
    text = message.text.markdown if message.text else message.caption.markdown
    name = text.split(None, 1)[1].strip()
    text = name.split(" ", 1)
    
    if len(text) > 1:
        name = text[0]
        data = text[1].strip()
        if replied_message and (
            replied_message.sticker or replied_message.video_note
        ):
            data = None
    else:
        if replied_message and (
            replied_message.sticker or replied_message.video_note
        ):
            data = None
        elif (
            replied_message
            and not replied_message.text
            and not replied_message.caption
        ):
            data = None
        else:
            data = (
                replied_message.text.markdown
                if replied_message.text
                else replied_message.caption.markdown
            )
            command = message.command[0]
            match = f"/{command} " + name
            if not message.reply_to_message and message.text:
                if match == data:
                    data = "error"
            elif not message.reply_to_message and not message.text:
                if match == data:
                    data = None
    
    return data, name

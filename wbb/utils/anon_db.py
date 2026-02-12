from sqlalchemy import Column, Integer, Boolean, String
from wbb.utils.database import BASE, SESSION


class AnonChat(BASE):
    __tablename__ = "anon_chats"

    chat_id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False)
    rate_limit_count = Column(Integer, default=10)
    rate_limit_window = Column(Integer, default=30)
    media_types = Column(String, default="photo,video,document,audio,voice,animation,sticker,video_note")
    total_reposted = Column(Integer, default=0)
    total_deleted = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)


class AnonWhitelist(BASE):
    __tablename__ = "anon_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer)
    user_id = Column(Integer)


def get_chat(chat_id: int):
    return SESSION.query(AnonChat).get(chat_id)


def get_or_create_chat(chat_id: int):
    chat = get_chat(chat_id)
    if not chat:
        chat = AnonChat(chat_id=chat_id)
        SESSION.add(chat)
        SESSION.commit()
    return chat


def enable_chat(chat_id: int):
    chat = get_or_create_chat(chat_id)
    chat.enabled = True
    SESSION.commit()


def disable_chat(chat_id: int):
    chat = get_or_create_chat(chat_id)
    chat.enabled = False
    SESSION.commit()


def is_enabled(chat_id: int) -> bool:
    chat = get_chat(chat_id)
    return chat.enabled if chat else False


def get_whitelist(chat_id: int):
    return [x.user_id for x in SESSION.query(AnonWhitelist).filter_by(chat_id=chat_id).all()]


def add_whitelist(chat_id: int, user_id: int):
    if user_id not in get_whitelist(chat_id):
        SESSION.add(AnonWhitelist(chat_id=chat_id, user_id=user_id))
        SESSION.commit()


def remove_whitelist(chat_id: int, user_id: int):
    SESSION.query(AnonWhitelist).filter_by(chat_id=chat_id, user_id=user_id).delete()
    SESSION.commit()

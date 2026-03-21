from pydantic import BaseModel
from typing import Optional


class TextBody(BaseModel):
    body: str


class ImageBody(BaseModel):
    file_key: str
    mime_type: str
    caption: Optional[str] = ""


class AudioBody(BaseModel):
    file_key: str
    mime_type: str


class TextPayload(BaseModel):
    user_id: str
    username: str
    phone_no: str
    timestamp: int
    message_type: str = "text"
    text: TextBody


class ImagePayload(BaseModel):
    user_id: str
    username: str
    phone_no: str
    timestamp: int
    message_type: str = "image"
    image: ImageBody


class AudioPayload(BaseModel):
    user_id: str
    username: str
    phone_no: str
    timestamp: int
    message_type: str = "audio"
    audio: AudioBody

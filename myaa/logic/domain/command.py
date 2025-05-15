from dataclasses import dataclass
from myaa.logic.domain.message import Message


@dataclass
class ChatCommand:
    responder_id: str
    message: Message

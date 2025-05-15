from dataclasses import dataclass, field
from typing import List
from myaa.logic.domain.message import Message


@dataclass
class Context:
    message: Message
    thread_memory: List[Message] = field(default_factory=list)

    @classmethod
    def init(cls, message: Message) -> "Context":
        return cls(message=message)

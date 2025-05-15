from dataclasses import dataclass, field
from typing import List, Optional
from .message import Message


@dataclass
class Context:
    message: Optional[Message] = None
    thread_memory: List[Message] = field(default_factory=list)

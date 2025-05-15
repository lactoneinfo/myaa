from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
import copy
from myaa.logic.domain.context import Context
from myaa.logic.domain.message import Message


class Status(str, Enum):
    ready = "ready"
    running = "running"


@dataclass
class AgentState:
    id: str
    character_name: str
    context: Context
    status: Status = Status.ready
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def new(cls, initial_message: Message) -> "AgentState":
        return cls(
            id=str(uuid.uuid4()),
            character_name="example",
            context=Context(message=initial_message),
            updated_at=time.time(),
        )

    def copy(self) -> "AgentState":
        return AgentState(
            id=str(uuid.uuid4()),
            character_name=self.character_name,
            status=Status.ready,
            context=copy.deepcopy(self.context),
            updated_at=time.time(),
        )

    def add_message(self, message: Message):
        if self.context.message:
            self.context.thread_memory.append(self.context.message)
            self.context.thread_memory = self.context.thread_memory[-5:]
        self.context.message = message
        self.updated_at = time.time()

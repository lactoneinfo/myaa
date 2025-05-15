from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
import copy
from myaa.domain.context import Context
from myaa.domain.message import Message


class Status(str, Enum):
    ready = "ready"
    running = "running"


@dataclass
class AgentState:
    id: str
    responder_id: str
    context: Context
    status: Status = Status.ready
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def new(cls, initial_message: Message, responder_id: str) -> "AgentState":
        return cls(
            id=str(uuid.uuid4()),
            responder_id=responder_id,
            context=Context(message=initial_message),
            updated_at=time.time(),
        )

    def copy(self) -> "AgentState":
        return AgentState(
            id=str(uuid.uuid4()),
            responder_id=self.responder_id,
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

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
from typing import List
import copy


class Status(str, Enum):
    ready = "ready"
    running = "running"


@dataclass
class Context:
    message: str = ""
    thread_memory: List[str] = field(default_factory=list)


@dataclass
class AgentState:
    id: str
    status: Status = Status.ready
    context: Context = field(default_factory=Context)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def new(cls) -> "AgentState":
        return cls(id=str(uuid.uuid4()))

    def copy(self) -> AgentState:
        return AgentState(
            id=str(uuid.uuid4()),
            status=Status.ready,
            context=copy.deepcopy(self.context),
            updated_at=time.time(),
        )

    def add_message(self, text: str):
        if self.context.message:
            self.context.thread_memory.append(self.context.message)
            self.context.thread_memory = self.context.thread_memory[-5:]
        self.context.message = text
        self.updated_at = time.time()

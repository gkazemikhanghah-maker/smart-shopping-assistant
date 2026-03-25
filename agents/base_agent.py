"""
Base Agent — Foundation for all agents in the system.
"""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from config import LOG_LEVEL, MAX_MEMORY_MSG

logging.basicConfig(level=LOG_LEVEL)


class AgentStatus(Enum):
    IDLE    = "idle"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"


@dataclass
class Message:
    sender:    str
    receiver:  str
    content:   Any
    msg_type:  str = "message"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __repr__(self) -> str:
        return f"[{self.msg_type.upper()}] {self.sender} -> {self.receiver}: {str(self.content)[:80]}"


@dataclass
class AgentResult:
    agent_name: str
    success:    bool
    data:       Any
    error:      str | None = None
    metadata:   dict = field(default_factory=dict)


class BaseAgent(ABC):
    def __init__(self, name: str, description: str = ""):
        self.name        = name
        self.description = description
        self.status      = AgentStatus.IDLE
        self._memory: list[Message]       = []
        self._tools:  dict[str, callable] = {}
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def run(self, input_data: Any) -> AgentResult: ...

    def set_status(self, status: AgentStatus) -> None:
        self.status = status

    def remember(self, message: Message) -> None:
        self._memory.append(message)
        if len(self._memory) > MAX_MEMORY_MSG:
            self._memory.pop(0)

    def success(self, data: Any, **metadata) -> AgentResult:
        return AgentResult(agent_name=self.name, success=True, data=data, metadata=metadata)

    def failure(self, error: str, **metadata) -> AgentResult:
        return AgentResult(agent_name=self.name, success=False, data=None, error=error, metadata=metadata)

    def __repr__(self) -> str:
        return f"<Agent:{self.name} status={self.status.value}>"
"""
Message Bus — Communication layer between agents.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger("core.message_bus")


@dataclass
class BusMessage:
    channel:   str
    sender:    str
    content:   Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MessageBus:
    def __init__(self):
        self._channels: dict[str, list[BusMessage]] = defaultdict(list)
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._history: list[BusMessage] = []

    async def publish(self, channel: str, sender: str, content: Any) -> BusMessage:
        msg = BusMessage(channel=channel, sender=sender, content=content)
        self._channels[channel].append(msg)
        self._history.append(msg)
        for callback in self._subscribers.get(channel, []):
            await callback(msg)
        return msg

    def get_messages(self, channel: str) -> list[BusMessage]:
        return list(self._channels.get(channel, []))

    def get_latest(self, channel: str) -> BusMessage | None:
        messages = self._channels.get(channel, [])
        return messages[-1] if messages else None

    def clear_all(self) -> None:
        self._channels.clear()
        self._history.clear()

    @property
    def active_channels(self) -> list[str]:
        return list(self._channels.keys())
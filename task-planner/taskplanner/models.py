"""Модели предметной области: задача, приоритет и работа с датами."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import IntEnum
from typing import Any, Optional

DATE_FORMAT = "%d.%m.%Y"
MAX_TITLE_LENGTH = 120


class Priority(IntEnum):
    """Приоритет задачи. Чем больше число, тем важнее задача."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return PRIORITY_LABELS[self]

    @classmethod
    def from_value(cls, value: Any) -> "Priority":
        """Приводит число, имя или русскую подпись к Priority."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            text = value.strip().casefold()
            for item in cls:
                if text in (item.name.casefold(), item.label.casefold()):
                    return item
            if not text.isdigit():
                raise ValueError(f"Неизвестный приоритет: {value!r}")
            value = int(text)
        return cls(int(value))


PRIORITY_LABELS = {
    Priority.LOW: "Низкий",
    Priority.MEDIUM: "Средний",
    Priority.HIGH: "Высокий",
}


def parse_date(text: Optional[str]) -> Optional[date]:
    """Разбирает дату ДД.ММ.ГГГГ (или ГГГГ-ММ-ДД). Пустая строка -> None."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    for fmt in (DATE_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("Дата должна быть в формате ДД.ММ.ГГГГ, например 31.12.2026")


def format_date(value: Optional[date]) -> str:
    return value.strftime(DATE_FORMAT) if value else ""


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


@dataclass
class Task:
    """Одна задача в планировщике."""

    title: str
    description: str = ""
    due_date: Optional[date] = None
    priority: Priority = Priority.MEDIUM
    category: str = ""
    done: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()
        self.category = (self.category or "").strip()
        self.priority = Priority.from_value(self.priority)
        if not self.title:
            raise ValueError("Название задачи не может быть пустым")
        if len(self.title) > MAX_TITLE_LENGTH:
            raise ValueError(
                f"Название слишком длинное (максимум {MAX_TITLE_LENGTH} символов)"
            )

    def is_overdue(self, today: Optional[date] = None) -> bool:
        """Задача просрочена, если срок прошёл, а она не выполнена."""
        if self.done or self.due_date is None:
            return False
        return self.due_date < (today or date.today())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority": int(self.priority),
            "category": self.category,
            "done": self.done,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Создаёт задачу из словаря. Устойчиво к отсутствующим полям,
        поэтому читает и файлы старого формата (title/description/due_date)."""
        try:
            due = parse_date(data.get("due_date"))
        except ValueError:
            due = None
        try:
            priority = Priority.from_value(data.get("priority", Priority.MEDIUM))
        except ValueError:
            priority = Priority.MEDIUM
        try:
            created = datetime.fromisoformat(data["created_at"])
        except (KeyError, TypeError, ValueError):
            created = _now()
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            due_date=due,
            priority=priority,
            category=data.get("category", ""),
            done=bool(data.get("done", False)),
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            created_at=created,
        )

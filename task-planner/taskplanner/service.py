"""Бизнес-логика: добавление, изменение, фильтрация и статистика задач."""
from __future__ import annotations

import dataclasses
from datetime import date
from typing import Dict, List, Optional

from .models import Priority, Task, parse_date
from .storage import JsonStorage

STATUSES = ("all", "active", "done", "overdue")
SORT_KEYS = ("due", "priority", "title", "created")
_EDITABLE = {"title", "description", "due_date", "priority", "category", "done"}


class TaskNotFoundError(KeyError):
    """Задача с таким id не найдена."""


class TaskService:
    """Работает со списком задач и сохраняет изменения через storage."""

    def __init__(self, storage: JsonStorage) -> None:
        self._storage = storage
        self._tasks: List[Task] = storage.load()

    # ---------- CRUD ----------
    def add(
        self,
        title: str,
        description: str = "",
        due_date=None,
        priority=Priority.MEDIUM,
        category: str = "",
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            due_date=self._to_date(due_date),
            priority=priority,
            category=category,
        )
        self._tasks.append(task)
        self._storage.save(self._tasks)
        return task

    def get(self, task_id: str) -> Task:
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise TaskNotFoundError(task_id)

    def exists(self, task_id: str) -> bool:
        return any(task.id == task_id for task in self._tasks)

    def update(self, task_id: str, **changes) -> Task:
        unknown = set(changes) - _EDITABLE
        if unknown:
            raise ValueError(f"Нельзя изменить поля: {', '.join(sorted(unknown))}")
        if "due_date" in changes:
            changes["due_date"] = self._to_date(changes["due_date"])
        old = self.get(task_id)
        # replace() заново вызывает __post_init__, значит данные проверяются
        new = dataclasses.replace(old, **changes)
        self._tasks[self._tasks.index(old)] = new
        self._storage.save(self._tasks)
        return new

    def toggle_done(self, task_id: str) -> Task:
        task = self.get(task_id)
        return self.update(task_id, done=not task.done)

    def delete(self, task_id: str) -> None:
        task = self.get(task_id)
        self._tasks.remove(task)
        self._storage.save(self._tasks)

    def clear_completed(self) -> int:
        before = len(self._tasks)
        self._tasks = [task for task in self._tasks if not task.done]
        removed = before - len(self._tasks)
        if removed:
            self._storage.save(self._tasks)
        return removed

    # ---------- выборки ----------
    def all(self) -> List[Task]:
        return list(self._tasks)

    def query(
        self,
        status: str = "all",
        search: str = "",
        sort_by: str = "due",
        today: Optional[date] = None,
    ) -> List[Task]:
        if status not in STATUSES:
            raise ValueError(f"Неизвестный статус: {status}")
        if sort_by not in SORT_KEYS:
            raise ValueError(f"Неизвестная сортировка: {sort_by}")

        today = today or date.today()
        needle = search.strip().casefold()
        result = []
        for task in self._tasks:
            if status == "active" and task.done:
                continue
            if status == "done" and not task.done:
                continue
            if status == "overdue" and not task.is_overdue(today):
                continue
            if needle:
                haystack = f"{task.title} {task.description} {task.category}".casefold()
                if needle not in haystack:
                    continue
            result.append(task)
        return self._sorted(result, sort_by)

    def stats(self, today: Optional[date] = None) -> Dict[str, int]:
        today = today or date.today()
        done = sum(1 for task in self._tasks if task.done)
        overdue = sum(1 for task in self._tasks if task.is_overdue(today))
        return {
            "total": len(self._tasks),
            "done": done,
            "active": len(self._tasks) - done,
            "overdue": overdue,
        }

    # ---------- внутреннее ----------
    @staticmethod
    def _to_date(value) -> Optional[date]:
        if isinstance(value, str) or value is None:
            return parse_date(value)
        return value

    @staticmethod
    def _sorted(tasks: List[Task], sort_by: str) -> List[Task]:
        def by_due(t: Task):
            return (t.due_date is None, t.due_date or date.max)

        # Выполненные всегда внизу списка
        if sort_by == "due":
            return sorted(
                tasks, key=lambda t: (t.done, *by_due(t), -int(t.priority), t.created_at)
            )
        if sort_by == "priority":
            return sorted(
                tasks, key=lambda t: (t.done, -int(t.priority), *by_due(t), t.created_at)
            )
        if sort_by == "title":
            return sorted(tasks, key=lambda t: (t.done, t.title.casefold()))
        # created: новые сверху
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

"""Хранение задач в JSON-файле."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Union

from .models import Task

FORMAT_VERSION = 1


class JsonStorage:
    """Читает и записывает список задач в JSON-файл."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def load(self) -> List[Task]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._quarantine()
            return []

        # Поддерживаем новый формат {"version": 1, "tasks": [...]}
        # и старый - просто список задач.
        items = raw.get("tasks") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            self._quarantine()
            return []

        tasks: List[Task] = []
        for item in items:
            try:
                tasks.append(Task.from_dict(item))
            except (ValueError, TypeError, AttributeError):
                continue  # битую запись пропускаем, остальные сохраняем
        return tasks

    def save(self, tasks: List[Task]) -> None:
        """Атомарная запись: сначала во временный файл, потом замена."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": FORMAT_VERSION,
            "tasks": [task.to_dict() for task in tasks],
        }
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp_path, self.path)

    def _quarantine(self) -> None:
        """Переименовывает повреждённый файл, чтобы не потерять данные."""
        backup = self.path.with_name(self.path.name + ".corrupt")
        os.replace(self.path, backup)

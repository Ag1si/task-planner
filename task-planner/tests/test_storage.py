import json
import tempfile
import unittest
from pathlib import Path

from taskplanner.models import Task
from taskplanner.storage import JsonStorage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "nested" / "tasks.json"

    def test_missing_file_gives_empty_list(self):
        self.assertEqual(JsonStorage(self.path).load(), [])

    def test_save_and_load(self):
        storage = JsonStorage(self.path)
        tasks = [Task("Первая"), Task("Вторая", category="Дом")]
        storage.save(tasks)
        self.assertEqual(storage.load(), tasks)
        self.assertFalse(self.path.with_name("tasks.json.tmp").exists())

    def test_file_keeps_cyrillic_readable(self):
        JsonStorage(self.path).save([Task("Привет")])
        self.assertIn("Привет", self.path.read_text(encoding="utf-8"))

    def test_corrupt_file_is_quarantined(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ это не json", encoding="utf-8")
        self.assertEqual(JsonStorage(self.path).load(), [])
        self.assertTrue(self.path.with_name("tasks.json.corrupt").exists())

    def test_old_list_format_is_supported(self):
        self.path.parent.mkdir(parents=True)
        old = [{"title": "Курсовая", "description": "Закончить", "due_date": "26.12.2026"}]
        self.path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        tasks = JsonStorage(self.path).load()
        self.assertEqual([t.title for t in tasks], ["Курсовая"])

    def test_bad_records_are_skipped(self):
        self.path.parent.mkdir(parents=True)
        data = {"tasks": [{"title": ""}, {"title": "Нормальная"}, 42]}
        self.path.write_text(json.dumps(data), encoding="utf-8")
        tasks = JsonStorage(self.path).load()
        self.assertEqual([t.title for t in tasks], ["Нормальная"])


if __name__ == "__main__":
    unittest.main()

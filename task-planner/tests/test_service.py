import tempfile
import unittest
from datetime import date
from pathlib import Path

from taskplanner.models import Priority
from taskplanner.service import TaskNotFoundError, TaskService
from taskplanner.storage import JsonStorage

TODAY = date(2026, 11, 23)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "tasks.json"
        self.service = TaskService(JsonStorage(self.path))

    def _reload(self):
        return TaskService(JsonStorage(self.path))

    def test_add_persists(self):
        task = self.service.add("Тест", due_date="01.12.2026", priority=Priority.HIGH)
        reloaded = self._reload().get(task.id)
        self.assertEqual(reloaded.title, "Тест")
        self.assertEqual(reloaded.due_date, date(2026, 12, 1))

    def test_add_invalid_does_not_change_state(self):
        with self.assertRaises(ValueError):
            self.service.add("")
        with self.assertRaises(ValueError):
            self.service.add("ok", due_date="вчера")
        self.assertEqual(self.service.all(), [])

    def test_update_and_clear_date(self):
        task = self.service.add("A", due_date="01.12.2026")
        self.service.update(task.id, title="B", due_date=None)
        fresh = self._reload().get(task.id)
        self.assertEqual(fresh.title, "B")
        self.assertIsNone(fresh.due_date)

    def test_update_rejects_protected_fields(self):
        task = self.service.add("A")
        with self.assertRaises(ValueError):
            self.service.update(task.id, id="hacked")

    def test_failed_update_keeps_old_task(self):
        task = self.service.add("A")
        with self.assertRaises(ValueError):
            self.service.update(task.id, title="  ")
        self.assertEqual(self.service.get(task.id).title, "A")

    def test_toggle_done(self):
        task = self.service.add("A")
        self.assertTrue(self.service.toggle_done(task.id).done)
        self.assertFalse(self.service.toggle_done(task.id).done)

    def test_delete(self):
        task = self.service.add("A")
        self.service.delete(task.id)
        self.assertFalse(self.service.exists(task.id))
        with self.assertRaises(TaskNotFoundError):
            self.service.delete(task.id)
        self.assertEqual(self._reload().all(), [])

    def test_clear_completed(self):
        a = self.service.add("A")
        self.service.add("B")
        self.service.toggle_done(a.id)
        self.assertEqual(self.service.clear_completed(), 1)
        self.assertEqual([t.title for t in self.service.all()], ["B"])

    def test_filters_and_search(self):
        a = self.service.add("Отчёт", category="Работа", due_date="01.11.2026")
        self.service.add("Молоко", category="Дом", due_date="30.11.2026")
        c = self.service.add("Звонок", description="про отчёт")
        self.service.toggle_done(c.id)

        titles = lambda **kw: [t.title for t in self.service.query(today=TODAY, **kw)]
        self.assertEqual(titles(status="overdue"), ["Отчёт"])
        self.assertEqual(titles(status="done"), ["Звонок"])
        self.assertCountEqual(titles(status="active"), ["Отчёт", "Молоко"])
        self.assertCountEqual(titles(search="ОТЧЁТ"), ["Отчёт", "Звонок"])
        self.assertEqual(titles(search="дом"), ["Молоко"])
        self.assertTrue(self.service.get(a.id).is_overdue(TODAY))

    def test_sort_by_due_puts_undated_and_done_last(self):
        self.service.add("без срока")
        self.service.add("поздно", due_date="30.12.2026")
        self.service.add("рано", due_date="01.12.2026")
        done = self.service.add("готово", due_date="01.01.2026")
        self.service.toggle_done(done.id)
        order = [t.title for t in self.service.query(sort_by="due", today=TODAY)]
        self.assertEqual(order, ["рано", "поздно", "без срока", "готово"])

    def test_sort_by_priority(self):
        self.service.add("low", priority=Priority.LOW)
        self.service.add("high", priority=Priority.HIGH)
        self.service.add("mid", priority=Priority.MEDIUM)
        order = [t.title for t in self.service.query(sort_by="priority")]
        self.assertEqual(order, ["high", "mid", "low"])

    def test_invalid_query_args(self):
        with self.assertRaises(ValueError):
            self.service.query(status="что-то")
        with self.assertRaises(ValueError):
            self.service.query(sort_by="что-то")

    def test_stats(self):
        a = self.service.add("A", due_date="01.11.2026")
        self.service.add("B")
        self.service.add("C", due_date="01.11.2026")
        self.service.toggle_done(a.id)
        self.assertEqual(
            self.service.stats(TODAY),
            {"total": 3, "done": 1, "active": 2, "overdue": 1},
        )


if __name__ == "__main__":
    unittest.main()

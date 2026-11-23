import unittest
from datetime import date

from taskplanner.models import Priority, Task, format_date, parse_date


class ParseDateTests(unittest.TestCase):
    def test_russian_format(self):
        self.assertEqual(parse_date("26.12.2026"), date(2026, 12, 26))

    def test_iso_format(self):
        self.assertEqual(parse_date("2026-12-26"), date(2026, 12, 26))

    def test_empty_is_none(self):
        self.assertIsNone(parse_date("   "))
        self.assertIsNone(parse_date(None))

    def test_invalid_raises(self):
        for bad in ("31.02.2026", "завтра", "2026/12/01"):
            with self.assertRaises(ValueError):
                parse_date(bad)

    def test_format_roundtrip(self):
        self.assertEqual(format_date(date(2026, 1, 5)), "05.01.2026")
        self.assertEqual(format_date(None), "")


class PriorityTests(unittest.TestCase):
    def test_from_value(self):
        self.assertEqual(Priority.from_value(3), Priority.HIGH)
        self.assertEqual(Priority.from_value("Низкий"), Priority.LOW)
        self.assertEqual(Priority.from_value("medium"), Priority.MEDIUM)
        self.assertEqual(Priority.from_value("2"), Priority.MEDIUM)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            Priority.from_value("срочно")
        with self.assertRaises(ValueError):
            Priority.from_value(9)


class TaskTests(unittest.TestCase):
    def test_title_is_required_and_trimmed(self):
        self.assertEqual(Task("  Тест  ").title, "Тест")
        with self.assertRaises(ValueError):
            Task("   ")

    def test_title_too_long(self):
        with self.assertRaises(ValueError):
            Task("x" * 500)

    def test_overdue(self):
        today = date(2026, 11, 23)
        self.assertTrue(Task("a", due_date=date(2026, 11, 22)).is_overdue(today))
        self.assertFalse(Task("a", due_date=date(2026, 11, 23)).is_overdue(today))
        self.assertFalse(Task("a").is_overdue(today))
        self.assertFalse(
            Task("a", due_date=date(2026, 1, 1), done=True).is_overdue(today)
        )

    def test_dict_roundtrip(self):
        task = Task("Купить хлеб", "в магазине", date(2026, 12, 1), Priority.HIGH, "Дом")
        clone = Task.from_dict(task.to_dict())
        self.assertEqual(task, clone)

    def test_legacy_format(self):
        legacy = {"title": "Курсовая", "description": "Закончить", "due_date": "26.12.2026"}
        task = Task.from_dict(legacy)
        self.assertEqual(task.due_date, date(2026, 12, 26))
        self.assertEqual(task.priority, Priority.MEDIUM)
        self.assertFalse(task.done)


if __name__ == "__main__":
    unittest.main()

"""Графический интерфейс TaskPlanner на Tkinter / ttk."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional, Union

from .models import Priority, Task, format_date, parse_date
from .service import TaskNotFoundError, TaskService
from .storage import JsonStorage

DEFAULT_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "tasks.json"

FILTERS = {
    "Все": "all",
    "Активные": "active",
    "Выполненные": "done",
    "Просроченные": "overdue",
}
SORTS = {
    "По сроку": "due",
    "По приоритету": "priority",
    "По названию": "title",
    "Сначала новые": "created",
}
PRIORITY_CHOICES = {item.label: item for item in Priority}
PRIORITY_NAMES = [Priority.LOW.label, Priority.MEDIUM.label, Priority.HIGH.label]


class TaskPlannerApp:
    """Главное окно приложения."""

    def __init__(self, root: tk.Tk, service: TaskService) -> None:
        self.root = root
        self.service = service
        self.editing_id: Optional[str] = None

        self.root.title("TaskPlanner — планировщик задач")
        self.root.minsize(900, 560)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------ интерфейс
    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self._build_form(main)
        self._build_list(main)

        self.stats_var = tk.StringVar()
        ttk.Label(main, textvariable=self.stats_var, anchor="w").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

    def _build_form(self, parent: ttk.Frame) -> None:
        form = ttk.LabelFrame(parent, text="Задача", padding=10)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        self.mode_var = tk.StringVar(value="Новая задача")
        ttk.Label(form, textvariable=self.mode_var, font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        ttk.Label(form, text="Название *").pack(anchor="w")
        self.title_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.title_var, width=34).pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Описание").pack(anchor="w")
        self.desc_text = tk.Text(form, height=5, width=34, wrap="word")
        self.desc_text.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Срок (ДД.ММ.ГГГГ, можно пусто)").pack(anchor="w")
        self.date_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.date_var, width=34).pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Приоритет").pack(anchor="w")
        self.priority_var = tk.StringVar(value=Priority.MEDIUM.label)
        ttk.Combobox(
            form,
            textvariable=self.priority_var,
            values=PRIORITY_NAMES,
            state="readonly",
        ).pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Категория").pack(anchor="w")
        self.category_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.category_var, width=34).pack(fill="x", pady=(0, 12))

        self.add_btn = ttk.Button(form, text="Добавить задачу", command=self.add_task)
        self.add_btn.pack(fill="x", pady=2)
        self.save_btn = ttk.Button(
            form, text="Сохранить изменения", command=self.save_changes, state="disabled"
        )
        self.save_btn.pack(fill="x", pady=2)
        ttk.Button(form, text="Очистить форму", command=self.reset_form).pack(fill="x", pady=2)

    def _build_list(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        # Панель поиска, фильтра и сортировки
        toolbar = ttk.Frame(panel)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="Поиск:").grid(row=0, column=0, padx=(0, 4))
        self.search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.search_var).grid(row=0, column=1, sticky="ew")
        self.search_var.trace_add("write", lambda *_: self.refresh())

        self.filter_var = tk.StringVar(value="Все")
        filter_box = ttk.Combobox(
            toolbar, textvariable=self.filter_var, values=list(FILTERS), state="readonly", width=14
        )
        filter_box.grid(row=0, column=2, padx=(8, 0))
        filter_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        self.sort_var = tk.StringVar(value="По сроку")
        sort_box = ttk.Combobox(
            toolbar, textvariable=self.sort_var, values=list(SORTS), state="readonly", width=16
        )
        sort_box.grid(row=0, column=3, padx=(8, 0))
        sort_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        # Таблица задач
        columns = ("done", "title", "category", "priority", "due")
        self.tree = ttk.Treeview(panel, columns=columns, show="headings", selectmode="browse")
        headings = {
            "done": ("✓", 40, "center"),
            "title": ("Название", 280, "w"),
            "category": ("Категория", 110, "w"),
            "priority": ("Приоритет", 90, "center"),
            "due": ("Срок", 100, "center"),
        }
        for name, (text, width, anchor) in headings.items():
            self.tree.heading(name, text=text)
            self.tree.column(name, width=width, anchor=anchor, stretch=(name == "title"))
        self.tree.tag_configure("overdue", foreground="#c0392b")
        self.tree.tag_configure("done", foreground="#8a8a8a")
        self.tree.grid(row=1, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(panel, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda _e: self.toggle_done())
        self.tree.bind("<Delete>", lambda _e: self.delete_task())

        # Кнопки действий над выбранной задачей
        actions = ttk.Frame(panel)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Выполнена / вернуть", command=self.toggle_done).pack(side="left")
        ttk.Button(actions, text="Удалить", command=self.delete_task).pack(side="left", padx=6)
        ttk.Button(actions, text="Удалить выполненные", command=self.clear_completed).pack(
            side="right"
        )

    # ------------------------------------------------------------ данные -> экран
    def refresh(self) -> None:
        """Перерисовывает таблицу с учётом поиска, фильтра и сортировки."""
        tasks = self.service.query(
            status=FILTERS[self.filter_var.get()],
            search=self.search_var.get(),
            sort_by=SORTS[self.sort_var.get()],
        )
        selection = self.tree.selection()
        selected_id = selection[0] if selection else None

        self.tree.delete(*self.tree.get_children())
        for task in tasks:
            tags = ()
            if task.done:
                tags = ("done",)
            elif task.is_overdue():
                tags = ("overdue",)
            self.tree.insert(
                "",
                tk.END,
                iid=task.id,
                tags=tags,
                values=(
                    "✓" if task.done else "",
                    task.title,
                    task.category,
                    task.priority.label,
                    format_date(task.due_date),
                ),
            )

        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
        if self.editing_id and not self.service.exists(self.editing_id):
            self.reset_form()
        self._update_stats()

    def _update_stats(self) -> None:
        s = self.service.stats()
        self.stats_var.set(
            f"Всего: {s['total']}   Активных: {s['active']}   "
            f"Выполнено: {s['done']}   Просрочено: {s['overdue']}"
        )

    # ------------------------------------------------------------ форма
    def _read_form(self) -> dict:
        return {
            "title": self.title_var.get(),
            "description": self.desc_text.get("1.0", "end-1c"),
            "due_date": parse_date(self.date_var.get()),
            "priority": PRIORITY_CHOICES[self.priority_var.get()],
            "category": self.category_var.get(),
        }

    def _load_into_form(self, task: Task) -> None:
        self.title_var.set(task.title)
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", task.description)
        self.date_var.set(format_date(task.due_date))
        self.priority_var.set(task.priority.label)
        self.category_var.set(task.category)
        self.editing_id = task.id
        self.mode_var.set("Редактирование задачи")
        self.save_btn.configure(state="normal")

    def reset_form(self) -> None:
        self.title_var.set("")
        self.desc_text.delete("1.0", tk.END)
        self.date_var.set("")
        self.priority_var.set(Priority.MEDIUM.label)
        self.category_var.set("")
        self.editing_id = None
        self.mode_var.set("Новая задача")
        self.save_btn.configure(state="disabled")
        self.tree.selection_remove(self.tree.selection())

    # ------------------------------------------------------------ действия
    def add_task(self) -> None:
        try:
            self.service.add(**self._read_form())
        except ValueError as error:
            messagebox.showwarning("Проверьте данные", str(error))
            return
        self.reset_form()
        self.refresh()

    def save_changes(self) -> None:
        if not self.editing_id:
            return
        try:
            self.service.update(self.editing_id, **self._read_form())
        except ValueError as error:
            messagebox.showwarning("Проверьте данные", str(error))
            return
        except TaskNotFoundError:
            self.reset_form()
            self.refresh()
            return
        self.refresh()

    def on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        task_id = selection[0]
        if task_id == self.editing_id:
            return  # эта задача уже открыта в форме
        try:
            self._load_into_form(self.service.get(task_id))
        except TaskNotFoundError:
            self.refresh()

    def _selected_id(self) -> Optional[str]:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def toggle_done(self) -> None:
        task_id = self._selected_id()
        if not task_id:
            messagebox.showinfo("Нет выбора", "Сначала выберите задачу в списке.")
            return
        self.service.toggle_done(task_id)
        self.refresh()

    def delete_task(self) -> None:
        task_id = self._selected_id()
        if not task_id:
            messagebox.showinfo("Нет выбора", "Сначала выберите задачу в списке.")
            return
        task = self.service.get(task_id)
        if messagebox.askyesno("Удаление", f"Удалить задачу «{task.title}»?"):
            self.service.delete(task_id)
            self.refresh()

    def clear_completed(self) -> None:
        count = self.service.stats()["done"]
        if not count:
            messagebox.showinfo("Нечего удалять", "Выполненных задач пока нет.")
            return
        if messagebox.askyesno("Удаление", f"Удалить все выполненные задачи ({count})?"):
            self.service.clear_completed()
            self.refresh()


def run(data_file: Union[str, Path] = DEFAULT_DATA_FILE) -> None:
    root = tk.Tk()
    service = TaskService(JsonStorage(data_file))
    TaskPlannerApp(root, service)
    root.mainloop()

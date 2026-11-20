"""Живые данные MeetMatch на диске: отзывы о знакомствах и анкеты «живого зала».

Требования, как к продакшен-хранилищу, но без базы данных (на хакатоне она не нужна):
  * атомарная запись — пишем во временный файл и подменяем одной операцией os.replace:
    при сбое посреди записи старый файл остаётся целым;
  * замок — несколько пользователей Streamlit пишут одновременно из разных потоков;
  * устойчивость — повреждённый файл не роняет приложение: он откладывается в сторону
    (*.corrupt-<время>), работа продолжается с пустого списка, событие пишется в лог.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from config import FEEDBACK_PATH, HALL_PATH, MAX_HALL_SIZE
from taxonomy import LEVELS

log = logging.getLogger("meetmatch")


class JsonListStore:
    """Список записей в одном JSON-файле."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._items: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError("ожидается список")
            return data
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
            backup = self.path.with_name(f"{self.path.name}.corrupt-{int(time.time())}")
            self.path.replace(backup)
            log.error("store_corrupt path=%s moved_to=%s error=%s", self.path, backup.name, e)
            return []

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            self._items = items
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._items)

    def append(self, item: dict) -> dict:
        with self._lock:
            self._write([*self._items, item])
        return item

    def clear(self) -> None:
        with self._lock:
            self._write([])


class FeedbackStore(JsonListStore):
    """Отзывы «познакомились / не подошло» — для дашборда организатора. Без имён: только id."""

    ACTIONS = {"met", "not_fit"}

    def __init__(self, path: Path = FEEDBACK_PATH):
        super().__init__(path)

    def add(self, action: str, candidate_id: str, goal: str) -> dict:
        if action not in self.ACTIONS:
            raise ValueError(f"неизвестное действие: {action}")
        item = self.append({"time": datetime.now().isoformat(timespec="seconds"), "action": action,
                            "candidate_id": candidate_id, "goal": goal})
        log.info("feedback action=%s candidate=%s goal=%s", action, candidate_id, goal)
        return item

    def stats(self) -> dict:
        items = self.all()
        met = sum(1 for e in items if e["action"] == "met")
        return {"total": len(items), "met": met, "not_fit": len(items) - met,
                "met_share": met / len(items) if items else None}


class HallStore(JsonListStore):
    """«Живой зал»: анкеты участников, которые разрешили показывать себя другим."""

    def __init__(self, path: Path = HALL_PATH):
        super().__init__(path)

    def join(self, q: dict, lang: str, guest_name: str) -> dict:
        """Превращает подготовленную анкету (matcher.prepare) в анкету базы и сохраняет её.
        Новые id уникальны и после очистки зала. Старые записи h001… читаются как прежде."""
        with self._lock:
            if len(self._items) >= MAX_HALL_SIZE:
                raise RuntimeError("живой зал переполнен")
            hid = f"h{uuid4().hex}"
            levels = q.get("inferred", {}).get("levels", []) if q["goal"] == "hire" else []
            profile = {
                "id": hid,
                "name": q.get("name") or f"{guest_name} {len(self._items) + 1}",
                "lang": lang, "role": q["role"], "experience": q["experience"],
                "stack": list(q["stack"]), "interests": list(q["interests"]), "about": q["about"],
                "goal": q["goal"], "seeking_roles": list(q["seeking_roles"]),
                "hire_levels": levels,
                "hire_exp_min": LEVELS[levels[0]][0] if levels else None,
                "hire_exp_max": LEVELS[levels[-1]][1] if levels else None,
                "company": None, "slots": list(q.get("slots") or []), "live": True,
            }
            self._write([*self._items, profile])
        log.info("hall_join id=%s goal=%s role=%s", hid, q["goal"], q["role"])
        return profile

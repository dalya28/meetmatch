"""Ближайшие мероприятия Алматы: анкету заполняют до события и заранее видят, с кем познакомиться.

Прототип:
  * события — из открытых анонсов (data/events.json, у каждого ссылка на источник);
  * участники каждого события — синтетические анкеты из общей базы. Кто «идёт» на событие,
    решает близость к его темам и ролям плюс стабильный случайный сдвиг (crc32), поэтому
    состав одинаков при каждом запуске и не зависит от порядка вызовов генератора;
  * участники живого зала попадают на то событие, к которому заполнили анкету.
"""
from __future__ import annotations

import json
import zlib
from datetime import date
from pathlib import Path

from config import DATA_DIR

EVENTS_PATH = DATA_DIR / "events.json"
DEFAULT_EVENT = "metu-ai-hackathon"  # анкеты живого зала без поля event — с хакатона, где запускали Wingman


def load_events(path: Path = EVENTS_PATH) -> list[dict]:
    events = json.loads(Path(path).read_text(encoding="utf-8"))
    return sorted(events, key=lambda e: (e["start"], e["id"]))


def upcoming(events: list[dict], today: date | None = None) -> list[dict]:
    """События, которые ещё не закончились: идущие сейчас и будущие."""
    today = (today or date.today()).isoformat()
    return [e for e in events if e["end"] >= today]


def _noise(event_id: str, profile_id: str) -> float:
    return zlib.crc32(f"{event_id}:{profile_id}".encode()) / 0xFFFFFFFF


def attendee_ids(event: dict, profiles: list[dict]) -> set[str]:
    """Кто из базы идёт на событие. Живые анкеты — только на своё событие."""
    synthetic = [p for p in profiles if not p.get("live")]
    live = {p["id"] for p in profiles if p.get("live") and p.get("event", DEFAULT_EVENT) == event["id"]}
    if event.get("all_profiles"):
        return {p["id"] for p in synthetic} | live
    topics, roles = set(event.get("topics", [])), set(event.get("roles", []))

    def score(p: dict) -> float:
        return (1.5 * len(topics & set(p["interests"])) + 2.0 * (p["role"] in roles)
                + 1.5 * _noise(event["id"], p["id"]))
    chosen = sorted(synthetic, key=lambda p: (-score(p), p["id"]))[:event["size"]]
    return {p["id"] for p in chosen} | live

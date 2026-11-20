"""Взаимный мэтч, Telegram и нетворкинг-бинго.

Взаимный мэтч: «Познакомиться» нажали оба — открывается контакт в Telegram.
  * Участник живого зала: взаимность — настоящая, по журналу нажатий (кто → кого).
  * Синтетический участник (демо): «отвечает» сам, с вероятностью, которая растёт с процентом
    совпадения. Решение стабильно (crc32 пары), чтобы при перезагрузке ответ не менялся.
    В интерфейсе это подписано как демо, у синтетических людей нет настоящего Telegram.

Бинго 3×3: задания вида «познакомьтесь с дизайнером». Клетка закрывается, когда вы нажимаете
«Познакомиться» с подходящим человеком. Задания берутся только такие, для которых на этом
событии среди ваших кандидатов есть хотя бы двое подходящих, — карточку всегда можно собрать.
"""
from __future__ import annotations

import re
import zlib

# ---------------------------------------------------------------- Telegram
TG_HANDLE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def clean_telegram(raw) -> str:
    """«@name», «t.me/name», «https://t.me/name» → «name». Неверный ник → пустая строка."""
    text = str(raw or "").strip()
    text = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", text, flags=re.IGNORECASE)
    text = text.lstrip("@").strip("/")
    return text if TG_HANDLE.match(text) else ""


def telegram_url(handle: str) -> str | None:
    handle = clean_telegram(handle)
    return f"https://t.me/{handle}" if handle else None


# ---------------------------------------------------------------- взаимность
def _unit(*parts: str) -> float:
    return zlib.crc32(":".join(parts).encode()) / 0xFFFFFFFF


def demo_accepts(me_key: str, pid: str, score: float) -> bool:
    """Синтетический участник соглашается тем охотнее, чем выше совпадение: 30% … 95%."""
    return _unit(me_key, pid) < min(0.95, 0.3 + 0.7 * max(score, 0.0))


def is_mutual(profile: dict, score: float, me_id: str | None, me_key: str, events: list[dict]) -> bool:
    if profile.get("live"):
        return bool(me_id) and any(
            e.get("action") == "met" and e.get("from") == profile["id"] and e.get("candidate_id") == me_id
            for e in events)
    return demo_accepts(me_key, profile["id"], score)


# ---------------------------------------------------------------- бинго
DEV = {"backend", "frontend", "fullstack", "mobile"}
DATA = {"ml", "data", "data_engineer", "analyst"}

BINGO_TASKS: dict[str, tuple[dict, callable]] = {
    "designer": ({"ru": "Дизайнер", "kk": "Дизайнер", "en": "A designer"}, lambda p: p["role"] == "designer"),
    "recruiter": ({"ru": "Рекрутер", "kk": "Рекрутер", "en": "A recruiter"}, lambda p: p["role"] == "recruiter"),
    "founder": ({"ru": "Основатель стартапа", "kk": "Стартап негізін қалаушы", "en": "A startup founder"},
                lambda p: p["role"] == "founder" or p["goal"] == "find_cofounder"),
    "student": ({"ru": "Студент", "kk": "Студент", "en": "A student"}, lambda p: p["role"] == "student"),
    "lead": ({"ru": "Тимлид или CTO", "kk": "Тимлид немесе CTO", "en": "A team lead or CTO"},
             lambda p: p["role"] == "lead"),
    "pm": ({"ru": "Продакт-менеджер", "kk": "Продакт-менеджер", "en": "A product manager"},
           lambda p: p["role"] == "pm"),
    "data": ({"ru": "Человек из данных или ML", "kk": "Деректер не ML маманы", "en": "Someone in data or ML"},
             lambda p: p["role"] in DATA),
    "dev": ({"ru": "Разработчик", "kk": "Әзірлеуші", "en": "A developer"}, lambda p: p["role"] in DEV),
    "veteran": ({"ru": "Опыт 10+ лет", "kk": "10+ жыл тәжірибе", "en": "10+ years of experience"},
                lambda p: p["experience"] >= 10),
    "rookie": ({"ru": "Опыт меньше года", "kk": "Бір жылдан аз тәжірибе", "en": "Under a year of experience"},
               lambda p: p["experience"] <= 1),
    "python": ({"ru": "Пишет на Python", "kk": "Python-да жазады", "en": "Writes Python"},
               lambda p: "python" in p["stack"]),
    "js": ({"ru": "Пишет на JavaScript", "kk": "JavaScript-те жазады", "en": "Writes JavaScript"},
           lambda p: bool({"javascript", "typescript", "react"} & set(p["stack"]))),
    "figma": ({"ru": "Работает в Figma", "kk": "Figma-да жұмыс істейді", "en": "Works in Figma"},
              lambda p: "figma" in p["stack"]),
    "fintech": ({"ru": "Кто-то из финтеха", "kk": "Финтехтен біреу", "en": "Someone from fintech"},
                lambda p: "fintech" in p["interests"]),
    "ai": ({"ru": "Фанат ИИ", "kk": "ЖИ жанкүйері", "en": "An AI fan"}, lambda p: "ai" in p["interests"]),
    "edtech": ({"ru": "Кто-то из EdTech", "kk": "EdTech-тен біреу", "en": "Someone from EdTech"},
               lambda p: "edtech" in p["interests"]),
    "ecommerce": ({"ru": "Кто-то из e-commerce", "kk": "E-commerce-тен біреу", "en": "Someone from e-commerce"},
                  lambda p: "ecommerce" in p["interests"]),
    "kazakh": ({"ru": "Анкета на казахском", "kk": "Сауалнамасы қазақша", "en": "Profile in Kazakh"},
               lambda p: p.get("lang") == "kk"),
    "english": ({"ru": "Анкета на английском", "kk": "Сауалнамасы ағылшынша", "en": "Profile in English"},
                lambda p: p.get("lang") == "en"),
    "mentor": ({"ru": "Ментор", "kk": "Тәлімгер", "en": "A mentor"}, lambda p: p["goal"] == "be_mentor"),
}
FREE = "free"  # центр: первое знакомство
FREE_LABEL = {"ru": "★ Первое знакомство", "kk": "★ Алғашқы таныстық", "en": "★ Your first meeting"}
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def bingo_label(task: str, lang: str) -> str:
    labels = FREE_LABEL if task == FREE else BINGO_TASKS[task][0]
    return labels.get(lang) or labels["ru"]


def bingo_reach(pool: list[dict]) -> dict[str, int]:
    """Сколько кандидатов подходит под каждое задание."""
    return {k: sum(1 for p in pool if test(p)) for k, (_, test) in BINGO_TASKS.items()}


def bingo_card(pool: list[dict], seed: str) -> list[str]:
    """9 клеток, центр — «первое знакомство». Сначала задания, для которых есть ≥ 2 кандидата."""
    reach = bingo_reach(pool)
    order = sorted(BINGO_TASKS, key=lambda k: (reach[k] < 2, reach[k] < 1, _unit(seed, k)))
    tasks = [k for k in order if reach[k] >= 1][:8]
    while len(tasks) < 8:  # совсем маленькое событие: добиваем самыми частыми заданиями
        tasks.append(next(k for k in sorted(BINGO_TASKS, key=lambda k: -reach[k]) if k not in tasks))
    return tasks[:4] + [FREE] + tasks[4:]


def bingo_tick(card: list[str], done: dict, profile: dict, reach: dict | None = None) -> list[int]:
    """Отмечает клетки за одно знакомство: центр (если ещё пуст) и одно подходящее задание —
    самое редкое из подходящих. Иначе частые клетки («разработчик») закрывались бы первыми
    и линия собиралась бы за три знакомства без всякой охоты."""
    new = []
    if "4" not in done:
        new.append(4)
    reach = reach or {}
    fits = [i for i, task in enumerate(card)
            if task != FREE and str(i) not in done and BINGO_TASKS[task][1](profile)]
    if fits:
        new.append(min(fits, key=lambda i: (reach.get(card[i], 0), i)))
    for i in new:
        done[str(i)] = profile.get("name", "")
    return new


def bingo_lines(done: dict) -> int:
    return sum(all(str(i) in done for i in line) for line in LINES)

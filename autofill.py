"""Анкета из текста за 10 секунд: человек вставляет «О себе» из LinkedIn или резюме.

Два уровня:
  1. Правила (всегда, без ключа): стек, интересы и роли — из того же разбора текста, что и подбор;
     цель, опыт и своя роль — по ключевым словам на русском, казахском и английском.
  2. Claude (если MEETMATCH_AI=1 и есть ANTHROPIC_API_KEY): структурированный ответ строго по схеме
     с нашими кодами ролей, стека и интересов. Любая ошибка — тихий откат на правила.

Перед отправкой в Claude из текста убираются e-mail и телефоны: для анкеты они не нужны.
"""
from __future__ import annotations

import json
import logging
import os
import re

from taxonomy import (ALIASES, GOALS, INTERESTS, ROLES, STACK, extract_tags, levels_in_text,
                      roles_from_stack)

log = logging.getLogger("meetmatch")
MAX_TEXT = 4000

GOAL_RULES = [  # порядок важен: «нанимаем» раньше «ищу работу», т. к. в вакансии бывает «ищем»
    ("hire", r"нанима|ищем [\w\s-]{0,30}?(разработ|дизайн|аналит|инженер|специалист|тестиров|в команду)|вакансия|"
             r"hiring|we.re looking for|join our team|маман іздейміз|жұмысқа аламыз|қызметкер іздейміз"),
    ("find_cofounder", r"кофаундер|сооснователь|co-?founder|партн[её]р в стартап|бірлескен құрылтайшы"),
    ("be_mentor", r"могу (по)?менторить|готов(а)? менторить|помогаю начинающим|ментор(ю)? джун|"
                  r"mentor(ing)? juniors|happy to mentor|тәлімгер бола аламын"),
    ("find_mentor", r"ищу ментора|нуж[её]н ментор|хочу ментора|looking for a mentor|need a mentor|"
                    r"тәлімгер іздеймін"),
    ("find_job", r"ищу работу|в поиске работы|открыт(а)? к предложениям|рассматриваю предложения|"
                 r"looking for (a )?(new )?(job|role|position)|open to work|open to opportunities|"
                 r"жұмыс іздеймін|жұмыс іздеп"),
]
RECRUITER = re.compile(r"рекрутер|recruit|talent acquisition|hr[- ]?(менеджер|manager|специалист)?\b|кадр",
                       re.IGNORECASE)
STUDENT = re.compile(r"студент|student|учусь|оқимын|бакалавр|курс[ае]? (кбту|ниш|университет)|university",
                     re.IGNORECASE)
SEEK = re.compile(r"ищу|ищем|looking for|seeking|нуж[её]н|іздеймін|іздейміз|іздеп", re.IGNORECASE)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(год|года|лет|years?|yrs?|жыл)", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s()-]{8,}\d")


def scrub(text: str) -> str:
    return PHONE.sub("[телефон]", EMAIL.sub("[email]", text or ""))[:MAX_TEXT]


def _roles_in_order(text: str) -> list[str]:
    """Роли в порядке первого упоминания: «Тимлид, пишу на Go» — сначала тимлид."""
    hits = [(m.start(), code) for code, rx in ALIASES["roles"].items() if (m := rx.search(text))]
    return [code for _, code in sorted(hits)]


def by_rules(text: str) -> dict:
    low = (text or "").lower()
    found = extract_tags(low)
    goal = next((g for g, rx in GOAL_RULES if re.search(rx, low)), "exchange")
    cut = SEEK.search(low)
    head, tail = (low[:cut.start()], low[cut.start():]) if cut else (low, "")
    own = _roles_in_order(head)  # о себе — до «ищу / looking for», о тех, кого ищут, — после
    wanted = _roles_in_order(tail)
    if goal == "hire":
        role = ("recruiter" if RECRUITER.search(head or low) else
                "founder" if "founder" in own else "lead")
        seeking = [r for r in wanted or own if r not in ("recruiter", role)]
    else:
        role = (own[0] if own else "student" if STUDENT.search(low)
                else (roles_from_stack(found["stack"]) or ["backend"])[0])
        seeking = [r for r in wanted if r != role] if goal == "find_cofounder" else []
    years = [int(m.group(1)) for m in YEARS.finditer(low) if int(m.group(1)) <= 40]
    levels = levels_in_text(low)
    if years:
        experience = max(years)
    elif levels and goal != "hire":
        experience = {"junior": 1, "middle": 3, "senior": 7}[levels[-1]]
    else:
        experience = 0 if role == "student" else 2
    return {"role": role, "experience": experience, "goal": goal,
            "stack": [s for s in STACK if s in found["stack"]],
            "interests": [i for i in INTERESTS if i in found["interests"]],
            "seeking_roles": seeking, "about": text.strip()[:600], "source": "rules"}


SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "enum": list(ROLES)},
        "experience": {"type": "integer"},
        "goal": {"type": "string", "enum": list(GOALS)},
        "stack": {"type": "array", "items": {"type": "string", "enum": list(STACK)}},
        "interests": {"type": "array", "items": {"type": "string", "enum": list(INTERESTS)}},
        "seeking_roles": {"type": "array", "items": {"type": "string", "enum": list(ROLES)}},
    },
    "required": ["role", "experience", "goal", "stack", "interests", "seeking_roles"],
    "additionalProperties": False,
}
SYSTEM = ("You fill in a networking-event profile from a person's self-description (LinkedIn About or CV), "
          "written in Russian, Kazakh or English. Use only facts stated in the text. "
          "role: the person's own role. goal: find_job if they look for work, hire if they hire, "
          "find_mentor / be_mentor for mentoring, find_cofounder for co-founders, otherwise exchange. "
          "experience: total years of professional experience as an integer (0 for students). "
          "seeking_roles: only roles they want to hire or partner with. Leave lists empty when unsure.")
FALLBACK_OK = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2"}


def by_claude(text: str, key: str, model: str) -> dict:
    from anthropic import Anthropic  # ленивый импорт: без ИИ библиотека не нужна
    extra = {"fallbacks": "default"} if model in FALLBACK_OK else {}
    with Anthropic(api_key=key, timeout=15, max_retries=0) as client:
        result = client.beta.messages.create(
            model=model, max_tokens=4000, system=SYSTEM,
            betas=["server-side-fallback-2026-07-01"] if extra else [],
            messages=[{"role": "user", "content": scrub(text)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            extra_body=extra or None)
    if result.stop_reason != "end_turn":
        raise ValueError(f"stop_reason={result.stop_reason}")
    data = json.loads(next(b.text for b in result.content if b.type == "text"))
    data["experience"] = min(max(int(data["experience"]), 0), 40)
    return {**data, "about": text.strip()[:600], "source": "claude"}


def autofill(text: str) -> dict:
    """Возвращает поля анкеты. Claude — только при MEETMATCH_AI=1 и ключе; иначе или при ошибке — правила."""
    text = (text or "").strip()[:MAX_TEXT]
    key = os.getenv("ANTHROPIC_API_KEY") if os.getenv("MEETMATCH_AI") == "1" else None
    if key:
        try:
            return by_claude(text, key, os.getenv("MEETMATCH_MODEL", "claude-opus-5-5"))
        except Exception as exc:  # сеть, лимиты, отказ, нет библиотеки — анкета всё равно заполнится
            log.warning("autofill_claude_fallback error_type=%s", type(exc).__name__)
    return by_rules(text)

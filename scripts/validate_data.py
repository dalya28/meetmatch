"""Проверка качества базы анкет MeetMatch (контракт данных).

Что проверяется:
  1. Схема — JSON Schema строится из справочников taxonomy.py, поэтому не расходится с кодом;
     сохраняется в data/profiles.schema.json.
  2. Бизнес-правила — у нанимающих есть вакансия и уровень, ментор опытнее подопечного и т.д.
  3. Уникальность — id, имена, тексты «о себе».
  4. Приватность — в текстах нет email, телефонов, ссылок и @-никнеймов.
  5. CSV и JSON содержат одно и то же.
  6. Покрытие — для каждой пары «цель × роль» есть ≥ 5 взаимных и подходящих по роли кандидатов.

Пишет отчёты reports/data_profile.md и reports/data_sample.md (20 случайных анкет для ручной проверки).

Запуск из корня проекта:  python scripts/validate_data.py      (код выхода 1 — есть ошибки)
Новая выборка для ручной проверки:  python scripts/validate_data.py --new-sample
"""
from __future__ import annotations

import csv
import json
import random
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taxonomy import (EVENT_SLOTS, GOAL_MATCH, GOALS, HIREABLE_ROLES, INTERESTS, LANGS,  # noqa: E402
                      LEVELS, ROLES, STACK, effective_roles, goal_label, interest_label,
                      role_label, role_similarity, stack_label)

DATA = ROOT / "data"
REPORTS = ROOT / "reports"
MIN_COVERAGE = 5
PII = re.compile(r"[\w.+-]+@[\w-]+\.\w+|\+?\d[\d\s()-]{8,}\d|https?://|www\.|(?<!\w)@\w{3,}", re.I)


# ---------------------------------------------------------------- 1. схема
def build_schema() -> dict:
    str_list = lambda enum, lo=0, hi=None: {  # noqa: E731
        "type": "array", "items": {"enum": enum}, "uniqueItems": True, "minItems": lo,
        **({"maxItems": hi} if hi else {})}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MeetMatch participant profile",
        "type": "array",
        "minItems": 100,
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "name", "lang", "role", "experience", "stack", "interests", "about",
                         "goal", "seeking_roles", "hire_levels", "hire_exp_min", "hire_exp_max",
                         "company", "slots"],
            "properties": {
                "id": {"type": "string", "pattern": r"^p\d{3}$"},
                "name": {"type": "string", "pattern": r"^[^\W\d_]+(-[^\W\d_]+)? [^\W\d_]+(-[^\W\d_]+)?$"},
                "lang": {"enum": list(LANGS)},
                "role": {"enum": list(ROLES)},
                "experience": {"type": "integer", "minimum": 0, "maximum": 40},
                "stack": str_list(list(STACK), 2, 6),
                "interests": str_list(list(INTERESTS), 1, 4),
                "about": {"type": "string", "minLength": 30, "maxLength": 400},
                "goal": {"enum": list(GOALS)},
                "seeking_roles": str_list(HIREABLE_ROLES + ["founder"]),
                "hire_levels": str_list(list(LEVELS)),
                "hire_exp_min": {"type": ["integer", "null"], "minimum": 0},
                "hire_exp_max": {"type": ["integer", "null"], "minimum": 0},
                "company": {"type": ["string", "null"]},
                "slots": str_list(EVENT_SLOTS, 1),
            },
        },
    }


# ---------------------------------------------------------------- 2–5. правила
def check_rules(profiles: list[dict]) -> list[str]:
    errors = []
    for p in profiles:
        pid, goal = p["id"], p["goal"]
        if goal == "hire":
            if not p["seeking_roles"] or not p["hire_levels"]:
                errors.append(f"{pid}: у нанимающего нет вакансии или уровня")
            if p["hire_exp_min"] is None or p["hire_exp_min"] >= p["hire_exp_max"]:
                errors.append(f"{pid}: неверный диапазон опыта вакансии")
            if not p["company"]:
                errors.append(f"{pid}: у нанимающего нет компании")
        else:
            if p["hire_levels"] or p["hire_exp_min"] is not None:
                errors.append(f"{pid}: поля вакансии у не-нанимающего")
        if goal == "find_cofounder" and not p["seeking_roles"]:
            errors.append(f"{pid}: кофаундер не указал, кого ищет")
        if goal not in ("hire", "find_cofounder") and p["seeking_roles"]:
            errors.append(f"{pid}: «кого ищу» у цели {goal}")
        if goal == "be_mentor" and p["experience"] < 5:
            errors.append(f"{pid}: ментор с опытом меньше 5 лет")
        if goal == "find_mentor" and p["experience"] > 3:
            errors.append(f"{pid}: ищущий ментора с опытом больше 3 лет")
        if p["role"] == "student" and p["experience"] != 0:
            errors.append(f"{pid}: у студента коммерческий опыт")
        if PII.search(p["about"]) or PII.search(p["name"]):
            errors.append(f"{pid}: похоже на персональные данные (email, телефон, ссылка, @ник)")
    for field in ("id", "name", "about"):
        dup = [v for v, c in Counter(p[field] for p in profiles).items() if c > 1]
        if dup:
            errors.append(f"повторяются значения поля {field}: {dup[:3]}")
    return errors


def check_csv(profiles: list[dict]) -> list[str]:
    with open(DATA / "profiles.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != len(profiles):
        return [f"CSV: {len(rows)} строк, JSON: {len(profiles)} анкет"]
    errors = []
    for row, p in zip(rows, profiles):
        for k, v in p.items():
            expected = ";".join(v) if isinstance(v, list) else ("" if v is None else str(v))
            if row.get(k) != expected:
                errors.append(f"CSV и JSON расходятся: {p['id']}.{k}")
                break
    return errors


# ---------------------------------------------------------------- 6. покрытие
def relevant(goal: str, persona_role: str, c: dict) -> bool:
    """Подходит ли кандидат c участнику с ролью persona_role и целью goal (по роли)."""
    if c["goal"] not in GOAL_MATCH[goal]:
        return False
    if goal == "find_job":
        return any(role_similarity(persona_role, s) >= 0.6 for s in c["seeking_roles"])
    if goal == "find_cofounder":
        groups = {ROLES[persona_role]["group"], ROLES[c["role"]]["group"]}
        return "tech" in groups and bool(groups & {"product", "business"})
    c_roles = effective_roles(c["role"], c["stack"])
    return any(role_similarity(persona_role, r) >= 0.6 for r in c_roles)


def coverage(profiles: list[dict]) -> dict[str, dict[str, int]]:
    personas = HIREABLE_ROLES + ["founder"]
    table: dict[str, dict[str, int]] = {}
    for goal in GOALS:
        table[goal] = {}
        for role in personas:
            if goal == "hire" and role == "founder":
                continue
            table[goal][role] = sum(relevant(goal, role, c) for c in profiles)
    return table


def coverage_errors(table) -> list[str]:
    errors = []
    for goal, row in table.items():
        for role, n in row.items():
            if role == "founder" and goal in ("find_job", "be_mentor"):
                continue  # редкий сценарий: фаундер подбирается по стеку, своя роль — не специализация
            if n < MIN_COVERAGE:
                errors.append(f"покрытие: «{goal_label(goal, 'ru')}» × «{role_label(role, 'ru')}» = {n} < {MIN_COVERAGE}")
    return errors


# ---------------------------------------------------------------- отчёты
def female_names() -> set[str]:
    from scripts.generate_profiles import FEMALE, translit  # те же списки, что у генератора
    return set(FEMALE) | {translit(n) for n in FEMALE}


def write_profile(profiles: list[dict], table, errors: list[str]) -> None:
    lines = ["# Профиль базы анкет", "",
             "Сгенерировано `scripts/validate_data.py`. Не редактировать вручную.", "",
             f"**Анкет:** {len(profiles)} · **ошибок проверки:** {len(errors)}", ""]
    by_goal = Counter(p["goal"] for p in profiles)
    lines += ["## Цели и опыт", "", "| Цель | Анкет | Опыт: мин | медиана | макс |", "|---|---|---|---|---|"]
    for g in GOALS:
        exp = [p["experience"] for p in profiles if p["goal"] == g]
        lines.append(f"| {goal_label(g, 'ru')} | {by_goal[g]} | {min(exp)} | {statistics.median(exp):g} | {max(exp)} |")
    langs = Counter(p["lang"] for p in profiles)
    fem = female_names()
    women = sum(p["name"].split()[0] in fem for p in profiles)
    lines += ["", "## Языки и состав", "",
              f"- Языки анкет: русский {langs['ru']}, казахский {langs['kk']}, английский {langs['en']}.",
              f"- Женских имён: {women} из {len(profiles)} ({round(100 * women / len(profiles))}%).", "",
              "## Роли", "", "| Роль | Анкет |", "|---|---|"]
    for r, n in Counter(p["role"] for p in profiles).most_common():
        lines.append(f"| {role_label(r, 'ru')} | {n} |")
    stack = Counter(s for p in profiles for s in p["stack"])
    interests = Counter(i for p in profiles for i in p["interests"])
    lines += ["", "## Стек и интересы", "",
              "Топ-10 стека: " + ", ".join(f"{stack_label(s)} ({n})" for s, n in stack.most_common(10)),
              "", "Топ-10 интересов: " + ", ".join(f"{interest_label(i, 'ru')} ({n})" for i, n in interests.most_common(10)),
              "", "Не используются ни в одной анкете: "
              + (", ".join([stack_label(s) for s in STACK if s not in stack] +
                           [interest_label(i, 'ru') for i in INTERESTS if i not in interests]) or "нет"), ""]
    roles = list(next(iter(table.values())).keys())
    lines += [f"## Покрытие: сколько взаимных и подходящих по роли кандидатов найдётся (нужно ≥ {MIN_COVERAGE})", "",
              "| Роль участника | " + " | ".join(goal_label(g, "ru") for g in GOALS) + " |",
              "|---|" + "---|" * len(GOALS)]
    for r in roles:
        cells = []
        for g in GOALS:
            n = table[g].get(r)
            cells.append("—" if n is None else (f"**{n}** ⚠️" if n < MIN_COVERAGE else str(n)))
        lines.append(f"| {role_label(r, 'ru')} | " + " | ".join(cells) + " |")
    if errors:
        lines += ["", "## Ошибки", ""] + [f"- {e}" for e in errors]
    (REPORTS / "data_profile.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sample(profiles: list[dict]) -> None:
    sample = random.Random(7).sample(profiles, 20)
    lines = ["# 20 случайных анкет для ручной проверки", "",
             "Отметьте ✅ / ❌: правдоподобна ли анкета (роль, опыт, стек и текст сочетаются).", "",
             "| ✅/❌ | id | Цель | Роль, опыт | Стек | О себе |", "|---|---|---|---|---|---|"]
    for p in sample:
        lines.append(f"|  | {p['id']} | {goal_label(p['goal'], 'ru')} | {role_label(p['role'], 'ru')}, "
                     f"{p['experience']} | {', '.join(stack_label(s) for s in p['stack'])} | {p['about']} |")
    (REPORTS / "data_sample.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- точка входа
def validate(new_sample: bool = False) -> tuple[list[str], dict]:
    """`new_sample=True` пересоздаёт reports/data_sample.md. По умолчанию файл не трогаем, если он
    есть: в нём ручные отметки команды (их уже однажды стёр прогон тестов)."""
    profiles = json.loads((DATA / "profiles.json").read_text(encoding="utf-8"))
    schema = build_schema()
    (DATA / "profiles.schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=1), encoding="utf-8")
    validator = jsonschema.Draft202012Validator(schema)
    errors = [f"схема: {'/'.join(map(str, e.path))}: {e.message}" for e in validator.iter_errors(profiles)]
    errors += check_rules(profiles) + check_csv(profiles)
    table = coverage(profiles)
    errors += coverage_errors(table)
    REPORTS.mkdir(exist_ok=True)
    write_profile(profiles, table, errors)
    if new_sample or not (REPORTS / "data_sample.md").exists():
        write_sample(profiles)
    return errors, {"profiles": len(profiles)}


if __name__ == "__main__":
    errs, info = validate(new_sample="--new-sample" in sys.argv)
    for e in errs:
        print("ОШИБКА:", e)
    print(f"Проверено анкет: {info['profiles']}. Ошибок: {len(errs)}. "
          f"Отчёты: reports/data_profile.md, reports/data_sample.md")
    sys.exit(1 if errs else 0)

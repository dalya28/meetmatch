"""Прогон тестовых анкет «как у жюри»: топ-5 с объяснениями в reports/review.md.

Запуск из корня проекта:  python scripts/review.py
Файл удобно открыть всей командой и отметить, какие рекомендации подходят.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matcher import Matcher, load_profiles, prepare  # noqa: E402
from taxonomy import goal_label, interest_label, role_label, stack_label  # noqa: E402


def main() -> None:
    matcher = Matcher(load_profiles())
    cases = json.loads((ROOT / "tests" / "jury_profiles.json").read_text(encoding="utf-8"))
    lines = ["# Проверка подбора на тестовых анкетах", ""]
    worst = 0.0
    for case in cases:
        lang = case.get("lang", "ru")
        q = prepare(case)
        t0 = time.perf_counter()
        recs = matcher.recommend(q, lang=lang)
        dt = time.perf_counter() - t0
        worst = max(worst, dt)
        lines += [f"## {case['case']}", "",
                  f"**Анкета:** {role_label(q['role'], 'ru')}, {q['experience']} г., "
                  f"цель — {goal_label(q['goal'], 'ru')}; стек: "
                  f"{', '.join(stack_label(s) for s in q['stack']) or '—'}; интересы: "
                  f"{', '.join(interest_label(i, 'ru') for i in q['interests']) or '—'}",
                  f"«{q['about']}»", "",
                  f"Из текста добавлено: {q['inferred']} · время: {dt * 1000:.0f} мс", "",
                  "| # | Кто | Цель | Опыт | Совп. | Объяснение | Первая фраза |",
                  "|---|---|---|---|---|---|---|"]
        for i, m in enumerate(recs, 1):
            p = m.profile
            who = f"{p['name']}, {role_label(p['role'], 'ru')}"
            lines.append(f"| {i} | {who} | {goal_label(p['goal'], 'ru')} | {p['experience']} | "
                         f"{m.score:.2f} | {m.explanation} | {m.icebreaker} |")
        lines.append("")
    lines.append(f"Самый долгий подбор: {worst * 1000:.0f} мс")
    out = ROOT / "reports" / "review.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Готово: {out} (самый долгий подбор {worst * 1000:.0f} мс)")


if __name__ == "__main__":
    main()

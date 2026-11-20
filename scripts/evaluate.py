"""Офлайн-оценка качества подбора MeetMatch по ручной разметке.

    python scripts/evaluate.py pool   собрать пул кандидатов для разметки → tests/labels.csv
    python scripts/evaluate.py eval   метрики, базовые линии, абляция, подбор весов → reports/evaluation.md

Методика:
  * Пулинг (как на TREC): размечаем объединение топ-5 нескольких систем — текущей, вариантов без
    каждого компонента, «только роль», случайной и без взаимности. Тогда сравнение систем честное.
  * Разметка 0/1/2 по рубрике (docs/04-evaluation.md). Кандидаты, нарушающие взаимность целей,
    автоматически получают 0 — это прямое требование кейса.
  * Метрики: P@5 (доля подходящих, оценка ≥ 1), строгая P@5 (оценка 2), nDCG@5 (2^оценка − 1),
    «≥ 3 из 5» — ровно то, что проверяет жюри.
  * Подбор весов перебором по сетке с шагом 0.1 и 3-кратной кросс-валидацией по анкетам.
    Неразмеченный кандидат в топ-5 считается неподходящим (консервативно), доля размеченных — judged@5.
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matcher import WEIGHTS, Matcher, load_profiles, prepare, score_parts  # noqa: E402
from taxonomy import (GOAL_MATCH, goal_label, interest_label, role_label,  # noqa: E402
                      stack_label)

LABELS = ROOT / "tests" / "labels.csv"
MANUAL = ROOT / "tests" / "labels_manual.csv"
REPORT = ROOT / "reports" / "evaluation.md"
COMPONENTS = list(WEIGHTS)
COMPONENT_RU = {"role": "роль", "stack": "стек", "experience": "опыт", "interests": "интересы", "text": "текст «о себе»"}

matcher = Matcher(load_profiles())


def load_cases() -> list[dict]:
    raw = json.loads((ROOT / "tests" / "jury_profiles.json").read_text(encoding="utf-8"))
    return [{**c, "case_id": f"j{i:02d}", "q": prepare(c)} for i, c in enumerate(raw, 1)]


def normalize(w: dict) -> dict:
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def top5(q: dict, weights: dict | None = None, reciprocity: bool = True) -> list[str]:
    return [m.profile["id"] for m in matcher.recommend(q, weights=weights, reciprocity=reciprocity)]


def random5(q: dict, seed: str) -> list[str]:
    valid = [c["id"] for c in matcher.profiles
             if c["goal"] in GOAL_MATCH[q["goal"]] and score_parts(q, c, 0.0) is not None]
    return random.Random(seed).sample(valid, min(5, len(valid)))


def systems() -> dict:
    s = {"MeetMatch (текущие веса)": lambda c: top5(c["q"])}
    for comp in COMPONENTS:
        w = normalize({k: (0.0 if k == comp else v) for k, v in WEIGHTS.items()})
        s[f"без компонента «{COMPONENT_RU[comp]}»"] = (lambda w: lambda c: top5(c["q"], w))(w)
    s["только роль"] = lambda c: top5(c["q"], {k: (1.0 if k == "role" else 0.0) for k in WEIGHTS})
    s["случайные 5 (со взаимностью)"] = lambda c: random5(c["q"], c["case_id"])
    s["без взаимности целей"] = lambda c: top5(c["q"], reciprocity=False)
    return s


# ---------------------------------------------------------------- пул для разметки
def summary(p: dict) -> str:
    parts = [f"{role_label(p['role'], 'ru')}, {p['experience']} л.", f"цель: {goal_label(p['goal'], 'ru')}"]
    if p.get("seeking_roles"):
        parts.append("ищет: " + ", ".join(role_label(r, "ru") for r in p["seeking_roles"]))
    if p.get("hire_levels"):
        parts.append("уровень: " + ", ".join(p["hire_levels"]))
    parts.append("стек: " + ", ".join(stack_label(s) for s in p["stack"]))
    parts.append("интересы: " + ", ".join(interest_label(i, "ru") for i in p["interests"]))
    return "; ".join(parts)


def read_labels(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if None in r:  # запятые в пояснении без кавычек — склеиваем обратно
                r["reason"] = ",".join([r.get("reason") or ""] + r.pop(None))
            out[(r["case_id"], r["candidate_id"])] = r
    return out


def cmd_pool() -> None:
    cases = load_cases()
    existing = read_labels(LABELS)
    manual = read_labels(MANUAL)
    rows, dump = [], ["# Пул для разметки", ""]
    for c in cases:
        q = c["q"]
        ids: list[str] = []
        for fn in systems().values():
            for pid in fn(c):
                if pid not in ids:
                    ids.append(pid)
        dump += [f"## {c['case_id']} {c['case']}", f"Анкета: {summary(q)}; о себе: «{q['about']}»", ""]
        for pid in ids:
            p = matcher.by_id[pid]
            reciprocal = p["goal"] in GOAL_MATCH[q["goal"]]
            key = (c["case_id"], pid)
            # оценка в labels.csv (её могла поправить команда) важнее первичной разметки
            old = existing.get(key, {})
            if not old.get("label"):
                old = manual.get(key, {})
            label, reason = old.get("label", ""), old.get("reason", "")
            # анкета кандидата изменилась после разметки (например, поправили стек) — оценку пересматриваем
            if existing.get(key, {}).get("candidate") not in (None, "", summary(p)):
                label, reason = "", f"анкета изменилась; прежняя оценка {old.get('label', '?')}: {reason}"
            if not reciprocal:
                label, reason = "0", "нарушена взаимность целей (авто)"
            rows.append({"case_id": c["case_id"], "case": c["case"], "candidate_id": pid,
                         "candidate": summary(p), "label": label, "reason": reason})
            if reciprocal:
                dump.append(f"- {pid} [{label or '?'}] {summary(p)}")
        dump.append("")
    with open(LABELS, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (ROOT / "reports" / "pool.md").write_text("\n".join(dump), encoding="utf-8")
    todo = sum(1 for r in rows if r["label"] == "")
    print(f"Пул: {len(rows)} пар, без оценки: {todo}. Файлы: tests/labels.csv, reports/pool.md")


# ---------------------------------------------------------------- метрики
def metrics(ranked: list[str], case_id: str, labels: dict) -> dict:
    rel = [labels.get((case_id, pid)) for pid in ranked[:5]]
    judged = sum(r is not None for r in rel) / 5
    rel = [r or 0 for r in rel]
    ideal = sorted((v for (cid, _), v in labels.items() if cid == case_id), reverse=True)[:5]
    dcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(rel))
    idcg = sum((2 ** r - 1) / math.log2(i + 2) for i, r in enumerate(ideal)) or 1
    good = sum(r >= 1 for r in rel)
    return {"p5": good / 5, "strict": sum(r == 2 for r in rel) / 5, "ndcg": dcg / idcg,
            "hit3": float(good >= 3), "judged": judged}


def evaluate(fn, cases, labels) -> dict:
    per = [metrics(fn(c), c["case_id"], labels) for c in cases]
    return {k: statistics.mean(m[k] for m in per) for k in per[0]} | {"per_case": per}


def grid(step: float = 0.1):
    n = round(1 / step)
    for combo in itertools.product(range(n + 1), repeat=len(COMPONENTS) - 1):
        if sum(combo) <= n:
            vals = list(combo) + [n - sum(combo)]
            yield {k: v / n for k, v in zip(COMPONENTS, vals)}


def cmd_eval() -> None:
    cases = load_cases()
    labels = {k: int(v["label"]) for k, v in read_labels(LABELS).items() if v["label"] != ""}
    missing = sum(1 for v in read_labels(LABELS).values() if v["label"] == "")
    lines = ["# Отчёт об оценке качества", "", "Сгенерировано `scripts/evaluate.py eval`. Не редактировать вручную.", "",
             f"Анкет «как у жюри»: {len(cases)} · размеченных пар: {len(labels)} · без оценки: {missing}", ""]

    # 1. системы
    results = {name: evaluate(fn, cases, labels) for name, fn in systems().items()}
    lines += ["## Сравнение систем", "",
              "| Система | P@5 | строгая P@5 | nDCG@5 | «≥ 3 из 5» | размечено в топ-5 |",
              "|---|---|---|---|---|---|"]
    for name, r in results.items():
        lines.append(f"| {name} | {r['p5']:.2f} | {r['strict']:.2f} | {r['ndcg']:.3f} | "
                     f"{r['hit3'] * 100:.0f}% | {r['judged'] * 100:.0f}% |")

    # 2. по целям
    cur = results["MeetMatch (текущие веса)"]
    lines += ["", "## Текущая система по целям", "", "| Цель | Анкет | P@5 | nDCG@5 | «≥ 3 из 5» |", "|---|---|---|---|---|"]
    by_goal: dict[str, list] = {}
    for c, m in zip(cases, cur["per_case"]):
        by_goal.setdefault(c["q"]["goal"], []).append(m)
    for g, ms in by_goal.items():
        lines.append(f"| {goal_label(g, 'ru')} | {len(ms)} | {statistics.mean(m['p5'] for m in ms):.2f} | "
                     f"{statistics.mean(m['ndcg'] for m in ms):.3f} | "
                     f"{statistics.mean(m['hit3'] for m in ms) * 100:.0f}% |")

    # 3. подбор весов с кросс-валидацией
    folds = [[c for i, c in enumerate(cases) if i % 3 == f] for f in range(3)]
    configs = list(grid())
    cache: dict = {}

    def score(w, subset):
        key = tuple(w.values())
        if key not in cache:
            cache[key] = {c["case_id"]: metrics(top5(c["q"], w), c["case_id"], labels) for c in cases}
        ms = [cache[key][c["case_id"]] for c in subset]
        return statistics.mean(m["ndcg"] for m in ms), statistics.mean(m["p5"] for m in ms), \
            statistics.mean(m["judged"] for m in ms)

    cv_rows, cv_new, cv_cur = [], [], []
    for f in range(3):
        train = [c for i, fold in enumerate(folds) if i != f for c in fold]
        best = max(configs, key=lambda w: score(w, train)[:2])
        new_t, cur_t = score(best, folds[f]), score(WEIGHTS, folds[f])
        cv_new.append(new_t[0])
        cv_cur.append(cur_t[0])
        cv_rows.append(f"| {f + 1} | {', '.join(f'{v:.1f}' for v in best.values())} | {cur_t[0]:.3f} | "
                       f"{new_t[0]:.3f} | {new_t[2] * 100:.0f}% |")
    best_all = max(configs, key=lambda w: score(w, cases)[:2])
    b = score(best_all, cases)
    lines += ["", "## Подбор весов: перебор по сетке (шаг 0.1, " + f"{len(configs)} вариантов) и 3-кратная кросс-валидация", "",
              f"Порядок весов: {', '.join(COMPONENT_RU[c] for c in COMPONENTS)}.", "",
              "| Фолд | Лучшие веса на обучении | nDCG@5 текущих на тесте | nDCG@5 новых на тесте | размечено |",
              "|---|---|---|---|---|"] + cv_rows
    lines += ["", f"Среднее на тестовых фолдах: текущие **{statistics.mean(cv_cur):.3f}**, "
                  f"подобранные **{statistics.mean(cv_new):.3f}**.",
              f"Лучшие веса на всех анкетах: {', '.join(f'{COMPONENT_RU[k]} {v:.1f}' for k, v in best_all.items())} — "
              f"nDCG@5 {b[0]:.3f}, P@5 {b[1]:.2f}, размечено {b[2] * 100:.0f}%."]

    # 4. разбор ошибок текущей системы
    lines += ["", "## Разбор ошибок текущей системы (оценка 0 или без оценки в топ-5)", ""]
    reasons = read_labels(LABELS)
    errors = 0
    for c in cases:
        for pid in top5(c["q"]):
            lab = labels.get((c["case_id"], pid))
            if lab in (None, 0):
                errors += 1
                r = reasons.get((c["case_id"], pid), {})
                lines.append(f"- **{c['case_id']} {c['case']}** → {pid}: {summary(matcher.by_id[pid])}. "
                             f"Оценка: {lab if lab is not None else 'нет'}. {r.get('reason', '')}")
    if not errors:
        lines.append("Ошибок нет.")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:30]))
    print(f"\nПолный отчёт: {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    {"pool": cmd_pool, "eval": cmd_eval}[sys.argv[1] if len(sys.argv) > 1 else "eval"]()

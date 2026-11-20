"""Нагрузочная проверка подбора: сколько длится подбор на 276 / 1 000 / 5 000 / 10 000 анкет.

    python scripts/benchmark.py   → reports/benchmark.md
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matcher import Matcher, load_profiles  # noqa: E402

BASE = load_profiles()
SIZES = [len(BASE), 1000, 5000, 10000]
QUERIES = BASE[:50]


def scaled(n: int) -> list[dict]:
    return [{**BASE[i % len(BASE)], "id": f"s{i:05d}"} for i in range(n)]


def main() -> None:
    rows = []
    for n in SIZES:
        t0 = time.perf_counter()
        m = Matcher(scaled(n))
        build = time.perf_counter() - t0
        times = []
        for q in QUERIES:
            t0 = time.perf_counter()
            m.recommend(q)
            times.append((time.perf_counter() - t0) * 1000)
        times.sort()
        p95 = times[int(0.95 * len(times)) - 1]
        rows.append((n, build, statistics.median(times), p95, times[-1]))
        print(f"{n:>6} анкет: индекс {build:.2f} с, подбор медиана {statistics.median(times):.1f} мс, "
              f"p95 {p95:.1f} мс, максимум {times[-1]:.1f} мс")
    lines = ["# Нагрузочная проверка подбора", "", "Сгенерировано `scripts/benchmark.py`. "
             f"{len(QUERIES)} запросов на каждый размер базы, один поток.", "",
             "| Анкет в базе | Построение индекса | Подбор: медиана | p95 | максимум |", "|---|---|---|---|---|"]
    lines += [f"| {n} | {b:.2f} с | {med:.1f} мс | {p95:.1f} мс | {mx:.1f} мс |" for n, b, med, p95, mx in rows]
    lines += ["", "Требование кейса: подбор для одного участника быстрее 3 с (3000 мс)."]
    (ROOT / "reports" / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

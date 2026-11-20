"""Регрессия качества по ручной разметке (tests/labels.csv, методика — docs/04-evaluation.md).

Если тест падает с judged < 0.95, в топ-5 появились неразмеченные кандидаты:
запустите `python scripts/evaluate.py pool`, разметьте пустые строки и повторите.
"""
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = sys.argv[:1]

import scripts.evaluate as ev  # noqa: E402


def _current():
    cases = ev.load_cases()
    labels = {k: int(v["label"]) for k, v in ev.read_labels(ev.LABELS).items() if v["label"] != ""}
    per = [ev.metrics(ev.top5(c["q"]), c["case_id"], labels) for c in cases]
    return {k: statistics.mean(m[k] for m in per) for k in per[0]}, per


def test_quality_on_hand_labels():
    mean, per = _current()
    assert mean["judged"] >= 0.95, "в топ-5 есть неразмеченные кандидаты — доразметьте пул"
    assert mean["p5"] >= 0.90          # ≥ 4.5 подходящих из 5 в среднем
    assert mean["ndcg"] >= 0.90
    assert all(m["hit3"] == 1.0 for m in per), "есть анкета, где подходящих меньше 3 из 5"


def test_reciprocity_beats_baselines():
    cases = ev.load_cases()
    labels = {k: int(v["label"]) for k, v in ev.read_labels(ev.LABELS).items() if v["label"] != ""}
    ours = statistics.mean(ev.metrics(ev.top5(c["q"]), c["case_id"], labels)["p5"] for c in cases)
    no_recip = statistics.mean(ev.metrics(ev.top5(c["q"], reciprocity=False), c["case_id"], labels)["p5"]
                               for c in cases)
    assert ours - no_recip >= 0.3

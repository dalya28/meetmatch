"""Проверки Wingman: база анкет, взаимность целей, скорость, качество и тексты.

Запуск из корня проекта:  python -m pytest -q
"""
import json
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matcher import (Matcher, load_booths, load_profiles, plan_meetings, prepare,  # noqa: E402
                     recommend_booths)
from taxonomy import GOAL_MATCH, GOALS, LANGS  # noqa: E402

PROFILES = load_profiles()
MATCHER = Matcher(PROFILES)
JURY = json.loads((ROOT / "tests" / "jury_profiles.json").read_text(encoding="utf-8"))
SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def _check_reciprocity(q: dict, recs) -> None:
    for m in recs:
        c = m.profile
        assert c["goal"] in GOAL_MATCH[q["goal"]], (q["goal"], c["goal"])
        if q["goal"] == "find_mentor":
            assert c["experience"] > q["experience"]
        if q["goal"] == "be_mentor":
            assert c["experience"] < q["experience"]


def test_dataset_is_complete():
    assert len(PROFILES) >= 100
    assert len({p["id"] for p in PROFILES}) == len(PROFILES)
    assert len({p["name"] for p in PROFILES}) == len(PROFILES)
    for p in PROFILES:
        for f in ("name", "role", "stack", "interests", "about", "goal"):
            assert p[f], (p["id"], f)
        assert p["goal"] in GOALS
        assert isinstance(p["experience"], int)
    for goal, wanted in GOAL_MATCH.items():
        assert sum(p["goal"] in wanted for p in PROFILES) >= 20, goal


def test_every_profile_gets_five_reciprocal_matches_under_3_seconds():
    worst = 0.0
    for p in PROFILES:
        t0 = time.perf_counter()
        recs = MATCHER.recommend(p)
        worst = max(worst, time.perf_counter() - t0)
        assert len(recs) == 5, p["id"]
        assert p["id"] not in {m.profile["id"] for m in recs}
        _check_reciprocity(prepare(p), recs)
    assert worst < 3.0


def test_job_seeker_never_sees_other_job_seekers():
    seeker = next(p for p in PROFILES if p["goal"] == "find_job")
    assert all(m.profile["goal"] == "hire" for m in MATCHER.recommend(seeker))


@pytest.mark.parametrize("case", JURY, ids=[c["case"] for c in JURY])
def test_jury_like_profiles_get_at_least_3_relevant(case):
    q = prepare(case)
    recs = MATCHER.recommend(q, lang=case["lang"])
    assert len(recs) == 5
    _check_reciprocity(q, recs)
    relevant = sum(1 for m in recs if m.parts["role"] >= 0.5)
    assert relevant >= 3, [(m.profile["name"], m.profile["role"], m.parts["role"]) for m in recs]


@pytest.mark.parametrize("lang", LANGS)
def test_explanations_are_one_or_two_sentences_in_every_language(lang):
    for case in JURY:
        for m in MATCHER.recommend(prepare(case), lang=lang):
            assert m.explanation and m.icebreaker
            assert 1 <= len(SENTENCE_END.findall(m.explanation)) <= 2, m.explanation
            assert "{" not in m.explanation + m.icebreaker


def test_about_text_is_understood():
    q = prepare({"role": "recruiter", "goal": "hire", "stack": [], "interests": [],
                 "about": "Ищем фронтенд-разработчика на React, уровень middle"})
    assert "react" in q["stack"]
    assert q["seeking_roles"] == ["frontend"]
    assert (q["hire_exp_min"], q["hire_exp_max"]) == (2, 5)


def test_feedback_removes_person_and_refills_top5():
    q = prepare(JURY[0])
    first = MATCHER.recommend(q)
    gone = first[0].profile
    second = MATCHER.recommend(q, exclude={gone["id"]}, rejected_roles=[gone["role"]])
    assert gone["id"] not in {m.profile["id"] for m in second}
    assert len(second) == 5


def test_schedule_has_no_double_booking():
    q = prepare(JURY[0])
    plan, left = plan_meetings(MATCHER.recommend(q))
    slots = [s for s, _ in plan]
    assert len(slots) == len(set(slots))
    assert all(s in q["slots"] for s in slots)
    assert len(plan) + len(left) == 5


def test_booths():
    booths = recommend_booths(prepare(JURY[0]), load_booths())
    assert len(booths) == 2

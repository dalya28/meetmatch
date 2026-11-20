"""«Куда пойти», взаимный мэтч и Telegram, нетворкинг-бинго, анкета из текста."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from autofill import autofill, by_rules, scrub
from matcher import load_profiles
from social import (FREE, LINES, bingo_card, bingo_lines, bingo_tick, clean_telegram, demo_accepts, is_mutual,
                    telegram_url)
from storage import FeedbackStore, HallStore
from survey_helper import complete_survey

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PROFILES = load_profiles()


# ---------------------------------------------------------------- Telegram и взаимность
@pytest.mark.parametrize("raw,handle", [("@dalya_dev", "dalya_dev"), ("https://t.me/dalya_dev", "dalya_dev"),
                                        ("t.me/dalya_dev/", "dalya_dev"), ("dal", ""), ("<script>", ""),
                                        ("javascript:alert(1)", "")])
def test_telegram_is_cleaned(raw, handle):
    assert clean_telegram(raw) == handle
    assert telegram_url(raw) == (f"https://t.me/{handle}" if handle else None)


def test_demo_answer_is_stable_and_grows_with_score():
    assert demo_accepts("me", "p001", 0.6) == demo_accepts("me", "p001", 0.6)
    low = sum(demo_accepts("me", p["id"], 0.1) for p in PROFILES)
    high = sum(demo_accepts("me", p["id"], 0.9) for p in PROFILES)
    assert low < high


def test_live_mutual_needs_both_clicks():
    them = {"id": "hB", "live": True}
    assert not is_mutual(them, 0.9, "hA", "hA", [])
    events = [{"action": "met", "from": "hB", "candidate_id": "hA"}]
    assert is_mutual(them, 0.9, "hA", "hA", events)
    assert not is_mutual(them, 0.9, None, "x", events)  # без анкеты в зале вас не видно


# ---------------------------------------------------------------- бинго
def test_bingo_card_is_reachable_and_lines_count():
    pool = PROFILES[:60]
    card = bingo_card(pool, "seed")
    assert len(card) == 9 and card[4] == FREE and len(set(card)) == 9
    done = {}
    for p in pool:
        bingo_tick(card, done, p)
    assert bingo_lines(done) >= 1
    assert bingo_lines({str(i): "x" for i in LINES[0]}) == 1


def test_one_meeting_closes_center_and_at_most_one_task():
    card = bingo_card(PROFILES, "seed")
    done = {}
    new = bingo_tick(card, done, PROFILES[0])
    assert 4 in new and len(new) <= 2


# ---------------------------------------------------------------- анкета из текста
@pytest.mark.parametrize("text,goal,role", [
    ("Senior backend developer, 6 years of Python and Django. Open to work in fintech.", "find_job", "backend"),
    ("Я IT-рекрутер маркетплейса. Ищем фронтенд-разработчика на React, middle.", "hire", "recruiter"),
    ("Студентка 3 курса, учу SQL и pandas, ищу ментора в data science", "find_mentor", "student"),
    ("Мен 4 жыл Android әзірлеушімін, Kotlin, жұмыс іздеп жүрмін", "find_job", "mobile"),
    ("Founder of an edtech startup, looking for a technical co-founder (CTO, backend)", "find_cofounder", "founder"),
    ("Тимлид, 12 лет в разработке, могу менторить джунов", "be_mentor", "lead"),
])
def test_rules_understand_bios(text, goal, role):
    r = by_rules(text)
    assert (r["goal"], r["role"]) == (goal, role)


def test_contacts_are_scrubbed_and_no_key_means_rules(monkeypatch):
    assert "@" not in scrub("пишите ivan@mail.kz") and "701" not in scrub("тел +7 (701) 123-45-67")
    monkeypatch.delenv("MEETMATCH_AI", raising=False)
    assert autofill("Backend developer, 3 years of Python. Looking for a job.")["source"] == "rules"


# ---------------------------------------------------------------- в приложении
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETMATCH_TODAY", "2026-11-20")
    monkeypatch.delenv("MEETMATCH_AI", raising=False)
    monkeypatch.setattr(HallStore.__init__, "__defaults__", (tmp_path / "hall.json",))
    monkeypatch.setattr(FeedbackStore.__init__, "__defaults__", (tmp_path / "feedback.json",))
    monkeypatch.setattr(config, "HALL_ENABLED", True)
    st.cache_resource.clear()
    yield AppTest.from_file(APP, default_timeout=30)
    st.cache_resource.clear()


def test_autofill_goes_straight_to_matches(app):
    app.query_params["start"] = "1"
    app.run()
    app.button(key="af_toggle").click().run()
    app.text_area(key="af_text").set_value("Я IT-рекрутер. Ищем фронтенд-разработчика на React, middle.")
    app.button(key="af_go").click().run()
    assert app.session_state["survey_step"] is None
    assert app.session_state["query"]["goal"] == "hire"
    assert app.info  # «анкета заполнена по вашему тексту: …»
    assert any((b.key or "").startswith("skip_") for b in app.button)


def test_where_to_go_ranks_events_and_meet_updates_bingo(app):
    app.run()
    complete_survey(app, goal="find_job")
    app.button(key="change_event").click().run()
    ranked = [b.key.removeprefix("ev_go_") for b in app.button if (b.key or "").startswith("ev_go_")]
    fits = app.session_state["event_fits"][1]
    assert [fits[e] for e in ranked] == sorted((fits[e] for e in ranked), reverse=True)
    app.button(key="events_back").click().run()

    pid = next(b.key.removeprefix("meet_") for b in app.button if (b.key or "").startswith("meet_"))
    app.button(key=f"meet_{pid}").click().run()
    assert not app.exception
    assert "4" in app.session_state["bingo"]["done"]  # центр — первое знакомство
    assert app.success or app.info  # «это взаимно» или «запрос отправлен»

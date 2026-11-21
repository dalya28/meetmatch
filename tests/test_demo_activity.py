"""Дашборд организатора не показывает нули: каждая цифра со скриншота заполнена демо-активностью,
а сама демо-активность получена теми же функциями, что работают у живых участников."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from demo_activity import DEMO_PATH, load_demo, simulate
from events import DEFAULT_EVENT, attendee_ids, load_events
from matcher import load_profiles
from storage import FeedbackStore, HallStore, ReviewStore, feedback_stats, review_stats

DEMO = load_demo()
APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_demo_file_matches_simulation():
    """Файл в репозитории — ровно то, что выдаёт симуляция: цифры не подрисованы руками."""
    assert DEMO_PATH.exists()
    assert simulate() == DEMO


def test_demo_people_are_attendees_of_the_event():
    here = attendee_ids(next(e for e in load_events() if e["id"] == DEFAULT_EVENT), load_profiles())
    assert len(DEMO["people"]) == 40 and set(DEMO["people"]) <= here
    assert all(e.get("from", DEMO["people"][0]) in DEMO["people"] for e in DEMO["feedback"])


@pytest.mark.parametrize("key", ["total", "met", "not_fit", "groups", "bingo"])
def test_every_feedback_number_is_filled(key):
    assert feedback_stats(DEMO["feedback"])[key] > 0


def test_meet_share_and_reviews_are_realistic():
    fb, rv = feedback_stats(DEMO["feedback"]), review_stats(DEMO["reviews"])
    assert 0.2 < fb["met_share"] < 0.8                     # не все подряд жмут «Познакомиться»
    assert rv["happened"] > 0 and 3.5 <= rv["avg"] <= 5
    assert 0 < rv["helped_share"] <= 1 and rv["learned"]


def test_demo_records_pass_store_validation(tmp_path):
    """Каждую демо-запись принимает настоящее хранилище — формат тот же, что у живых."""
    fb, rv = FeedbackStore(tmp_path / "f.json"), ReviewStore(tmp_path / "r.json")
    for e in DEMO["feedback"]:
        fb.add(e["action"], e["candidate_id"], e["goal"], from_id=e.get("from"))
    for e in DEMO["reviews"]:
        rv.add(event=e["event"], candidate_id=e["candidate_id"], happened=e["happened"], rating=e["rating"],
               learned=e["learned"], helped=e["helped"], next_step=e["next"])
    assert fb.stats() == feedback_stats(DEMO["feedback"])
    assert rv.stats() == review_stats(DEMO["reviews"])


def test_groups_have_three_or_four_people():
    sizes = {}
    for e in DEMO["feedback"]:
        if e["action"] == "group":
            sizes[e["candidate_id"]] = sizes.get(e["candidate_id"], 0) + 1
    assert sizes and all(3 <= n <= 4 for n in sizes.values())


def test_broken_demo_file_gives_empty_activity(tmp_path):
    bad = tmp_path / "demo.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_demo(bad) == {"event": None, "people": [], "feedback": [], "reviews": []}
    assert load_demo(tmp_path / "missing.json")["feedback"] == []


def _dashboard(tmp_path, monkeypatch):
    for cls, name in ((HallStore, "hall"), (FeedbackStore, "feedback"), (ReviewStore, "reviews")):
        monkeypatch.setattr(cls.__init__, "__defaults__", (tmp_path / f"{name}.json",))
    monkeypatch.setattr(config, "HALL_ENABLED", True)
    st.cache_resource.clear()
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input(key="org_code").set_value("admin")
    next(b for b in app.button if b.label == "Войти").click().run()
    assert not app.exception and app.radio(key="main_page").value == "dash"
    return app


SCREEN = ["Участников", "Отзывов о знакомствах", "Доля «познакомились»", "Записи в компании", "Собрали бинго",
          "Участников в живом зале", "Встреч с отзывом", "Средняя оценка", "Помогло цели"]


def test_dashboard_has_no_zeros_with_demo(tmp_path, monkeypatch):
    app = _dashboard(tmp_path, monkeypatch)
    values = {m.label: m.value for m in app.metric}
    for label in SCREEN:
        assert values[label] not in ("0", "0%", "—"), label
    assert values["Участников в живом зале"] == "40"
    assert any("демо-активность" in c.value for c in app.caption)


def test_real_actions_are_added_on_top_of_demo(tmp_path, monkeypatch):
    FeedbackStore(tmp_path / "feedback.json").add("bingo", DEFAULT_EVENT, "find_job")
    app = _dashboard(tmp_path, monkeypatch)
    bingo = next(m.value for m in app.metric if m.label == "Собрали бинго")
    assert int(bingo) == feedback_stats(DEMO["feedback"])["bingo"] + 1


def test_demo_toggle_off_shows_only_real_numbers(tmp_path, monkeypatch):
    app = _dashboard(tmp_path, monkeypatch)
    app.toggle(key="dash_demo").set_value(False).run()
    values = {m.label: m.value for m in app.metric}
    assert values["Отзывов о знакомствах"] == "0" and values["Собрали бинго"] == "0"
    assert values["Участников в живом зале"] == "0"

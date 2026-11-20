"""Встречи в компании и доступ к странице организатора."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from groups import suggest_group
from matcher import load_profiles, prepare
from storage import FeedbackStore
from survey_helper import complete_survey
from taxonomy import EVENT_SLOTS, GOALS

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PROFILES = load_profiles()


@pytest.mark.parametrize("goal", GOALS)
def test_group_has_same_goal_and_respects_exclude(goal):
    q = prepare({"goal": goal, "role": "backend", "experience": 2, "stack": ["python"],
                 "interests": ["fintech"], "slots": ["11:00"]})
    g = suggest_group(q, PROFILES)
    assert g is not None and len(g.members) == 3
    assert all(m["goal"] == goal for m in g.members)
    assert len({m["id"] for m in g.members}) == 3
    assert g.slot in EVENT_SLOTS and 1 <= g.table <= 12
    other = suggest_group(q, PROFILES, exclude=[m["id"] for m in g.members])
    assert other is not None and not {m["id"] for m in other.members} & {m["id"] for m in g.members}


def test_group_needs_enough_people():
    q = prepare({"goal": "find_job", "role": "backend", "experience": 2})
    assert suggest_group(q, [p for p in PROFILES if p["goal"] == "find_job"][:1]) is None


@pytest.fixture
def feedback_file(tmp_path, monkeypatch):
    monkeypatch.setattr(FeedbackStore.__init__, "__defaults__", (tmp_path / "feedback.json",))
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def test_group_view_join_and_other(feedback_file):
    app = AppTest.from_file(APP).run()
    complete_survey(app, fmt="group")
    assert app.session_state["view_pick"] == "group"
    assert not any((b.key or "").startswith("skip_") for b in app.button)  # вместо 5 карточек — компания
    app.button(key="group_join").click().run()
    assert not app.exception and app.success
    assert FeedbackStore().stats()["groups"] == 1
    assert not any(b.key == "group_join" for b in app.button)  # повторно записаться нельзя
    app.segmented_control(key="view_pick").set_value("one").run()  # можно вернуться к знакомствам 1:1
    assert sum((b.key or "").startswith("skip_") for b in app.button) == 5


def test_group_other_shows_new_people(feedback_file):
    app = AppTest.from_file(APP).run()
    complete_survey(app, fmt="group")
    app.button(key="group_other").click().run()
    seen = app.session_state["group_seen"]
    assert len(seen) == 3
    app.button(key="group_other").click().run()
    assert len(app.session_state["group_seen"]) == 6 and len(set(app.session_state["group_seen"])) == 6


def test_dashboard_hidden_without_code():
    app = AppTest.from_file(APP)
    app.secrets["organizers"] = {"dalya": "right-code-123"}
    app.run()
    assert not any(r.key == "main_page" for r in app.radio)

    app.query_params["org"] = "wrong"
    app.run()
    assert app.error and app.session_state["organizer"] is None
    assert not any(r.key == "main_page" for r in app.radio)

    app.query_params["org"] = "right-code-123"
    app.run()
    assert app.session_state["organizer"] == "dalya"
    assert app.radio(key="main_page").value == "dash"
    assert "org" not in app.query_params  # код не остаётся в адресе

    app.button(key="org_logout").click().run()
    assert app.session_state["organizer"] is None
    assert not any(r.key == "main_page" for r in app.radio)


def test_login_attempts_are_limited():
    app = AppTest.from_file(APP)
    app.secrets["organizers"] = {"dalya": "right-code-123"}
    app.run()
    for _ in range(5):
        app.text_input(key="org_code").set_value("nope")
        next(b for b in app.button if b.label == "Войти").click().run()
    assert app.session_state["org_attempts"] == 5
    app.run()
    assert not any(ti.key == "org_code" for ti in app.text_input)  # форма закрыта
    app.query_params["org"] = "right-code-123"  # и ссылка тоже не пускает до перезагрузки
    app.run()
    assert app.session_state["organizer"] is None

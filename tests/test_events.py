"""Ближайшие события: список, состав участников и подбор только среди тех, кто идёт на событие."""
from datetime import date
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from events import DEFAULT_EVENT, attendee_ids, load_events, upcoming
from matcher import load_profiles
from storage import HallStore
from survey_helper import complete_survey
from taxonomy import INTERESTS, ROLES

APP = str(Path(__file__).resolve().parents[1] / "app.py")
EVENTS = load_events()
PROFILES = load_profiles()
TYPES = {"hackathon", "training", "workshop", "forum", "meetup", "conference", "summit"}


def test_events_file_is_valid():
    assert len(EVENTS) >= 8
    assert len({e["id"] for e in EVENTS}) == len(EVENTS)
    for e in EVENTS:
        assert e["type"] in TYPES
        assert e["url"].startswith("https://")
        assert e["start"] <= e["end"]
        assert set(e["about"]) == {"ru", "kk", "en"}
        assert set(e["topics"]) <= set(INTERESTS) and set(e["roles"]) <= set(ROLES)
    assert [e["start"] for e in EVENTS] == sorted(e["start"] for e in EVENTS)


def test_upcoming_hides_finished_events():
    assert upcoming(EVENTS, date(2026, 11, 21))[0]["id"] == DEFAULT_EVENT  # второй день хакатона
    later = upcoming(EVENTS, date(2026, 11, 22))
    assert DEFAULT_EVENT not in {e["id"] for e in later} and later
    assert upcoming(EVENTS, date(2027, 1, 1)) == []


def test_attendees_are_stable_and_live_profiles_stay_on_their_event():
    servercore = next(e for e in EVENTS if e["id"] == "servercore-it-besh")
    hackathon = next(e for e in EVENTS if e["id"] == DEFAULT_EVENT)
    first = attendee_ids(servercore, PROFILES)
    assert first == attendee_ids(servercore, PROFILES) and len(first) == servercore["size"]
    assert attendee_ids(hackathon, PROFILES) == {p["id"] for p in PROFILES}
    live = {**PROFILES[0], "id": "hX", "live": True, "event": "servercore-it-besh"}
    assert "hX" in attendee_ids(servercore, PROFILES + [live])
    assert "hX" not in attendee_ids(hackathon, PROFILES + [live])


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETMATCH_TODAY", "2026-11-20")
    monkeypatch.setattr(HallStore.__init__, "__defaults__", (tmp_path / "hall.json",))
    monkeypatch.setattr(config, "HALL_ENABLED", True)
    st.cache_resource.clear()
    yield AppTest.from_file(APP, default_timeout=30).run()
    st.cache_resource.clear()


def _cards(app) -> set[str]:
    return {b.key.removeprefix("skip_") for b in app.button if (b.key or "").startswith("skip_")}


def test_pick_event_fill_once_and_switch(app):
    soon = [e["id"] for e in upcoming(EVENTS, date(2026, 11, 20))]
    shown = [b.key.removeprefix("ev_go_") for b in app.button if (b.key or "").startswith("ev_go_")]
    assert shown == soon[:6]                                    # на главной — первые шесть
    app.button(key="events_all_btn").click().run()
    shown = [b.key.removeprefix("ev_go_") for b in app.button if (b.key or "").startswith("ev_go_")]
    assert shown == soon

    app.button(key="ev_go_servercore-it-besh").click().run()  # без анкеты — сразу опрос
    assert app.session_state["survey_step"] == 0
    complete_survey(app, goal="exchange")
    here = attendee_ids(next(e for e in EVENTS if e["id"] == "servercore-it-besh"), PROFILES)
    assert _cards(app) and _cards(app) <= here

    app.button(key="change_event").click().run()               # анкета уже есть — опрос не нужен
    app.button(key="ev_go_hr-forum-central-asia").click().run()
    assert app.session_state["survey_step"] is None and not app.exception
    hr = attendee_ids(next(e for e in EVENTS if e["id"] == "hr-forum-central-asia"), PROFILES)
    assert _cards(app) and _cards(app) <= hr


def test_group_and_hall_follow_the_event(app):
    app.button(key="events_all_btn").click().run()
    app.button(key="ev_go_moy-realnyy-biznes").click().run()
    complete_survey(app, goal="find_cofounder", fmt="group")
    here = attendee_ids(next(e for e in EVENTS if e["id"] == "moy-realnyy-biznes"), PROFILES)
    app.button(key="group_other").click().run()
    assert set(app.session_state["group_seen"]) <= here

    app.button(key="hall_join").click().run()
    assert [p["event"] for p in HallStore().all()] == ["moy-realnyy-biznes"]
    app.button(key="change_event").click().run()
    app.button(key="ev_go_echai-startup-mixer").click().run()
    assert any(b.key == "hall_join" for b in app.button)        # на другое событие — отдельная запись

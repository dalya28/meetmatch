"""Отзывы о встречах: оповещение после знакомства, форма, статистика организатора."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from storage import FeedbackStore, HallStore, ReviewStore
from survey_helper import complete_survey

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_store_validates_and_counts(tmp_path):
    store = ReviewStore(tmp_path / "r.json")
    store.add(event="e", candidate_id="p1", happened=True, rating=5, learned="про найм", helped="yes", next_step="yes")
    store.add(event="e", candidate_id="p2", happened=False)
    st_ = ReviewStore(tmp_path / "r.json").stats()
    assert st_["total"] == 2 and st_["happened"] == 1 and st_["avg"] == 5 and st_["learned"] == ["про найм"]
    with pytest.raises(ValueError):
        store.add(event="e", candidate_id="p3", happened=True, rating=9)


def test_reminder_and_review_flow(tmp_path, monkeypatch):
    for cls, name in ((HallStore, "hall"), (FeedbackStore, "fb"), (ReviewStore, "rev")):
        monkeypatch.setattr(cls.__init__, "__defaults__", (tmp_path / f"{name}.json",))
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(APP, default_timeout=30).run()
        complete_survey(app)
        pid = next(b.key.removeprefix("meet_") for b in app.button if (b.key or "").startswith("meet_"))
        app.button(key=f"meet_{pid}").click().run()
        assert any("notifications_active" in (i.icon or "") for i in app.info)  # оповещение
        app.text_area(key=f"fb_{pid}_learned").set_value("Узнал, как устроен найм")
        app.radio(key=f"fb_{pid}_helped").set_value("yes")
        next(b for b in app.button if b.key == f"FormSubmitter:fb_{pid}_form-" + b.label or "fb_" in (b.key or "") and "form" in (b.key or "")).click().run()
        assert not app.exception
        assert ReviewStore().all()[0]["learned"] == "Узнал, как устроен найм"
        assert not any("notifications_active" in (i.icon or "") for i in app.info)
    finally:
        st.cache_resource.clear()

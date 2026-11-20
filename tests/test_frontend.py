from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from matcher import Matcher
from storage import HallStore
from texts import t


def test_join_resubmit_and_organizer_clear(tmp_path, monkeypatch):
    path = tmp_path / "hall.json"
    monkeypatch.setattr(HallStore.__init__, "__defaults__", (path,))
    monkeypatch.setattr(config, "HALL_ENABLED", True)
    monkeypatch.setenv("MEETMATCH_ORGANIZER_CODE", "organizer-test")
    st.cache_resource.clear()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()

    def click(label):
        next(b for b in app.button if b.label == label).click().run()
        assert not app.exception

    try:
        click("Показать 5 человек")
        click("Добавить меня в зал")
        joined = app.session_state["query"]["id"]
        click("Показать 5 человек")
        assert app.session_state["query"]["id"] == joined
        assert not any(b.label == "Добавить меня в зал" for b in app.button)
        assert [p["id"] for p in HallStore().all()] == [joined]

        app.radio(key="main_page").set_value("dash").run()
        assert any(m.label == "Участников в живом зале" and m.value == "1" for m in app.metric)
        app.text_input[0].set_value("wrong")
        click("Очистить живой зал")
        assert app.error and len(HallStore().all()) == 1
        app.text_input[0].set_value("organizer-test")
        click("Очистить живой зал")
        assert HallStore().all() == []
        assert any(m.label == "Участников в живом зале" and m.value == "0" for m in app.metric)
        app.radio(key="main_page").set_value("match").run()
        click("Добавить меня в зал")
        assert app.session_state["query"]["id"] != joined

        with monkeypatch.context() as patch:
            def unavailable(*args, **kwargs):
                raise RuntimeError("test")
            patch.setattr(Matcher, "recommend", unavailable)
            click("Показать 5 человек")
            assert app.error
        click("Повторить подбор")
        assert not app.error
        with monkeypatch.context() as patch:
            patch.setattr(Matcher, "recommend", lambda *args, **kwargs: [])
            for lang in ("ru", "kk", "en"):
                app.segmented_control(key="lang_pick").set_value(lang).run()
                assert not app.exception
                assert any(w.value == t(lang, "no_more") for w in app.warning)
                assert any(s.value == t(lang, "hall_joined") for s in app.success)
    finally:
        st.cache_resource.clear()

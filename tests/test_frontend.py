from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

import config
from matcher import Matcher
from storage import HallStore
from texts import t
from survey_helper import complete_survey


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
        complete_survey(app)  # анкета попадает в живой зал сама
        joined = app.session_state["query"]["id"]
        complete_survey(app)
        assert app.session_state["query"]["id"] == joined
        assert [p["id"] for p in HallStore().all()] == [joined]

        assert not any(r.key == "main_page" for r in app.radio)  # без кода вкладки организатора нет
        app.text_input(key="org_code").set_value("wrong")
        click("Войти")
        assert app.error and app.session_state["organizer"] is None
        app.text_input(key="org_code").set_value("organizer-test")
        click("Войти")
        assert app.session_state["organizer"] == "organizer"
        assert app.radio(key="main_page").value == "dash"
        app.toggle(key="dash_demo").set_value(False).run()  # считаем только реальных людей
        assert any(m.label == "Участников в живом зале" and m.value == "1" for m in app.metric)
        assert next(b for b in app.button if b.key == "hall_clear_btn").disabled  # сначала подтверждение
        app.checkbox(key="hall_confirm").check().run()
        click("Очистить живой зал")
        assert HallStore().all() == []
        assert any(m.label == "Участников в живом зале" and m.value == "0" for m in app.metric)
        app.radio(key="main_page").set_value("match").run()

        with monkeypatch.context() as patch:
            def unavailable(*args, **kwargs):
                raise RuntimeError("test")
            patch.setattr(Matcher, "recommend", unavailable)
            complete_survey(app)
            assert app.error
        click("Повторить подбор")
        assert not app.error
        with monkeypatch.context() as patch:
            patch.setattr(Matcher, "recommend", lambda *args, **kwargs: [])
            for lang in ("ru", "kk", "en"):
                app.segmented_control(key="lang_pick").set_value(lang).run()
                assert not app.exception
                assert any(w.value == t(lang, "no_more") for w in app.warning)
    finally:
        st.cache_resource.clear()


def test_demo_organizer_code_opens_dashboard_without_hall_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(HallStore.__init__, "__defaults__", (tmp_path / "hall.json",))
    monkeypatch.setattr(config, "HALL_ENABLED", True)
    st.cache_resource.clear()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    complete_survey(app)                                  # в зале есть человек — кнопка очистки была бы видна
    app.text_input(key="org_code").set_value("admin")
    next(b for b in app.button if b.label == "Войти").click().run()
    assert not app.exception
    assert app.session_state["organizer"] == "demo"
    assert app.radio(key="main_page").value == "dash"
    assert not any(b.key == "hall_clear_btn" for b in app.button)   # публичный код не стирает зал

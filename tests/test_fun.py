"""Звери ролей, фото, кубик с первыми фразами."""
import base64
import io
from pathlib import Path

import streamlit as st
from PIL import Image
from streamlit.testing.v1 import AppTest

import config
from avatars import FUN_OPENERS, ROLE_ANIMAL, opener, photo_data_uri, profile_avatar
from storage import HallStore
from taxonomy import ROLES

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_every_role_has_an_animal_and_a_joke_in_three_languages():
    assert set(ROLE_ANIMAL) == set(ROLES)
    for emoji, jokes in ROLE_ANIMAL.values():
        assert emoji and set(jokes) == {"ru", "kk", "en"}
    assert profile_avatar({"role": "fullstack"}) == "🦆"
    assert profile_avatar({"role": "fullstack", "avatar": "🦖"}) == "🦖"


def test_photo_is_cropped_small_and_garbage_is_rejected():
    raw = io.BytesIO()
    Image.new("RGB", (1200, 800), (21, 88, 201)).save(raw, "JPEG")
    uri = photo_data_uri(raw.getvalue())
    img = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
    assert img.size == (160, 160) and img.format == "WEBP"
    assert photo_data_uri(b"<script>alert(1)</script>") is None
    assert photo_data_uri(b"") is None


def test_opener_starts_with_smart_line_then_cycles():
    lines = [opener("smart", "Жансая Ахметова", "ru", n) for n in range(len(FUN_OPENERS["ru"]) + 2)]
    assert lines[0] == "smart" and lines[1].startswith("Жансая,")
    assert lines[len(FUN_OPENERS["ru"]) + 1] == "smart"  # круг замкнулся


def test_avatar_dice_and_hall(tmp_path, monkeypatch):
    monkeypatch.setattr(HallStore.__init__, "__defaults__", (tmp_path / "hall.json",))
    monkeypatch.setattr(config, "HALL_ENABLED", True)
    st.cache_resource.clear()
    try:
        app = AppTest.from_file(APP, default_timeout=30)
        app.query_params["start"] = "1"
        app.run()
        for key in ("sv_goal_find_job", "sv_format_one", "sv_role_fullstack", "sv_experience_1"):
            app.button(key=key).click().run()
        assert "🦆" in app.button(key="sv_next_avatar").label  # зверь роли по умолчанию
        app.button_group(key="sv_avatar_pick").set_value("🦖").run()  # другой зверь — сразу дальше
        assert app.session_state["form"]["avatar"] == "🦖"
        while app.session_state["survey_step"] is not None:
            nxt = [b for b in app.button if (b.key or "").startswith("sv_next_") or b.key == "sv_finish"]
            nxt[0].click().run()
        assert app.session_state["query"]["avatar"] == "🦖"

        pid = next(b.key.removeprefix("ice_") for b in app.button if (b.key or "").startswith("ice_"))
        before = [c.value for c in app.code]
        app.button(key=f"ice_{pid}").click().run()
        assert [c.value for c in app.code] != before  # кубик меняет фразу

        assert HallStore().all()[0]["avatar"] == "🦖"  # анкета в зале сразу после опроса
    finally:
        st.cache_resource.clear()

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from claude_rank import apply_rows
from survey_helper import complete_survey
from taxonomy import GOALS
from texts import t

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _cards(app) -> list[str]:
    return [b.key.removeprefix("skip_") for b in app.button if (b.key or "").startswith("skip_")]


@pytest.mark.parametrize("lang", ["ru", "kk", "en"])
def test_jury_flow(lang):
    """Опрос по шагам → 5 человек → «Пропустить» → «Новые участники» — для каждой цели и языка."""
    app = AppTest.from_file(APP).run()
    app.segmented_control(key="lang_pick").set_value(lang).run()
    for goal in GOALS:
        about = "Деректерді талдаймын, тәжірибе алмасқым келеді." if lang == "kk" else None
        complete_survey(app, goal=goal, lang=lang, about=about)
        assert app.session_state["query"]["goal"] == goal
        first = _cards(app)
        assert len(first) == 5
        assert app.button(key=f"meet_{first[0]}")

        app.button(key=f"skip_{first[0]}").click().run()       # пропуск убирает карточку
        assert _cards(app) == first[1:]
        app.button(key=f"meet_{first[1]}").click().run()       # «Познакомиться» оставляет её с отметкой
        assert first[1] not in _cards(app)
        assert app.success or app.info                        # «это взаимно» или «запрос отправлен»

        app.button(key="new_people_1").click().run()           # следующие пятеро, без повторов
        assert not app.exception
        second = _cards(app)
        assert len(second) == 5 and not set(second) & set(first)
        assert app.session_state["batch_no"] == 2


def test_survey_back_and_seeking_question():
    app = AppTest.from_file(APP)
    app.query_params["start"] = "1"
    app.run()
    app.button(key="sv_goal_hire").click().run()
    assert app.session_state["survey_step"] == 1
    app.button(key="sv_back").click().run()
    assert app.session_state["survey_step"] == 0
    app.button(key="sv_goal_hire").click().run()
    app.button(key="sv_format_one").click().run()
    app.button(key="sv_role_recruiter").click().run()
    app.button(key="sv_experience_3").click().run()
    assert any(s.value == t("ru", "q_avatar") for s in app.subheader)  # шаг-шутка: зверь роли
    app.button(key="sv_next_avatar").click().run()
    assert any(s.value == t("ru", "q_seeking_roles") for s in app.subheader)  # для найма — «Кого ищете?»


def test_model_rejects_duplicate_or_unknown_ids():
    with pytest.raises(ValueError):
        apply_rows([{"id": "a"}] * 5, dict.fromkeys("abcde"))
    with pytest.raises(ValueError):
        apply_rows([{"id": "z", "why": "why", "hello": "hello"}], {"a": None})

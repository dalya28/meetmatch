import pytest
from streamlit.testing.v1 import AppTest
from pathlib import Path
from matcher import Matcher, load_profiles
from taxonomy import GOALS
from texts import t
from claude_rank import apply_rows

@pytest.mark.parametrize("lang", ["ru", "kk", "en"])
def test_jury_flow(lang):
    matcher = Matcher(load_profiles())
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    app.segmented_control(key="lang_pick").set_value(lang).run()
    for goal in GOALS:
        app.radio(key=f"w_goal_{lang}").set_value(goal)
        if lang == "kk":
            app.text_area(key="w_about_kk").set_value("Деректерді талдаймын, тәжірибе алмасқым келеді.")
        next(b for b in app.button if b.label == t(lang, "submit")).click().run()
        assert not app.exception
        assert app.session_state.query["goal"] == goal
        people = app.radio(key="person_pick")
        assert len(people.options) == 5
        assert app.button(key=f"met_{people.value}")
        first_id = people.value
        fifth = matcher.recommend(app.session_state.query, lang=lang)[4].profile["id"]
        people.set_value(fifth).run()
        last_id = app.radio(key="person_pick").value
        assert first_id != last_id == fifth
        assert app.button(key=f"no_{last_id}")

def test_model_rejects_duplicate_or_unknown_ids():
    with pytest.raises(ValueError):
        apply_rows([{"id":"a"}] * 5, dict.fromkeys("abcde"))
    with pytest.raises(ValueError):
        apply_rows([{"id":"z","why":"why","hello":"hello"}], {"a": None})

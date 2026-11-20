import pytest
from streamlit.testing.v1 import AppTest
from pathlib import Path
from taxonomy import GOALS, GOAL_MATCH
from texts import t
from claude_rank import apply_rows

@pytest.mark.parametrize("lang", ["ru", "kk", "en"])
def test_jury_flow(lang):
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    app.segmented_control(key="lang_pick").set_value(lang).run()
    for goal in GOALS:
        app.radio(key=f"w_goal_{lang}").set_value(goal)
        if lang == "kk":
            app.text_area(key="w_about_kk").set_value("Деректерді талдаймын, тәжірибе алмасқым келеді.")
        next(b for b in app.button if b.label == t(lang, "submit")).click().run()
        assert not app.exception
        assert app.session_state.query["goal"] == goal
        matches = [b for b in app.button if b.key and b.key.startswith("met_")]
        assert len(matches) == 5
        assert len(set(b.key for b in matches)) == 5

def test_model_rejects_duplicate_or_unknown_ids():
    with pytest.raises(ValueError):
        apply_rows([{"id":"a"}] * 5, dict.fromkeys("abcde"))
    with pytest.raises(ValueError):
        apply_rows([{"id":"z","why":"why","hello":"hello"}], {"a": None})

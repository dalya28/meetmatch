"""Прохождение пошагового опроса в AppTest: так же, как это делает человек."""


def complete_survey(app, goal: str = "find_job", lang: str = "ru", about: str | None = None,
                    fmt: str = "one"):
    if app.session_state["query"] is None:
        app.query_params["start"] = "1"  # кнопка «Заполнить анкету» в обложке — ссылка ?start=1
        app.run()
    else:
        app.button(key="edit_profile").click().run()
    # один ответ — сразу следующий вопрос
    app.button(key=f"sv_goal_{goal}").click().run()
    app.button(key=f"sv_format_{fmt}").click().run()  # один человек или компания
    app.button(key="sv_role_backend").click().run()
    app.button(key="sv_experience_1").click().run()
    for _ in range(10):  # вопросы с несколькими ответами — «Далее», последний — «Показать 5 человек»
        if app.session_state["survey_step"] is None:
            break
        if about is not None and any(a.key == f"sv_about_{lang}" for a in app.text_area):
            app.text_area(key=f"sv_about_{lang}").set_value(about)
        finish = [b for b in app.button if b.key == "sv_finish"]
        if finish:
            finish[0].click().run()
        else:
            next(b for b in app.button if (b.key or "").startswith("sv_next_")).click().run()
        assert not app.exception
    assert app.session_state["survey_step"] is None
    return app

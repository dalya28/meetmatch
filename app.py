"""Wingman — веб-интерфейс на Streamlit.

Запуск:  python -m streamlit run app.py
"""
from __future__ import annotations

import base64
import html
import re
import json
import hmac
import os
import threading
import time
from datetime import date

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


def _reload_changed_modules() -> None:
    """Streamlit Cloud после git pull перезапускает только app.py, а модули проекта остаются в памяти
    старыми — отсюда ImportError на новых именах. Модуль устарел, если его исходник новее
    скомпилированной копии в __pycache__ (она пишется в момент импорта) — тогда перечитываем."""
    import importlib
    import sys
    for name in ("config", "taxonomy", "theme", "texts", "matcher", "storage", "events", "groups",
                 "avatars", "social", "autofill", "claude_rank"):  # порядок зависимостей
        mod = sys.modules.get(name)
        src = getattr(mod, "__file__", None)
        pyc = getattr(getattr(mod, "__spec__", None), "cached", None)
        try:
            if src and pyc and os.path.getmtime(src) > os.path.getmtime(pyc) + 1:
                importlib.reload(mod)
        except OSError:
            pass


_reload_changed_modules()

from config import HALL_ENABLED, setup_logging
from claude_rank import rerank
from matcher import Matcher, load_booths, load_profiles, plan_meetings, prepare, recommend_booths
from storage import FeedbackStore, HallStore, ReviewStore
from taxonomy import (EVENT_SLOTS, GOALS, HIREABLE_ROLES, INTERESTS, LOW_INFO_INTERESTS, ROLES,
                      STACK, STACK_ROLES, goal_label, interest_label, role_label, stack_label, years_ru)
from autofill import autofill
from avatars import avatar_choices, opener, photo_data_uri, profile_avatar, role_avatar, role_joke
from events import DEFAULT_EVENT, attendee_ids, load_events, upcoming
from groups import suggest_group
from social import (FREE, bingo_card, bingo_label, bingo_lines, bingo_reach, bingo_tick, clean_telegram, is_activity, is_mutual,
                    telegram_url)
from texts import GOAL_VERB, GROUP_TITLE, RECIPROCITY, UI, t
from theme import HEATMAP_SCALE, PAIR_COLOR, PAIR_OF, PRIMARY

st.set_page_config(page_title="Wingman", page_icon=str(Path(__file__).parent / "assets" / "favicon.png"),
                   layout="wide")
ASSETS = Path(__file__).parent / "assets"
st.html(ASSETS / "meetmatch.css")


@st.cache_data
def image_data(name: str) -> str:
    return base64.b64encode((ASSETS / f"{name}.webp").read_bytes()).decode("ascii")


# Логотип — уменьшенная 3D-картинка двух сцепленных звеньев (assets/logo-mark.webp).
st.html(f"<style>:root{{--mm-logo:url(data:image/webp;base64,{image_data('logo-mark')})}}</style>")


def section_art(name: str) -> None:
    st.html(f'<img class="mm-section-art mm-{name}" alt="" '
            f'src="data:image/webp;base64,{image_data(name)}">', width="content")


def event_cover(lang: str) -> None:
    st.html(f"""
        <section class="mm-cover">
          <div class="mm-intro">
            <div class="mm-kicker"><span class="mm-dot"></span> {t(lang, 'hero_kicker')}</div>
            <h1>{t(lang, 'hero_title')}<br><em>{t(lang, 'hero_accent')}</em></h1>
            <p>{t(lang, 'hero_copy')}</p>
            <div class="mm-cover-actions">
              <a class="mm-cta" href="?start=1&amp;lang={lang}&amp;event={html.escape(current_event()['id'])}" target="_self">{t(lang, 'hero_cta')} <span aria-hidden="true">→</span></a>
              <a class="mm-browse" href="#mm-events">{t(lang, 'browse')} <span aria-hidden="true">↓</span></a>
            </div>
          </div>
          <div class="mm-art">
            <img alt="" src="data:image/webp;base64,{image_data('wingman-links-cutout')}">
            <span class="mm-place">{t(lang, 'events_count', n=len(event_list()))}</span>
          </div>
        </section>
    """)


# ---------------------------------------------------------------- данные (общие для всех сессий)
log = setup_logging()


@st.cache_resource
def review_store() -> ReviewStore:
    return ReviewStore()


@st.cache_resource
def hall_store() -> HallStore:
    return HallStore()


@st.cache_resource
def feedback_store() -> FeedbackStore:
    """Отзывы всех участников на диске — переживают перезапуск; нужны дашборду организатора."""
    return FeedbackStore()


@st.cache_resource
def get_matcher() -> Matcher:
    m = Matcher(load_profiles())
    if HALL_ENABLED:
        m.add_profiles(hall_store().all())  # участники живого зала, которые уже присоединились
    log.info("startup profiles=%d hall=%s", len(m.profiles), HALL_ENABLED)
    return m


@st.cache_resource
def get_booths() -> list[dict]:
    return load_booths()


@st.cache_resource
def get_events() -> list[dict]:
    return load_events()


@st.cache_resource
def hall_lock():
    return threading.Lock()


def join_hall(q: dict, lang: str) -> dict:
    """Живой зал: анкета участника становится видна следующим участникам.
    Возвращает подготовленную анкету с id, чтобы человек не видел в рекомендациях сам себя."""
    event_id = current_event()["id"]
    with hall_lock():
        current = get_matcher()
        if q.get("id") in current.by_id and current.by_id[q["id"]].get("event", DEFAULT_EVENT) == event_id:
            return q
        profile = hall_store().join(q, lang, guest_name=t(lang, "guest"), event=event_id)
        current.add_profiles([profile])
    st.session_state.my_ids.append(profile["id"])  # свои анкеты на других событиях не показываем себе
    set_attending(event_id, True)
    return {**q, "id": profile["id"]}


try:
    matcher = get_matcher()
except RuntimeError as e:  # нет или повреждена база анкет — понятное сообщение вместо трассировки
    log.error("startup_failed error=%s", e)
    st.error(str(e))
    st.stop()

# ---------------------------------------------------------------- состояние
# Значения анкеты храним в `form` отдельно от виджетов: ключи виджетов зависят от языка,
# иначе Streamlit оставляет подписи списков на прежнем языке.
FIELDS = {"name": "", "role": "backend", "experience": 1, "stack": [], "interests": [], "about": "",
          "goal": "find_job", "seeking_roles": [], "slots": [], "format": "one", "avatar": "", "photo": "",
          "telegram": ""}
DEFAULTS = {"form": dict(FIELDS), "excluded": [], "rejected_roles": [], "met": [], "query": None,
            "lang": "ru", "survey_step": None, "answered": set(), "skipped": [], "batch_rejected": [],
            "batch_no": 1, "group_seen": [], "group_joined": None, "organizer": None,
            "org_attempts": 0, "event": None, "show_events": False, "my_ids": [], "ice": {}, "photo_nonce": 0, "bingo": None, "reviewed": []}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

# Keep only public event IDs on this device. The profile and contact details
# stay out of the attendance cookie.
ATTENDANCE_COOKIE = "wingman_events_v1"
if "attending" not in st.session_state:
    saved = set(st.context.cookies.get(ATTENDANCE_COOKIE, "").split(","))
    saved.update(matcher.by_id[pid].get("event", DEFAULT_EVENT) for pid in st.session_state.my_ids
                 if pid in matcher.by_id)
    st.session_state.attending = [e["id"] for e in get_events() if e["id"] in saved]


def set_attending(event_id: str, attending: bool) -> None:
    ids = set(st.session_state.attending)
    if attending:
        ids.add(event_id)
    else:
        ids.discard(event_id)
    st.session_state.attending = sorted(ids)
    st.session_state.attendance_change = (event_id, attending)


def persist_attendance() -> None:
    change = st.session_state.pop("attendance_change", None)
    if change:
        event_id, attending = change
        # Merge this single change with other tabs' choices before saving.
        st.html(f"""<script>/* {time.monotonic_ns()} */
          (() => {{
            const key = "{ATTENDANCE_COOKIE}=";
            const value = document.cookie.split("; ").find(x => x.startsWith(key)) || key;
            const ids = new Set(value.slice(key.length).split(",").filter(Boolean));
            ids.{'add' if attending else 'delete'}({json.dumps(event_id)});
            document.cookie = key + [...ids].join(",") + "; Max-Age=31536000; Path=/; SameSite=Lax";
          }})();
        </script>""", unsafe_allow_javascript=True)


def events_home() -> None:
    st.session_state.update(show_events=True, survey_step=None, preview_bingo=False)


def brand_home() -> None:
    events_home()
    st.session_state.update(main_page="match", event_scope="all")


def wkey(field: str, lang: str) -> str:
    return f"w_{field}_{lang}"


def clear_widgets() -> None:
    for key in [k for k in st.session_state.keys() if str(k).startswith("w_")]:
        del st.session_state[key]


EXAMPLES = {
    "find_job": {"role": "backend", "experience": 1, "stack": ["python", "django", "postgresql"],
                 "interests": ["fintech"], "goal": "find_job", "slots": ["11:00", "14:00", "15:30"],
                 "about": {"ru": "Начинающий Python-разработчик, делал пет-проекты на Django. Хочу в финтех.",
                           "kk": "Python-әзірлеушімін, Django-мен пет-жобалар жасадым. Финтехте жұмыс істегім келеді.",
                           "en": "Junior Python developer, built pet projects with Django. Want to work in fintech."}},
    "hire": {"role": "recruiter", "experience": 4, "interests": ["ecommerce"], "goal": "hire",
             "slots": ["11:00", "13:30", "16:00"],
             "about": {"ru": "IT-рекрутер маркетплейса. Ищем фронтенд-разработчика на React, уровень middle.",
                       "kk": "Маркетплейстің IT-рекрутерімін. React бойынша frontend-әзірлеуші іздейміз, деңгейі middle.",
                       "en": "IT recruiter at a marketplace. We're hiring a React frontend developer, middle level."}},
    "find_mentor": {"role": "student", "experience": 0, "stack": ["sql", "python"],
                    "interests": ["data_science"], "goal": "find_mentor", "slots": ["11:00", "12:00", "16:30"],
                    "about": {"ru": "Студент 3 курса, изучаю SQL и pandas, хочу стать аналитиком данных.",
                              "kk": "3-курс студентімін, SQL мен pandas үйреніп жүрмін, деректер талдаушысы болғым келеді.",
                              "en": "Third-year student learning SQL and pandas, want to become a data analyst."}},
}


def reset_feedback() -> None:
    s = st.session_state
    s.excluded, s.rejected_roles, s.met, s.skipped, s.batch_rejected = [], [], [], [], []
    s.batch_no = 1
    s.pop("claude_result", None)


def build_query(*, publish: bool = True) -> None:
    st.session_state.show_events = False
    st.session_state.preview_bingo = False
    st.session_state.activity_tabs = t(st.session_state.lang, "match_nav")
    previous_id = (st.session_state.query or {}).get("id")
    form = st.session_state.form
    query = prepare(dict(form))
    query["avatar"] = form.get("avatar") or role_avatar(query["role"])
    if form.get("photo"):
        query["photo"] = form["photo"]
    if clean_telegram(form.get("telegram")):
        query["telegram"] = clean_telegram(form["telegram"])
    if previous_id in get_matcher().by_id:
        query["id"] = previous_id
    if publish and HALL_ENABLED:
        try:
            query = join_hall(query, st.session_state.lang)
        except (RuntimeError, OSError):
            log.warning("hall_join_failed", exc_info=True)
            st.session_state.hall_failed = True
    st.session_state.query = query
    st.session_state.focus_results = True
    st.session_state.view_pick = st.session_state.view_last = st.session_state.form.get("format", "one")
    st.session_state.group_seen, st.session_state.group_joined = [], None
    reset_feedback()


def fill_example(goal: str) -> None:
    ex = EXAMPLES[goal]
    form = dict(FIELDS)
    form.update({k: (list(v) if isinstance(v, list) else v) for k, v in ex.items() if k != "about"})
    form["about"] = ex["about"][st.session_state.lang]
    st.session_state.form = form
    st.session_state.answered = set(FIELDS)
    st.session_state.survey_step = None
    clear_widgets()
    build_query(publish=False)


def pick_example() -> None:
    goal = st.session_state.ex_pick
    if goal:
        fill_example(goal)
    st.session_state.ex_pick = None


def _goal() -> str:
    q = st.session_state.query
    return q["goal"] if q else ""


# ---------------------------------------------------------------- пошаговый опрос
# Один вопрос на экране. Вопрос с одним ответом сразу переходит к следующему,
# вопрос с несколькими ответами — по кнопке «Далее». В конце — 5 человек.
SINGLE = {"goal", "format", "role", "experience"}
EXP_BUCKETS = [0, 1, 3, 7, 12]  # «без опыта», «до 2», «2–5», «5–10», «10+» → годы для подбора
POPULAR_STACK = ["python", "javascript", "typescript", "react", "java", "go", "sql", "docker",
                 "kotlin", "swift", "figma", "excel", "jira", "product_analytics"]


def survey_steps(goal: str) -> list[str]:
    steps = ["goal", "format", "role", "experience", "avatar", "seeking_roles", "stack", "interests", "slots",
             "about"]
    # «Кого вы ищете?» спрашиваем только тех, кто нанимает или ищет кофаундера
    return [x for x in steps if x != "seeking_roles" or goal in ("hire", "find_cofounder")]


def start_survey(fresh: bool = False) -> None:
    s = st.session_state
    if fresh:
        s.form, s.answered = dict(FIELDS), set()
    s.survey_step = 0
    clear_widgets()


def _next_step() -> None:
    s = st.session_state
    if s.survey_step + 1 >= len(survey_steps(s.form["goal"])):
        s.survey_step = None
        build_query()
    else:
        s.survey_step += 1


def answer(field: str, value) -> None:
    st.session_state.form[field] = value
    st.session_state.answered.add(field)
    _next_step()


def answer_multi(field: str, *keys: str) -> None:
    values: list = []
    for key in keys:
        for v in st.session_state.get(key) or []:
            if v not in values:
                values.append(v)
    answer(field, values)


def answer_about(about_key: str, name_key: str, tg_key: str) -> None:
    st.session_state.form["name"] = st.session_state.get(name_key, "")
    st.session_state.form["telegram"] = clean_telegram(st.session_state.get(tg_key, ""))
    answer("about", st.session_state.get(about_key, ""))


def step_back() -> None:
    s = st.session_state
    s.survey_step = s.survey_step - 1 if s.survey_step > 0 else None


PHOTO_URI = re.compile(r"^data:image/webp;base64,[A-Za-z0-9+/=]+$")


def face_html(p: dict) -> str:
    """Фото (только наше, пересохранённое в WEBP) или эмодзи."""
    photo = p.get("photo") or ""
    if PHOTO_URI.match(photo):
        return f'<img src="{photo}" alt="">'
    return html.escape(profile_avatar(p))


def on_avatar_pick() -> None:
    s = st.session_state
    chosen = s.get("sv_avatar_pick")
    if chosen:
        s.form["photo"] = ""
        answer("avatar", chosen)


def on_photo(key: str) -> None:
    s = st.session_state
    f = s.get(key)
    if f is None:
        return
    uri = photo_data_uri(f.getvalue())
    if uri:
        s.form["photo"] = uri
    else:
        s.photo_bad = True


def clear_photo() -> None:
    st.session_state.form["photo"] = ""
    st.session_state.photo_nonce += 1  # новый ключ — загрузчик забывает файл


def on_autofill() -> None:
    """Анкета из текста: заполняем все поля и сразу показываем подборку — поправить можно потом."""
    s = st.session_state
    text = (s.get("af_text") or "").strip()
    if len(text) < 20:
        s.af_short = True
        return
    data = autofill(text)
    form = dict(FIELDS)
    form.update({k: data[k] for k in ("role", "experience", "goal", "stack", "interests", "seeking_roles", "about")})
    form["name"] = s.form.get("name", "")
    s.form, s.answered, s.survey_step = form, set(FIELDS), None
    s.af_note = data
    log.info("autofill source=%s goal=%s role=%s", data["source"], data["goal"], data["role"])
    clear_widgets()
    build_query()


def render_autofill(lang: str) -> None:
    s = st.session_state
    if not s.get("af_open"):
        st.button(t(lang, "af_open"), key="af_toggle", type="tertiary",
                  on_click=lambda: s.update(af_open=True))
        return
    with st.container(key="af_box"):
        st.text_area(t(lang, "af_label"), key="af_text", height=120, placeholder=t(lang, "af_ph"))
        if s.pop("af_short", False):
            st.warning(t(lang, "af_empty"))
        st.button(t(lang, "af_go"), key="af_go", type="primary", icon=":material/bolt:", on_click=on_autofill)
        st.caption(t(lang, "af_privacy"))


def render_af_note(q: dict, lang: str) -> None:
    """Что поняли из текста — одной строкой, чтобы человек сразу увидел ошибку."""
    data = st.session_state.pop("af_note", None)
    if not data:
        return
    parts = [role_label(q["role"], lang), exp_short(q["experience"], lang), goal_label(q["goal"], lang)]
    parts += [stack_label(x) for x in q["stack"][:4]] + [interest_label(i, lang) for i in q["interests"][:2]]
    head = t(lang, "af_note_ai" if data.get("source") == "claude" else "af_note_rules")
    st.info(f"{head} {' · '.join(parts)}. {t(lang, 'af_check')}", icon=":material/auto_awesome:")


def render_avatar_step(lang: str) -> None:
    """Шаг-шутка: у роли есть свой зверь. Можно взять его, выбрать другого или загрузить фото."""
    s = st.session_state
    role = s.form["role"]
    current = s.form.get("avatar") or role_avatar(role)
    st.html(f"""<div class="mm-me"><span class="mm-me-face">{face_html({**s.form, "avatar": current})}</span>
        <p><b>{html.escape(role_label(role, lang))}</b> — {html.escape(role_joke(role, lang))}</p></div>""")
    s.setdefault("sv_avatar_pick", None)
    st.pills(t(lang, "avatar_other"), avatar_choices(role), key="sv_avatar_pick", on_change=on_avatar_pick)
    key = f"sv_photo_{s.photo_nonce}"
    st.file_uploader(t(lang, "photo_upload"), type=["jpg", "jpeg", "png", "webp"], key=key,
                     on_change=on_photo, args=(key,), max_upload_size=6)
    if s.pop("photo_bad", False):
        st.warning(t(lang, "photo_bad"))
    st.caption(t(lang, "photo_note"))
    c1, c2 = st.columns(2)
    c1.button(t(lang, "avatar_take", a="" if s.form.get("photo") else current).strip(), type="primary",
              width="stretch", key="sv_next_avatar", on_click=answer, args=("avatar", current))
    if s.form.get("photo"):
        c2.button(t(lang, "photo_clear"), width="stretch", key="sv_photo_clear", on_click=clear_photo)


def stack_options(role: str) -> list[str]:
    """Технологии своей роли — кнопками, остальные — в списке «Другие технологии»."""
    own = [s for s in STACK if role in STACK_ROLES.get(s, ())]
    return own[:16] if len(own) >= 3 else POPULAR_STACK


def render_survey(lang: str) -> None:
    s = st.session_state
    steps = survey_steps(s.form["goal"])
    i = min(s.survey_step, len(steps) - 1)
    field = steps[i]
    with st.container(key="survey"):
        st.button(t(lang, "back"), icon=":material/arrow_back:", on_click=step_back, key="sv_back")
        section_art("badge")
        st.caption(t(lang, "step_of", i=i + 1, n=len(steps)))
        if HALL_ENABLED and i == 0:
            st.caption({"ru": "После заполнения вашу анкету увидят участники этого события.",
                        "kk": "Толтырылған сауалнамаңызды осы іс-шараның қатысушылары көреді.",
                        "en": "Once completed, your profile will be visible to participants at this event."}[lang])
        st.progress((i + 1) / len(steps))
        st.subheader(t(lang, f"q_{field}"), anchor=False)

        if field == "avatar":
            render_avatar_step(lang)
            return
        if field == "goal":
            render_autofill(lang)
            with st.container(key="onboarding"):  # быстрый пример — прямо в анкете, а не на главной
                st.pills(t(lang, "examples"), list(EXAMPLES), format_func=lambda g: t(lang, f"ex_{g}"),
                         key="ex_pick", on_change=pick_example)
        if field in SINGLE:
            if field == "goal":
                options, label = list(GOALS), lambda g: goal_label(g, lang)
            elif field == "format":
                options, label = ["one", "group"], lambda f: t(lang, f"fmt_{f}")
                st.caption(t(lang, "hint_format"))
            elif field == "role":
                options, label = list(ROLES), lambda r: role_label(r, lang)
            else:
                options, label = EXP_BUCKETS, lambda b: t(lang, f"exp_{b}")
            current = s.form[field]
            if field == "experience":
                current = min(EXP_BUCKETS, key=lambda b: abs(b - current))
            chosen = field in s.answered
            cols = st.columns(3 if field == "role" else 1 if field == "format" else 2)
            for n, opt in enumerate(options):
                cols[n % len(cols)].button(
                    label(opt), key=f"sv_{field}_{opt}", on_click=answer, args=(field, opt),
                    type="primary" if chosen and opt == current else "secondary", width="stretch")
            return

        if field == "about":
            about_key, name_key = f"sv_about_{lang}", f"sv_name_{lang}"
            s.setdefault(about_key, s.form["about"])
            s.setdefault(name_key, s.form["name"])
            st.caption(t(lang, "hint_about"))
            st.text_area(t(lang, "about"), key=about_key, placeholder=t(lang, "about_ph"), height=110,
                         label_visibility="collapsed")
            st.text_input(t(lang, "name"), key=name_key)
            tg_key = f"sv_tg_{lang}"
            s.setdefault(tg_key, s.form.get("telegram", ""))
            st.text_input(t(lang, "tg_label"), key=tg_key, placeholder="@username", help=t(lang, "tg_help"))
            if s.get(tg_key) and not clean_telegram(s.get(tg_key)):
                st.caption(t(lang, "tg_bad"))
            finish = "submit_group" if s.form.get("format") == "group" else "submit"
            st.button(t(lang, finish), type="primary", width="stretch", key="sv_finish",
                      on_click=answer_about, args=(about_key, name_key, tg_key))
            return

        # вопросы с несколькими ответами
        if field == "seeking_roles":
            options, label = HIREABLE_ROLES + ["founder"], lambda r: role_label(r, lang)
        elif field == "interests":
            options, label = list(INTERESTS), lambda x: interest_label(x, lang)
        elif field == "slots":
            options, label = EVENT_SLOTS, str
        else:
            options, label = stack_options(s.form["role"]), stack_label
        key = f"sv_{field}_{lang}"
        s.setdefault(key, [v for v in s.form[field] if v in options])
        st.caption(t(lang, "hint_multi"))
        st.pills(t(lang, f"q_{field}"), options, selection_mode="multi", format_func=label,
                 key=key, label_visibility="collapsed")
        keys = [key]
        if field == "stack":
            more_key = f"sv_stack_more_{lang}"
            s.setdefault(more_key, [v for v in s.form["stack"] if v not in options])
            st.multiselect(t(lang, "stack_more"), [x for x in STACK if x not in options],
                           format_func=stack_label, key=more_key, placeholder=t(lang, "choose"))
            keys.append(more_key)
        c1, c2 = st.columns(2)
        c1.button(t(lang, "next") + " →", type="primary", width="stretch", key=f"sv_next_{field}",
                  on_click=answer_multi, args=(field, *keys))
        c2.button(t(lang, "skip_question"), width="stretch", key=f"sv_skip_{field}", on_click=_next_step)


# ---------------------------------------------------------------- подборка: познакомиться / пропустить / новые
def me_key(q: dict | None) -> str:
    """Чей это запрос: id в живом зале или, пока его нет, роль+цель+имя (для стабильного демо-ответа)."""
    q = q or {}
    return q.get("id") or f"{q.get('role')}:{q.get('goal')}:{q.get('name', '')}"


def mutual_with(p: dict, score: float) -> bool:
    q = st.session_state.query or {}
    return is_mutual(p, score, q.get("id"), me_key(q), feedback_store().all())


def on_meet(pid: str, name: str, score: float = 0.0) -> None:
    s = st.session_state
    s.met.append((pid, name))
    feedback_store().add("met", pid, _goal(), from_id=(s.query or {}).get("id"))
    s.toast = "toast_meet"
    p = matcher.by_id.get(pid)
    if p is not None:
        if mutual_with(p, score):
            s.toast = "toast_mutual"
        if bingo_on_meet(p):
            s.toast = "toast_bingo"


# ---------------------------------------------------------------- нетворкинг-бинго
def bingo_state() -> dict:
    """Одна карточка на событие на протяжении сессии, включая просмотр до заполнения анкеты."""
    s = st.session_state
    ev = current_event()
    event_id = ev["id"]
    boards = s.setdefault("bingo_boards", {})
    if event_id not in boards:
        here = event_attendees(ev)
        pool = [p for p in matcher.profiles if p["id"] in here and p["id"] not in s.my_ids]
        if s.query:
            pool = [m.profile for m in matcher.recommend(s.query, k=60, exclude=set(s.my_ids) | (set(matcher.by_id) - here))]
        boards[event_id] = {"card": bingo_card(pool, event_id, ev), "reach": bingo_reach(pool),
                            "done": {}, "won": False, "met_ids": set()}
    s.bingo = boards[event_id]
    return s.bingo


def bingo_on_meet(p: dict) -> bool:
    """Отмечает клетки; True — если только что собрана первая линия."""
    q = st.session_state.query
    if not q:
        return False
    b = bingo_state()
    if p["id"] in b["met_ids"]:
        return False
    b["met_ids"].add(p["id"])
    bingo_tick(b["card"], b["done"], p, b.get("reach"))
    return check_bingo_win(b)


def check_bingo_win(b: dict) -> bool:
    if not b["won"] and bingo_lines(b["done"]):
        b["won"] = True
        feedback_store().add("bingo", current_event()["id"], _goal())
        return True
    return False


def mark_activity(i: int) -> None:
    b = bingo_state()
    if is_activity(b["card"][i]):
        b["done"][str(i)] = ""
        if check_bingo_win(b):
            st.session_state.toast = "toast_bingo"


def render_bingo(lang: str) -> None:
    b = bingo_state()
    st.subheader(f'{t(lang, "bingo")} · {len(b["done"])}/9', anchor=False)
    st.caption(t(lang, "bingo_rules"))
    with st.container(key="bingo_grid"):
        for i, task in enumerate(b["card"]):
            who = b["done"].get(str(i))
            label = bingo_label(task, lang)
            if is_activity(task) and who is None:
                st.button(label, key=f"activity_{current_event()['id']}_{i}", icon=":material/add:",
                          width="stretch", on_click=mark_activity, args=(i,))
                continue
            cls = "mm-bc" + (" mm-done" if who is not None else "") + (" mm-free" if task == FREE else "")
            mark = f"<small>✓ {html.escape(who.split()[0] if who else '')}</small>" if who is not None else ""
            st.html(f'<div class="{cls}"><span>{html.escape(label)}</span>{mark}</div>')
    if b["won"]:
        st.success(t(lang, "bingo_won"), icon=":material/emoji_events:")


def on_skip(pid: str, role: str) -> None:
    st.session_state.skipped.append(pid)
    st.session_state.rejected_roles.append(role)
    feedback_store().add("not_fit", pid, _goal())
    st.session_state.toast = "toast_skip"


def on_new_people(shown: list[str]) -> None:
    """Следующие 5: все показанные уходят из подбора, пропуски учитываются в оценке."""
    s = st.session_state
    s.excluded.extend(pid for pid in shown if pid not in s.excluded)
    s.skipped, s.batch_rejected = [], list(s.rejected_roles)
    s.batch_no += 1
    s.pop("claude_result", None)
    s.toast, s.focus_results = "toast_new", True


# ---------------------------------------------------------------- вспомогательное
def chips(items: list[str]) -> str:
    return "".join(f'<span class="mm-chip">{html.escape(x)}</span>' for x in items)


def exp_short(n: int, lang: str) -> str:
    if n <= 0:
        return t(lang, "no_exp")
    return years_ru(n) if lang == "ru" else f"{n} жыл" if lang == "kk" else f"{n} yrs"


def next_opener(pid: str) -> None:
    st.session_state.ice[pid] = st.session_state.ice.get(pid, 0) + 1


# лаймовые и синие точки разлетаются из центра один раз — в момент мэтча
CONFETTI = [(-210, -120), (-150, -170), (-60, -190), (40, -185), (140, -160), (220, -110), (250, -20),
            (-250, -30), (-190, 70), (200, 80), (-100, 120), (110, 125), (0, -140), (-30, 150)]


def render_match(p: dict, m, lang: str, me: str, first: str) -> None:
    """Яркий момент мэтча: чёрный блок, наклейка «МЭТЧ», два аватара, сцепленные как звенья логотипа."""
    s = st.session_state
    seen = s.setdefault("match_seen", [])
    burst = p["id"] not in seen
    if burst:
        seen.append(p["id"])
    dots = "".join(
        f'<i class="mm-dot-c{n % 3}" style="--x:{x}px; --y:{y}px; --d:{n * 25}ms"></i>'
        for n, (x, y) in enumerate(CONFETTI)) if burst else ""
    tags = [stack_label(x) for x in m.shared_stack[:3]] + [interest_label(i, lang) for i in m.shared_interests[:2]]
    if m.common_slots:
        tags.append("🕑 " + ", ".join(m.common_slots[:2]))
    chips_html = "".join(f'<span class="mm-match-chip">{html.escape(x)}</span>' for x in tags)
    st.html(f"""<div class="mm-match{' mm-burst' if burst else ''}" role="status">
        <div class="mm-confetti" aria-hidden="true">{dots}</div>
        <span class="mm-match-sticker">{t(lang, 'match_sticker')}</span>
        <div class="mm-match-faces" aria-hidden="true"><span class="mm-mf mm-mf-a">{me}</span><span class="mm-mf mm-mf-b">{face_html(p)}</span></div>
        <p class="mm-match-title">{t(lang, 'match_title')}</p>
        <p class="mm-match-sub">{t(lang, 'match_sub', name=html.escape(first))}</p>
        <div class="mm-match-chips">{chips_html}</div>
        </div>""")


def render_card(m, lang: str, position: int, count: int, met: bool) -> None:
    p = m.profile
    meta = " · ".join(x for x in (role_label(p["role"], lang), exp_short(p["experience"], lang),
                                   p.get("company")) if x)
    s = st.session_state
    with st.container(border=True, key=f"card_{p['id']}"):
        st.html(f"""
            <div class="mm-person">
                <span class="mm-avatar" title="{html.escape(role_label(p['role'], lang) + ' — ' + role_joke(p['role'], lang))}">{face_html(p)}</span>
                <div class="mm-person-body"><span class="mm-goal">{GOAL_VERB[lang][p['goal']]}</span><span class="mm-score">{round(m.score * 100)}% {t(lang, 'match')}</span>
                    <h3>{html.escape(p['name'])}</h3><p>{html.escape(meta)}</p></div>
                <span class="mm-position">{t(lang, 'card_index', i=position, n=count)}</span>
            </div>
            <div class="mm-reason"><strong>{t(lang, 'why')}</strong>
                <p>{html.escape(m.explanation)}</p></div>
        """)
        tags = [stack_label(s) for s in m.shared_stack[:4]] + \
               [interest_label(i, lang) for i in m.shared_interests[:3]]
        if tags:
            st.markdown(chips(tags), unsafe_allow_html=True)
        st.markdown(f"<p class='mm-label'>{t(lang, 'icebreaker')}</p>", unsafe_allow_html=True)
        st.code(opener(m.icebreaker, p["name"], lang, s.ice.get(p["id"], 0)), language=None, wrap_lines=True)
        dice, when = st.columns([1, 2], vertical_alignment="center")
        dice.button(t(lang, "ice_more"), key=f"ice_{p['id']}", type="tertiary", on_click=next_opener,
                    args=(p["id"],))
        when.caption(t(lang, "slot", slots=", ".join(m.common_slots)) if m.common_slots
                     else t(lang, "no_slot"))
        if met:
            mutual = mutual_with(p, m.score)
            first = p["name"].split()[0]
            me = face_html(s.query or {})
            if not mutual:
                st.html(f"""<div class="mm-met mm-wait" aria-hidden="true">
                    <span class="mm-met-a">{me}</span><span class="mm-met-h">⏳</span>
                    <span class="mm-met-b">{face_html(p)}</span></div>""")
            if mutual:
                render_match(p, m, lang, me, first)
                url = telegram_url(p.get("telegram", ""))
                if url:
                    st.link_button(t(lang, "tg_write"), url, type="primary", width="stretch", icon=":material/send:")
                else:
                    st.caption(t(lang, "tg_none" if p.get("live") else "tg_demo"))
            else:
                st.info(t(lang, "pending", name=first), icon=":material/schedule:")
                if p.get("live") and not (s.query or {}).get("id"):
                    st.caption(t(lang, "pending_hall"))
            return
        b1, b2 = st.columns(2)
        b1.button(t(lang, "meet"), key=f"meet_{p['id']}", on_click=on_meet, type="primary",
                  args=(p["id"], p["name"], m.score), width="stretch", icon=":material/handshake:")
        b2.button(t(lang, "skip"), key=f"skip_{p['id']}", on_click=on_skip,
                  args=(p["id"], p["role"]), width="stretch", icon=":material/close:")


# ---------------------------------------------------------------- страница подбора
def page_match(lang: str) -> None:
    s = st.session_state
    if s.get("survey_step") is not None:
        render_survey(lang)
        return
    q = s.query
    if (q is None and not s.get("preview_bingo")) or s.show_events:
        event_cover(lang)
        if q is not None:
            st.button("← " + t(lang, "results_title"), key="events_back", on_click=lambda: s.update(show_events=False))
        render_events(lang)
        return
    render_results(q, lang)


# ---------------------------------------------------------------- ближайшие события
MONTHS = {
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
           "октября", "ноября", "декабря"],
    "kk": ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек",
           "қазан", "қараша", "желтоқсан"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def today() -> date:
    """MEETMATCH_TODAY=2026-11-20 — чтобы показать прототип «как в день хакатона» и в тестах."""
    fixed = os.environ.get("MEETMATCH_TODAY")
    return date.fromisoformat(fixed) if fixed else date.today()


def event_list() -> list[dict]:
    return upcoming(get_events(), today())


def current_event() -> dict:
    events = get_events()
    by_id = {e["id"]: e for e in events}
    chosen = by_id.get(st.session_state.get("event") or "")
    if chosen:
        return chosen
    soon = upcoming(events, today())
    return by_id.get(DEFAULT_EVENT) if not soon or soon[0]["id"] == DEFAULT_EVENT else soon[0]


def event_date(e: dict, lang: str) -> str:
    a, b = date.fromisoformat(e["start"]), date.fromisoformat(e["end"])
    m = MONTHS[lang]
    if lang == "en":
        day = f"{m[a.month - 1]} {a.day}" + (f"–{b.day}" if b != a else "")
    elif lang == "kk":
        day = f"{a.day}" + (f"–{b.day}" if b != a else "") + f" {m[a.month - 1]}"
    else:
        day = f"{a.day}" + (f"–{b.day}" if b != a else "") + f" {m[a.month - 1]}"
    return day + (f", {e['time']}" if e.get("time") else "")


def event_when(e: dict, lang: str) -> str:
    now = today()
    a, b = date.fromisoformat(e["start"]), date.fromisoformat(e["end"])
    if a <= now <= b:
        return t(lang, "event_now")
    days = (a - now).days
    return t(lang, "event_tomorrow") if days == 1 else t(lang, "event_days", n=days)


def event_attendees(e: dict) -> set[str]:
    return attendee_ids(e, matcher.profiles)


def on_pick_event(event_id: str, bingo: bool = False) -> None:
    """Анкета заполняется один раз: при смене события подбор просто пересчитывается."""
    s = st.session_state
    s.event, s.show_events = event_id, False
    s.preview_bingo = bingo
    s.activity_tabs = t(s.lang, "bingo" if bingo else "match_nav")
    s.excluded, s.skipped, s.rejected_roles, s.batch_rejected, s.met = [], [], [], [], []
    s.batch_no, s.group_seen, s.group_joined = 1, [], None
    s.pop("claude_result", None)
    log.info("event_pick event=%s has_profile=%s", event_id, s.query is not None)
    if s.query is None:
        if not bingo:
            start_survey(fresh=not s.answered)
    else:
        s.query.pop("id", None)
        for pid in s.my_ids:
            if matcher.by_id.get(pid, {}).get("event") == event_id:
                s.query["id"] = pid
                break
        s.focus_results = True


GOOD_MATCH = 0.5  # «подходящий» человек: совпадение от 50% (так на ручной разметке выглядят «стоит познакомиться»)


def event_fits(q: dict) -> dict[str, int]:
    """«Куда пойти»: сколько подходящих вам людей на каждом событии. Анкета одна — подбор на всех."""
    s = st.session_state
    sig = json.dumps([{k: v for k, v in q.items() if k != "photo"}, len(matcher.profiles), s.my_ids],
                     sort_keys=True, default=str)
    cached = s.get("event_fits")
    if cached and cached[0] == sig:
        return cached[1]
    fits = {}
    for e in event_list():
        here = event_attendees(e)
        recs = matcher.recommend(q, k=60, exclude=set(s.my_ids) | (set(matcher.by_id) - here))
        fits[e["id"]] = sum(m.score >= GOOD_MATCH for m in recs)
    s.event_fits = (sig, fits)
    return fits


def event_card(e: dict, lang: str, selected: bool, fit: int | None = None, best: bool = False) -> None:
    """Карточка события: у всех одна высота — заголовок и описание обрезаются до двух строк."""
    when = event_when(e, lang)
    now = when == t(lang, "event_now")
    people = (f"<b class='mm-fit'>{t(lang, 'event_fit', n=fit)}</b>" if fit is not None
              else t(lang, "event_people", n=len(event_attendees(e))))
    extra = [people, html.escape(e.get("venue") or t(lang, "city"))]
    if e.get("price") == "free":
        extra.append(t(lang, "event_free"))
    if e.get("status") == "proposed":
        extra.append(t(lang, "event_unconfirmed"))
    with st.container(key=f"event_{e['id']}"):
        st.html(f"""
            <div class="mm-ev{' mm-ev-picked' if selected else ''}">
              <div class="mm-ev-meta"><span class="mm-ev-type">{t(lang, f"ev_{e['type']}")}</span>
                <span class="mm-ev-when{' mm-ev-now' if now else ''}">{when}</span></div>
              <h4><a class="mm-ev-link" href="{html.escape(e['url'])}" target="_blank" rel="noopener"
                     title="{html.escape(t(lang, 'event_site'))}: {html.escape(e['title'])}">{html.escape(e['title'])}</a></h4>
              <p class="mm-ev-about">{html.escape(e['about'].get(lang) or e['about']['ru'])}</p>
              <p class="mm-ev-foot mm-ev-date"><b>{event_date(e, lang)}</b>
                <a href="{html.escape(e['url'])}" target="_blank" rel="noopener">{t(lang, 'event_site')} ↗</a></p>
              <p class="mm-ev-foot mm-ev-more">{' · '.join(extra)}</p>
              {f'<span class="mm-ev-best">{t(lang, "event_best")}</span>' if best else ''}
            </div>""")
        if selected:
            st.caption("✓ " + t(lang, "going"))
        st.button(t(lang, "event_go"), key=f"ev_go_{e['id']}",
                  type="primary" if selected else "secondary", width="stretch",
                  on_click=on_pick_event, args=(e["id"],))
        st.button(t(lang, "remove_event" if selected else "attend"), key=f"attend_{e['id']}",
                  icon=":material/remove:" if selected else ":material/add:",
                  type="tertiary" if selected else "primary", width="stretch",
                  on_click=set_attending, args=(e["id"], not selected))
        st.button(t(lang, "bingo"), key=f"open_bingo_{e['id']}", type="tertiary", icon=":material/grid_view:",
                  on_click=on_pick_event, args=(e["id"], True))


def render_events(lang: str) -> None:
    s = st.session_state
    events = event_list()
    fits = event_fits(s.query) if s.query is not None else None
    if fits:  # анкета есть — сначала события, где для вас больше людей
        events = sorted(events, key=lambda e: (-fits[e["id"]], e["start"]))
    with st.container(key="events_heading"):
        section_art("ticket")
        st.subheader(t(lang, "events_title"), anchor="mm-events")
    mine = [e for e in events if e["id"] in s.attending]
    scope = st.radio(t(lang, "events_title"), ["all", "mine"],
                     format_func=lambda v: (f"{t(lang, 'my_events')} · {len(mine)}" if v == "mine"
                                            else f"{t(lang, 'all_events')} · {len(events)}"),
                     horizontal=True, label_visibility="collapsed", key="event_scope")
    shown = mine if scope == "mine" else events
    if not shown:
        st.caption(t(lang, "mine_empty" if scope == "mine" else "no_events"))
    top = events[0]["id"] if fits and fits[events[0]["id"]] else None
    for row in range(0, len(shown), 3):
        for col, e in zip(st.columns(3, gap="medium"), shown[row:row + 3]):
            with col:
                event_card(e, lang, selected=e["id"] in s.attending,
                           fit=fits[e["id"]] if fits else None, best=e["id"] == top)


# ---------------------------------------------------------------- встреча в компании
def on_group_join(key: str) -> None:
    feedback_store().add("group", key, _goal())
    st.session_state.group_joined = key
    st.session_state.toast = "toast_group"


def on_group_other(ids: list[str]) -> None:
    s = st.session_state
    s.group_seen.extend(ids)
    s.group_joined = None


def render_group(q: dict, lang: str) -> None:
    """Компания из 3–4 человек с той же целью: время, место, тема и общая первая фраза."""
    s = st.session_state
    here = event_attendees(current_event())
    g = suggest_group(q, [p for p in matcher.profiles if p["id"] in here], exclude=s.group_seen + s.my_ids)
    if g is None:
        st.info(t(lang, "group_none"))
        if s.group_seen:
            st.button(t(lang, "group_other"), on_click=lambda: s.update(group_seen=[]), key="group_reset")
        return
    topic = interest_label(g.topic, lang) if g.topic else GROUP_TITLE[lang][q["goal"]]
    everyone = [q] + g.members
    free = sum(1 for p in everyone if g.slot in (p.get("slots") or []))
    with st.container(border=True, key="group_card"):
        st.markdown(f"### {GROUP_TITLE[lang][q['goal']]}")
        lines = [t(lang, "group_topic", topic=topic), t(lang, "group_where", table=g.table)]
        if g.slot:
            lines.insert(0, t(lang, "group_when", slot=g.slot, n=free, total=len(everyone)))
        st.markdown("  \n".join(lines))
        for m in g.members:
            shared = [interest_label(i, lang) for i in g.shared.get(m["id"], [])]
            meta = ", ".join([role_label(m["role"], lang), exp_short(m["experience"], lang)]
                             + ([t(lang, "group_shared", x=", ".join(shared))] if shared else []))
            st.markdown(f"- **{html.escape(m['name'])}** — {html.escape(meta)}")
        st.markdown(f"<p class='mm-label'>{t(lang, 'icebreaker')}</p>", unsafe_allow_html=True)
        st.code(t(lang, "group_icebreaker", topic=topic), language=None, wrap_lines=True)
        going = feedback_store().going(g.key)
        if going:
            st.caption(t(lang, "group_going", n=going))
        if s.group_joined == g.key:
            st.success(t(lang, "group_joined", table=g.table, slot=g.slot or "—"), icon=":material/groups:")
        else:
            b1, b2 = st.columns(2)
            b1.button(t(lang, "group_join"), type="primary", width="stretch", key="group_join",
                      icon=":material/groups:", on_click=on_group_join, args=(g.key,))
            b2.button(t(lang, "group_other"), width="stretch", key="group_other", icon=":material/refresh:",
                      on_click=on_group_other, args=([m["id"] for m in g.members],))


def on_view_change() -> None:
    s = st.session_state
    if s.view_pick is None:  # переключатель нельзя «отжать»
        s.view_pick = s.get("view_last") or s.form.get("format", "one")
    s.view_last = s.view_pick


def render_results(q: dict | None, lang: str) -> None:
    s = st.session_state
    if s.get("toast"):
        st.toast(t(lang, s.pop("toast")))
    ev = current_event()
    here = event_attendees(ev)
    # Заголовок, над ним — для какого события подбор; под ним — одна строка управления.
    st.html(f"<p class='mm-eyebrow'><a class='mm-ev-link' href='{html.escape(ev['url'])}' target='_blank' "
            f"rel='noopener'><b>{html.escape(ev['title'])} ↗</b></a> · {event_date(ev, lang)} · "
            f"{t(lang, 'event_people', n=len(here))}</p>")
    pending = pending_reviews()
    if pending:  # оповещение: встреча была — расскажите, как прошла
        first = pending[0][1].split()[0]
        st.info(t(lang, "fb_remind", name=first) if len(pending) == 1 else t(lang, "fb_remind_n", n=len(pending)),
                icon=":material/notifications_active:")
    fb_label = t(lang, "fb_tab") + (f" · {len(pending)}" if pending else "")
    matches, bingo, reviews = st.tabs([t(lang, "match_nav"), t(lang, "bingo"), fb_label],
                                      key="activity_tabs", on_change="rerun")
    with bingo:
        render_bingo(lang)
    with reviews:
        render_reviews(lang)
    if matches.open:
        with matches:
            if q is None:
                st.button(t(lang, "hero_cta"), on_click=start_survey, type="primary", key="event_survey")
            else:
                render_matches(q, lang, ev, here)


# ---------------------------------------------------------------- отзывы о встречах
def _review_key(pid: str) -> str:
    return f"{current_event()['id']}:{pid}"


def pending_reviews() -> list[tuple[str, str]]:
    s = st.session_state
    return [(pid, name) for pid, name in s.met if _review_key(pid) not in s.reviewed]


def save_review(pid: str, happened: bool) -> None:
    s = st.session_state
    k = f"fb_{pid}"
    stars = s.get(f"{k}_stars")
    review_store().add(event=current_event()["id"], candidate_id=pid, happened=happened,
                       rating=stars + 1 if stars is not None else None, learned=s.get(f"{k}_learned", ""),
                       helped=s.get(f"{k}_helped"), next_step=s.get(f"{k}_next"))
    s.reviewed.append(_review_key(pid))
    s.toast = "fb_thanks"


def render_reviews(lang: str) -> None:
    s = st.session_state
    pending = pending_reviews()
    if not s.met:
        st.caption(t(lang, "fb_empty"))
        return
    st.caption(t(lang, "fb_hint"))
    for pid, name in pending:
        p = matcher.by_id.get(pid, {"name": name, "role": ""})
        k = f"fb_{pid}"
        with st.container(border=True, key=f"review_{pid}"):
            st.html(f"""<div class="mm-person"><span class="mm-avatar">{face_html(p)}</span>
                <div class="mm-person-body"><h3>{html.escape(name)}</h3>
                <p>{t(lang, 'fb_how')}</p></div></div>""")
            with st.form(f"{k}_form", border=False):
                st.markdown(f"**{t(lang, 'fb_rate')}**")
                st.feedback("stars", key=f"{k}_stars")
                st.text_area(t(lang, "fb_learned"), key=f"{k}_learned", placeholder=t(lang, "fb_learned_ph"),
                             max_chars=500, height=90)
                st.radio(t(lang, "fb_helped"), ["yes", "partly", "no"], key=f"{k}_helped", horizontal=True,
                         index=None, format_func=lambda v: t(lang, f"fb_helped_{v}"))
                st.radio(t(lang, "fb_next"), ["yes", "maybe", "no"], key=f"{k}_next", horizontal=True,
                         index=None, format_func=lambda v: t(lang, f"fb_next_{v}"))
                st.form_submit_button(t(lang, "fb_send"), type="primary", on_click=save_review, args=(pid, True))
            st.button(t(lang, "fb_missed"), key=f"{k}_missed", type="tertiary", on_click=save_review,
                      args=(pid, False))
    done = len(s.met) - len(pending)
    if done:
        st.success(t(lang, "fb_done", n=done), icon=":material/check_circle:")


def render_matches(q: dict, lang: str, ev: dict, here: set[str]) -> None:
    s = st.session_state
    render_af_note(q, lang)
    if s.pop("hall_failed", False):
        st.error(t(lang, "hall_error"))
    with st.container(key="matches_heading"):
        section_art("conversation")
        st.header(t(lang, "results_title"), anchor="mm-results")
    view, other, edit = st.columns([2, 1, 1], vertical_alignment="center")
    other.button(t(lang, "home"), key="change_event", icon=":material/event:", width="stretch",
                 on_click=events_home)
    edit.button(f"{q.get('avatar') or role_avatar(q['role'])} {t(lang, 'edit_profile')}", key="edit_profile",
                on_click=start_survey, width="stretch")

    if s.pop("focus_results", False):
        # Уникальный маркер запускает переход и при повторном показе.
        st.html(f"""<script>/* {time.monotonic_ns()} */
        requestAnimationFrame(() => {{
            const heading = document.getElementById("mm-results");
            if (heading) {{
                heading.tabIndex = -1;
                heading.focus({{preventScroll:true}});
                heading.scrollIntoView({{block:"start", behavior:"instant"}});
            }}
        }});
        </script>""", unsafe_allow_javascript=True)
    if s.get("view_pick") is None:  # состояние виджета теряется, пока открыт дашборд
        s.view_pick = s.get("view_last") or s.form.get("format", "one")
    view.segmented_control(t(lang, "q_format"), ["one", "group"], key="view_pick", on_change=on_view_change,
                           format_func=lambda v: t(lang, f"view_{v}"), label_visibility="collapsed")
    if s.get("view_pick") == "group":
        st.caption(t(lang, "hint_format"))
        render_group(q, lang)
        return
    try:
        with st.spinner(t(lang, "loading")):
            # Streamlit exposes root-level secrets as environment variables after loading.
            st.secrets.load_if_toml_exists()
            api_key = os.getenv("ANTHROPIC_API_KEY") if os.getenv("MEETMATCH_AI") == "1" else None
            pool = matcher.recommend(q, k=15 if api_key else 5, lang=lang, exclude=set(s.excluded) | set(s.my_ids) | (set(matcher.by_id) - here),
                                     rejected_roles=s.batch_rejected)
            recs = pool[:5]
            signature = json.dumps([lang, q, [m.profile["id"] for m in pool]], sort_keys=True)
            cached = s.get("claude_result")
            if api_key and cached and cached[0] == signature and cached[1]:
                recs = cached[1]
    except (ValueError, RuntimeError, OSError):
        log.exception("recommend_failed")
        st.error(t(lang, "match_error"))
        st.button(t(lang, "retry"), key="retry_matches")
        return

    st.caption(f"{t(lang, 'batch_n', n=s.batch_no)} · {RECIPROCITY[lang][q['goal']]}")
    met_ids = {pid for pid, _ in s.met}
    shown = [m.profile["id"] for m in recs]
    visible = [(n, m) for n, m in enumerate(recs, 1) if m.profile["id"] not in s.skipped]
    for n, m in visible:
        render_card(m, lang, n, len(recs), met=m.profile["id"] in met_ids)
    if not recs:
        st.warning(t(lang, "no_more"))
        st.button(t(lang, "restart"), on_click=start_survey, args=(True,), key="restart")
    else:
        if not visible:
            st.info(t(lang, "all_skipped"))
        st.button(t(lang, "new_people"), icon=":material/refresh:", key=f"new_people_{s.batch_no}",
                  type="primary" if not visible else "secondary", width="stretch",
                  on_click=on_new_people, args=(shown,))

    if api_key and pool and (not cached or cached[0] != signature):
        try:
            improved = rerank(q, pool, lang, api_key, os.getenv("MEETMATCH_MODEL", "claude-haiku-5-5"))
        except Exception as exc:
            log.warning("claude_fallback error_type=%s", type(exc).__name__)
            improved = None
        s.claude_result = (signature, improved)
        if improved:
            st.rerun()

    if s.met:
        st.success(t(lang, "met_list", names=", ".join(name for _, name in s.met)))


    with st.container(border=True):
        st.subheader(t(lang, "schedule_title"), anchor=False)
        if not q.get("slots"):
            st.caption(t(lang, "schedule_none"))
        else:
            plan, left = plan_meetings([m for _, m in visible])
            if plan:
                st.dataframe(pd.DataFrame([{t(lang, "col_time"): slot,
                                            t(lang, "col_with"): f"{m.profile['name']} — {role_label(m.profile['role'], lang)}"}
                                           for slot, m in plan]), hide_index=True, width="stretch")
            if left:
                st.caption(t(lang, "schedule_left", names=", ".join(m.profile["name"] for m in left)))

    if ev["id"] == DEFAULT_EVENT:  # стенды партнёров есть только на хакатоне
        with st.container(border=True):
            st.subheader(t(lang, "booths_title"), anchor=False)
            for col, booth in zip(st.columns(2), recommend_booths(q, get_booths())):
                with col.container(border=True):
                    st.markdown(f"**{booth['name']}**")
                    st.caption(booth["desc"][lang])
                    st.markdown(chips([interest_label(i, lang) for i in booth["interests"][:3]]),
                                unsafe_allow_html=True)
                    if booth["hiring"]:
                        st.caption(t(lang, "booth_hiring",
                                     roles=", ".join(role_label(r, lang) for r in booth["hiring"])))


# ---------------------------------------------------------------- дашборд организатора
def _ratio(x: float, lang: str) -> str:
    text = f"{x:.1f}"
    return text.replace(".", ",") if lang in ("ru", "kk") else text


def page_dashboard(lang: str) -> None:
    if not st.session_state.organizer:  # вторая линия защиты: вкладка и так скрыта
        st.info(t(lang, "org_login"))
        return
    df = pd.DataFrame(matcher.profiles)
    events = feedback_store().all()
    stats = feedback_store().stats()

    who, out = st.columns([4, 1], vertical_alignment="center")
    who.caption(t(lang, "org_hello", name=st.session_state.organizer))
    out.button(t(lang, "org_logout"), key="org_logout", on_click=org_sign_out, width="stretch")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t(lang, "dash_people"), len(df))
    c2.metric(t(lang, "dash_feedback"), stats["total"])
    c3.metric(t(lang, "dash_met_rate"),
              f"{round(100 * stats['met_share'])}%" if stats["met_share"] is not None else "—")
    c4.metric(t(lang, "dash_groups"), stats["groups"])
    c5.metric(t(lang, "dash_bingo"), stats["bingo"])

    if HALL_ENABLED:
        live_count = sum(p.get("live") is True for p in matcher.profiles)
        st.metric(t(lang, "hall_count"), live_count)
        if st.session_state.pop("hall_cleared", False):
            st.success(t(lang, "hall_cleared"))
        if live_count and st.session_state.organizer != DEMO_ORGANIZER:
            with st.expander(t(lang, "hall_clear")):
                st.caption(t(lang, "hall_clear_note"))
                sure = st.checkbox(t(lang, "hall_confirm"), key="hall_confirm")
                if st.button(t(lang, "hall_clear"), key="hall_clear_btn", disabled=not sure):
                    try:
                        with hall_lock():
                            hall_store().clear()
                            get_matcher.clear()
                        log.info("hall_cleared by=%s", st.session_state.organizer)
                        st.session_state.hall_cleared = True
                        st.rerun()
                    except OSError:
                        log.warning("hall_clear_failed", exc_info=True)
                        st.error(t(lang, "hall_clear_error"))

    rv = review_store().stats()
    st.markdown(f"#### {t(lang, 'fb_dash')}")
    r1, r2, r3 = st.columns(3)
    r1.metric(t(lang, "fb_dash_n"), rv["happened"])
    r2.metric(t(lang, "fb_dash_avg"), f"{rv['avg']:.1f} ★" if rv["avg"] else "—")
    r3.metric(t(lang, "fb_dash_helped"), f"{round(100 * rv['helped_share'])}%" if rv["helped_share"] is not None else "—")
    for quote in rv["learned"]:
        st.markdown(f"> {html.escape(quote)}")

    st.markdown(f"#### {t(lang, 'dash_events')}")
    st.dataframe(pd.DataFrame([{t(lang, "col_event"): e["title"], t(lang, "col_date"): event_date(e, lang),
                                t(lang, "col_people"): len(event_attendees(e)),
                                t(lang, "col_live"): sum(1 for p in matcher.profiles if p.get("live")
                                                         and p.get("event", DEFAULT_EVENT) == e["id"])}
                               for e in event_list()]), hide_index=True, width="stretch")

    goals = df["goal"].value_counts()
    st.markdown(f"#### {t(lang, 'dash_tips')}")
    tips = []
    seekers, hirers = goals.get("find_job", 0), goals.get("hire", 0)
    if hirers and seekers / hirers > 1.3:
        tips.append(t(lang, "tip_jobs", x=_ratio(seekers / hirers, lang)))
    elif seekers and hirers / seekers > 1.3:
        tips.append(t(lang, "tip_jobs_rev"))
    mentees, mentors = goals.get("find_mentor", 0), goals.get("be_mentor", 0)
    if mentors and mentees / mentors > 1.1:
        tips.append(t(lang, "tip_mentors", x=_ratio(mentees / mentors, lang)))
    interests = df.explode("interests")["interests"]
    top = interests[~interests.isin(LOW_INFO_INTERESTS)].value_counts()
    if len(top):
        tips.append(t(lang, "tip_topic", topic=interest_label(top.index[0], lang)))
    if goals.get("find_cofounder", 0) >= 10:
        tips.append(t(lang, "tip_cofounder", n=goals["find_cofounder"]))
    for tip in tips:
        st.markdown(f"- {tip}")

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(f"#### {t(lang, 'dash_balance')}")
        pair_names = UI[lang]["pair"]
        bal = pd.DataFrame({"goal": [goal_label(g, lang) for g in goals.index],
                            "pair": [pair_names[PAIR_OF[g]] for g in goals.index],
                            "n": goals.values})
        bal = bal.sort_values(["pair", "n"])
        # Те же цвета пар, что и «ленты» карточек: один цветовой язык на весь продукт.
        fig = px.bar(bal, x="n", y="goal", color="pair", orientation="h", text="n",
                     color_discrete_map={pair_names[p]: c for p, c in PAIR_COLOR.items()})
        # подписи снаружи: на чёрных столбцах тёмный текст не виден; тонкий контур — для лаймовых
        fig.update_traces(textposition="outside", cliponaxis=False, marker_line_color="#030407",
                          marker_line_width=1)
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="",
                          legend=dict(orientation="h", yanchor="top", y=-0.22, x=0),
                          xaxis_title=t(lang, "dash_count"), yaxis_title="")
        st.plotly_chart(fig, width="stretch")
    with right:
        st.markdown(f"#### {t(lang, 'dash_stack')}")
        stack = df.explode("stack")["stack"].value_counts().head(12)[::-1]
        fig = px.bar(x=stack.values, y=[stack_label(s) for s in stack.index], orientation="h",
                     text=stack.values, color_discrete_sequence=[PRIMARY])
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                          xaxis_title=t(lang, "dash_count"), yaxis_title="")
        st.plotly_chart(fig, width="stretch")

    st.markdown(f"#### {t(lang, 'dash_map')}")
    ex = df.explode("interests")
    ex = ex[ex["interests"].notna()]
    table = pd.crosstab(ex["role"].map(lambda r: role_label(r, lang)),
                        ex["interests"].map(lambda i: interest_label(i, lang)))
    table = table[table.sum().sort_values(ascending=False).index[:14]]
    fig = px.imshow(table, text_auto=True, aspect="auto", color_continuous_scale=HEATMAP_SCALE)
    fig.update_layout(height=460, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False,
                      xaxis_title="", yaxis_title="")
    st.plotly_chart(fig, width="stretch")

    st.markdown(f"#### {t(lang, 'dash_feedback')}")
    if events:
        names = matcher.by_id

        def who(cid: str) -> str:  # у записи в компанию candidate_id — состав «p001+p002+p003»
            return ", ".join(names.get(i, {}).get("name", "") for i in cid.split("+"))
        st.dataframe(pd.DataFrame([{"time": e["time"][11:16], "": t(lang, e["action"]),
                                    "name": who(e["candidate_id"])}
                                   for e in reversed(events[-20:])]), hide_index=True, width="stretch")
    else:
        st.caption(t(lang, "dash_feedback_none"))


# ---------------------------------------------------------------- доступ организатора
MAX_ORG_ATTEMPTS = 5


# Общий демо-вход в панель организатора на время хакатона. Под ним видна вся статистика,
# но кнопки «Очистить зал» нет: этот код публичный.
DEMO_ORGANIZER, DEMO_ORG_CODE = "demo", "admin"


def organizer_codes() -> dict[str, str]:
    """Имя организатора → личный код. Коды лежат в секретах Streamlit ([organizers]), не в репозитории.
    MEETMATCH_ORGANIZER_CODE — запасной общий код из переменной окружения (Docker, локальный запуск)."""
    codes: dict[str, str] = {}
    try:
        section = st.secrets.get("organizers") or {}
        codes.update({str(k): str(v).strip() for k, v in section.items() if str(v).strip()})
    except Exception:  # секретов нет вовсе — это нормально, вход просто недоступен
        pass
    env = os.environ.get("MEETMATCH_ORGANIZER_CODE", "").strip()
    if env:
        codes.setdefault("organizer", env)
    codes.setdefault(DEMO_ORGANIZER, DEMO_ORG_CODE)  # общий код для показа жюри; зал им очистить нельзя
    return codes


def org_sign_in(code: str) -> bool:
    s = st.session_state
    if s.org_attempts >= MAX_ORG_ATTEMPTS:
        return False
    code = (code or "").strip().encode()
    name = None
    for who, real in organizer_codes().items():  # сравнение за постоянное время, без раннего выхода
        if code and hmac.compare_digest(code, real.encode()):
            name = who
    if name is None:
        s.org_attempts += 1
        log.warning("organizer_login_failed attempt=%s", s.org_attempts)
        return False
    s.organizer, s.org_attempts = name, 0
    log.info("organizer_login name=%s", name)  # имя — да, код — никогда
    return True


def org_sign_out() -> None:
    log.info("organizer_logout name=%s", st.session_state.organizer)
    st.session_state.organizer = None
    st.session_state.main_page = "match"


def how_it_works(lang: str) -> None:
    """Подбор на одной картинке: два круга — вы и собеседник, общая часть — то, что совпало."""
    weights = [("w_role", 34), ("w_stack", 28), ("w_exp", 17), ("w_text", 11), ("w_int", 10)]
    bars = "".join(f'<span style="flex:{w}" class="mm-w{n}"><b>{w}%</b>{t(lang, k)}</span>'
                   for n, (k, w) in enumerate(weights))
    st.html(f"""
        <div class="mm-venn"><span class="mm-c mm-c1">{t(lang, 'how_you')}</span>
          <span class="mm-c mm-c2">{t(lang, 'how_them')}</span><span class="mm-venn-lens"></span>
          <span class="mm-venn-mid">{t(lang, 'how_mid')}</span></div>
        <ol class="mm-how"><li>{t(lang, 'how_1')}</li><li>{t(lang, 'how_2')}</li><li>{t(lang, 'how_3')}</li></ol>
        <div class="mm-weights">{bars}</div>""")


def render_footer(lang: str) -> None:
    """Подвал как у обычных сайтов: о проекте слева, колонки ссылок, внизу — строка с копирайтом."""
    s = st.session_state
    link = lambda href, text: (f'<a class="mm-fl" href="{href}" target="_blank" rel="noopener">{text}</a>')
    with st.container(key="footer"):
        about, product, project, org = st.columns([2.2, 1, 1, 1], gap="large")
        about.html(f"""<div class="mm-fbrand"><span class="mm-flogo" aria-hidden="true"></span>Wingman</div>
            <p class="mm-ftext">{t(lang, 'foot_tagline')}</p>""")
        with product:
            st.html(f"<p class='mm-fhead'>{t(lang, 'foot_product')}</p>")
            with st.popover(t(lang, "how_title"), type="tertiary"):
                how_it_works(lang)
            st.html(link("https://dalya28.github.io/meetmatch/demo/", t(lang, "foot_demo")))
        project.html(f"<p class='mm-fhead'>{t(lang, 'foot_project')}</p>"
                     + link("https://github.com/dalya28/meetmatch", "GitHub")
                     + link("https://hackathon.metu.kz/", "AI in Engineering Hackathon"))
        with org:
            st.html(f"<p class='mm-fhead'>{t(lang, 'foot_org')}</p>")
            if s.organizer:
                st.caption(t(lang, "org_hello", name=s.organizer))
            else:
                with st.popover(t(lang, "org_login"), type="tertiary", icon=":material/lock:"):
                    org_login_form(lang)
        n = sum(not x.get("live") for x in matcher.profiles)
        st.html(f"""<div class="mm-fbottom"><span>© 2026 Wingman · AI in Engineering Hackathon, METU</span>
            <span>{t(lang, 'data_note', n=n)} {t(lang, 'event_note')}</span></div>""")


def org_login_form(lang: str) -> None:
    s = st.session_state
    if s.org_attempts >= MAX_ORG_ATTEMPTS:
        st.warning(t(lang, "org_locked"))
        return
    with st.form("org_login_form", clear_on_submit=True, border=False):
        code = st.text_input(t(lang, "org_code"), type="password", key="org_code")
        sent = st.form_submit_button(t(lang, "org_enter"))
    if sent:
        if org_sign_in(code):
            s.main_page = "dash"
            st.rerun()
        st.error(t(lang, "org_locked" if s.org_attempts >= MAX_ORG_ATTEMPTS else "org_bad"))


# ---------------------------------------------------------------- каркас
def on_lang_change() -> None:
    """Переключатель языка нельзя «отжать»: пустой выбор возвращаем к прежнему языку."""
    if st.session_state.lang_pick is None:
        st.session_state.lang_pick = st.session_state.lang
    if st.session_state.get("activity_tabs"):
        in_bingo = st.session_state.activity_tabs == t(st.session_state.lang, "bingo")
        st.session_state.activity_tabs = t(st.session_state.lang_pick, "bingo" if in_bingo else "match_nav")
    st.session_state.lang = st.session_state.lang_pick
    clear_widgets()


if st.query_params.get("start") == "1":  # кнопка «Заполнить анкету» в обложке
    if st.query_params.get("event") in {e["id"] for e in get_events()}:
        st.session_state.event = st.query_params["event"]
    if st.query_params.get("lang") in ("kk", "ru", "en"):
        st.session_state.lang = st.session_state.lang_pick = st.query_params["lang"]
    st.query_params.clear()
    start_survey(fresh=True)

if "org" in st.query_params:  # личная ссылка организатора: ...streamlit.app/?org=<код>
    org_code = st.query_params["org"]
    del st.query_params["org"]  # код не остаётся в адресной строке
    if org_sign_in(org_code):
        st.session_state.main_page = "dash"
    else:
        st.session_state.org_failed = True

lang = st.session_state.lang
persist_attendance()
st.session_state.setdefault("lang_pick", lang)
with st.container(key="topbar"):
    brand, nav, language = st.columns([3, 5, 2], vertical_alignment="center")
    # Знак — два сцепленных звена: два человека, которые зацепились друг за друга.
    brand.button("Wingman", key="brand_home", type="tertiary", on_click=brand_home, help=t(lang, "home"))
    page = "match"
    if st.session_state.organizer:  # вкладку видят только те, кому выдан код
        with nav:
            page = st.radio(t(lang, "navigation"), ["match", "dash"], key="main_page",
                            horizontal=True, label_visibility="collapsed",
                            format_func=lambda v: t(lang, "match_nav" if v == "match" else "org_nav"))
    elif st.session_state.survey_step is not None:
        nav.button(t(lang, "home"), on_click=events_home, key="survey_home", icon=":material/arrow_back:")
    with language:
        st.segmented_control("Тіл · Язык · Language", ["kk", "ru", "en"], format_func=str.upper,
                             key="lang_pick", on_change=on_lang_change, label_visibility="collapsed")

if page == "match":
    page_match(lang)
else:
    st.header(t(lang, "nav_dash"))
    page_dashboard(lang)

if st.session_state.pop("org_failed", False):
    st.error(t(lang, "org_bad"))
render_footer(lang)

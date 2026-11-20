"""MeetMatch — веб-интерфейс на Streamlit.

Запуск:  python -m streamlit run app.py
"""
from __future__ import annotations

import base64
import html
import json
import hmac
import os
import threading
import time

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from config import HALL_ENABLED, setup_logging
from claude_rank import rerank
from matcher import Matcher, load_booths, load_profiles, plan_meetings, prepare, recommend_booths
from storage import FeedbackStore, HallStore
from taxonomy import (EVENT_SLOTS, GOALS, HIREABLE_ROLES, INTERESTS, LOW_INFO_INTERESTS, ROLES,
                      STACK, goal_label, interest_label, role_label, stack_label, years_ru)
from texts import GOAL_VERB, RECIPROCITY, UI, t
from theme import HEATMAP_SCALE, PAIR_COLOR, PAIR_OF, PRIMARY

st.set_page_config(page_title="MeetMatch", page_icon="✳️", layout="wide")
ASSETS = Path(__file__).parent / "assets"
st.html(ASSETS / "meetmatch.css")


@st.cache_data
def cover_image() -> str:
    return base64.b64encode((ASSETS / "almaty.webp").read_bytes()).decode("ascii")


def event_cover(lang: str) -> None:
    st.html(f"""
        <section class="mm-cover">
          <div class="mm-intro">
            <div class="mm-event"><span class="mm-dot"></span> AI in Engineering · METU</div>
            <h1>{t(lang, 'hero_title')}<br><em>{t(lang, 'hero_accent')}</em></h1>
            <p>{t(lang, 'hero_copy')}</p>
            <a class="mm-cta" href="#mm-profile">{t(lang, 'hero_cta')} <span aria-hidden="true">↘</span></a>
          </div>
          <div class="mm-art">
            <img alt="" src="data:image/webp;base64,{cover_image()}">
            <span class="mm-place">{t(lang, 'city')} &nbsp;·&nbsp; {t(lang, 'dates')}</span>
          </div>
        </section>
    """)


# ---------------------------------------------------------------- данные (общие для всех сессий)
log = setup_logging()


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
def hall_lock():
    return threading.Lock()


def join_hall(q: dict, lang: str) -> dict:
    """Живой зал: анкета участника становится видна следующим участникам.
    Возвращает подготовленную анкету с id, чтобы человек не видел в рекомендациях сам себя."""
    with hall_lock():
        current = get_matcher()
        if q.get("id") in current.by_id:
            return q
        profile = hall_store().join(q, lang, guest_name=t(lang, "guest"))
        current.add_profiles([profile])
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
          "goal": "find_job", "seeking_roles": [], "slots": []}
DEFAULTS = {"form": dict(FIELDS), "excluded": [], "rejected_roles": [], "met": [], "query": None,
            "lang": "ru"}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


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
    st.session_state.excluded, st.session_state.rejected_roles, st.session_state.met = [], [], []


def build_query() -> None:
    previous_id = (st.session_state.query or {}).get("id")
    query = prepare(dict(st.session_state.form))
    if previous_id in get_matcher().by_id:
        query["id"] = previous_id
    st.session_state.query = query
    st.session_state.pop("person_pick", None)
    st.session_state.focus_results = True
    reset_feedback()


def fill_example(goal: str) -> None:
    ex = EXAMPLES[goal]
    form = dict(FIELDS)
    form.update({k: (list(v) if isinstance(v, list) else v) for k, v in ex.items() if k != "about"})
    form["about"] = ex["about"][st.session_state.lang]
    st.session_state.form = form
    clear_widgets()
    build_query()


def pick_example() -> None:
    goal = st.session_state.ex_pick
    if goal:
        fill_example(goal)
    st.session_state.ex_pick = None


def _goal() -> str:
    q = st.session_state.query
    return q["goal"] if q else ""


def on_met(pid: str, name: str) -> None:
    st.session_state.met.append((pid, name))
    feedback_store().add("met", pid, _goal())
    st.session_state.toast = "toast_met"


def on_reject(pid: str, role: str) -> None:
    st.session_state.excluded.append(pid)
    st.session_state.rejected_roles.append(role)
    feedback_store().add("not_fit", pid, _goal())
    st.session_state.toast = "toast_not_fit"


# ---------------------------------------------------------------- вспомогательное
def chips(items: list[str]) -> str:
    return "".join(f'<span class="mm-chip">{html.escape(x)}</span>' for x in items)


def exp_short(n: int, lang: str) -> str:
    if n <= 0:
        return t(lang, "no_exp")
    return years_ru(n) if lang == "ru" else f"{n} жыл" if lang == "kk" else f"{n} yrs"


def render_card(m, lang: str, position: int, count: int) -> None:
    p = m.profile
    meta = " · ".join(x for x in (role_label(p["role"], lang), exp_short(p["experience"], lang),
                                   p.get("company")) if x)
    initials = "".join(part[0] for part in p["name"].split()[:2])
    with st.container(border=True, key=f"card_{p['id']}"):
        st.html(f"""
            <div class="mm-person">
                <span class="mm-avatar">{html.escape(initials)}</span>
                <div class="mm-person-body"><span class="mm-goal">{GOAL_VERB[lang][p['goal']]} · {round(m.score * 100)}% {t(lang, 'match')}</span>
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
        st.code(m.icebreaker, language=None, wrap_lines=True)
        st.caption(t(lang, "slot", slots=", ".join(m.common_slots)) if m.common_slots
                   else t(lang, "no_slot"))
        b1, b2 = st.columns(2)
        b1.button("✓ " + t(lang, "met"), key=f"met_{p['id']}", on_click=on_met,
                  args=(p["id"], p["name"]), width="stretch")
        b2.button("✕ " + t(lang, "not_fit"), key=f"no_{p['id']}", on_click=on_reject,
                  args=(p["id"], p["role"]), width="stretch")


# ---------------------------------------------------------------- страница подбора
def profile_form(lang: str) -> None:
    st.pills(t(lang, "examples"), list(EXAMPLES), format_func=lambda g: t(lang, f"ex_{g}"),
             key="ex_pick", on_change=pick_example)
    choose = t(lang, "choose")
    for field, value in st.session_state.form.items():
        st.session_state.setdefault(wkey(field, lang), list(value) if isinstance(value, list) else value)

    def key(field):
        return wkey(field, lang)

    with st.form(f"profile_{lang}", border=False):
        goals, profile = st.columns([5, 7], gap="large")
        with goals:
            st.markdown(f"#### {t(lang, 'goal_q')}")
            st.radio(t(lang, "goal_q"), list(GOALS), format_func=lambda g: goal_label(g, lang),
                     key=key("goal"), horizontal=True, width="stretch", label_visibility="collapsed")
        with profile:
            st.markdown(f"#### {t(lang, 'profile_details')}")
            c1, c2 = st.columns([3, 2])
            c1.selectbox(t(lang, "role"), list(ROLES), format_func=lambda r: role_label(r, lang), key=key("role"))
            c2.number_input(t(lang, "experience"), min_value=0, max_value=40, step=1, key=key("experience"))
            c1, c2 = st.columns(2)
            c1.multiselect(t(lang, "stack"), list(STACK), format_func=stack_label, key=key("stack"),
                           help=t(lang, "stack_help"), placeholder=choose)
            c2.multiselect(t(lang, "interests"), list(INTERESTS), placeholder=choose,
                           format_func=lambda i: interest_label(i, lang), key=key("interests"))
            st.text_area(t(lang, "about"), key=key("about"), placeholder=t(lang, "about_ph"), height=82)
            with st.expander(t(lang, "more")):
                st.text_input(t(lang, "name"), key=key("name"))
                st.multiselect(t(lang, "seeking"), HIREABLE_ROLES + ["founder"], placeholder=choose,
                               format_func=lambda r: role_label(r, lang), key=key("seeking_roles"))
                st.multiselect(t(lang, "slots"), EVENT_SLOTS, key=key("slots"), placeholder=choose)
            if st.form_submit_button(t(lang, "submit"), type="primary", width="stretch"):
                st.session_state.form = {field: st.session_state[key(field)] for field in FIELDS}
                build_query()
                st.rerun()


def page_match(lang: str) -> None:
    q = st.session_state.query
    if q is None:
        event_cover(lang)
        with st.container(border=True, key="onboarding"):
            st.subheader(t(lang, "form_title"), anchor="mm-profile")
            profile_form(lang)
        with st.expander(t(lang, "how_title")):
            st.markdown(t(lang, "how_text"))
        return
    with st.expander(t(lang, "edit_profile"), icon=":material/tune:", key="edit_profile"):
        profile_form(lang)
    render_results(q, lang)


def render_results(q: dict, lang: str) -> None:
    s = st.session_state
    if s.get("toast"):
        st.toast(t(lang, s.pop("toast")))

    met_ids = [pid for pid, _ in s.met]
    t0 = time.perf_counter()
    st.header(t(lang, "results_title"), anchor="mm-results")

    if s.pop("focus_results", False):
        # Уникальный маркер запускает переход и при повторной отправке той же формы.
        st.html(f"""<script>/* {time.monotonic_ns()} */
        requestAnimationFrame(() => {{
            const heading = document.getElementById("mm-results");
            if (heading && window.matchMedia("(max-width: 640px)").matches) {{
                heading.tabIndex = -1;
                heading.focus({{preventScroll:true}});
                heading.scrollIntoView({{block:"start", behavior:"instant"}});
            }}
        }});
        </script>""", unsafe_allow_javascript=True)
    try:
        with st.spinner(t(lang, "loading")):
            # Streamlit exposes root-level secrets as environment variables after loading.
            st.secrets.load_if_toml_exists()
            api_key = os.getenv("ANTHROPIC_API_KEY") if os.getenv("MEETMATCH_AI") == "1" else None
            pool = matcher.recommend(q, k=15 if api_key else 5, lang=lang, exclude=set(s.excluded) | set(met_ids),
                                     rejected_roles=s.rejected_roles)
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
    elapsed = time.perf_counter() - t0

    st.caption(RECIPROCITY[lang][q["goal"]])
    if recs:
        people, detail = st.columns([4, 8], gap="medium")
        matches = {m.profile["id"]: m for m in recs}
        ids = list(matches)
        if s.get("person_pick") not in matches:
            s.person_pick = ids[0]
        with people:
            selected = st.radio(t(lang, "pick_person"), ids, key="person_pick", width="stretch",
                                format_func=lambda pid: f'{ids.index(pid) + 1:02d}　{matches[pid].profile["name"]}')
        with detail:
            render_card(matches[selected], lang, ids.index(selected) + 1, len(ids))
    else:
        st.warning(t(lang, "no_more"))

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
    if s.met or s.excluded:
        st.button(t(lang, "reset"), on_click=reset_feedback)

    if HALL_ENABLED:
        if q.get("id") in matcher.by_id:
            st.success(t(lang, "hall_joined"))
        else:
            st.caption(t(lang, "hall_consent"))
            if st.button(t(lang, "hall_join"), key="hall_join"):
                try:
                    s.query = join_hall(q, lang)
                    st.rerun()
                except (RuntimeError, OSError):
                    log.warning("hall_join_failed", exc_info=True)
                    st.error(t(lang, "hall_error"))

    with st.expander(t(lang, "schedule_title")):
        if not q.get("slots"):
            st.caption(t(lang, "schedule_none"))
        else:
            plan, left = plan_meetings(recs)
            if plan:
                st.dataframe(pd.DataFrame([{t(lang, "col_time"): slot,
                                            t(lang, "col_with"): f"{m.profile['name']} — {role_label(m.profile['role'], lang)}"}
                                           for slot, m in plan]), hide_index=True, width="stretch")
            if left:
                st.caption(t(lang, "schedule_left", names=", ".join(m.profile["name"] for m in left)))

    with st.expander(t(lang, "booths_title")):
        for col, booth in zip(st.columns(2), recommend_booths(q, get_booths())):
            with col.container(border=True):
                st.markdown(f"**{booth['name']}**")
                st.caption(booth["desc"][lang])
                st.markdown(chips([interest_label(i, lang) for i in booth["interests"][:3]]), unsafe_allow_html=True)
                if booth["hiring"]:
                    st.caption(t(lang, "booth_hiring", roles=", ".join(role_label(r, lang) for r in booth["hiring"])))

    with st.expander(t(lang, "how_title")):
        st.caption(t(lang, "found_in", ms=max(1, round(elapsed * 1000)), n=len(matcher.profiles)))
        if not q["stack"] and not q["about"].strip():
            st.caption(t(lang, "need_more"))
        inferred = [stack_label(x) for x in q["inferred"]["stack"]] + [
            interest_label(i, lang) for i in q["inferred"]["interests"]] + [
            role_label(r, lang) for r in q["inferred"]["seeking"]] + q["inferred"].get("levels", [])
        if inferred:
            st.caption(t(lang, "inferred", tags=", ".join(inferred)))
        st.markdown(t(lang, "how_text"))


# ---------------------------------------------------------------- дашборд организатора
def _ratio(x: float, lang: str) -> str:
    text = f"{x:.1f}"
    return text.replace(".", ",") if lang in ("ru", "kk") else text


def page_dashboard(lang: str) -> None:
    df = pd.DataFrame(matcher.profiles)
    events = feedback_store().all()
    stats = feedback_store().stats()

    c1, c2, c3 = st.columns(3)
    c1.metric(t(lang, "dash_people"), len(df))
    c2.metric(t(lang, "dash_feedback"), stats["total"])
    c3.metric(t(lang, "dash_met_rate"),
              f"{round(100 * stats['met_share'])}%" if stats["met_share"] is not None else "—")

    if HALL_ENABLED:
        live_count = sum(p.get("live") is True for p in matcher.profiles)
        st.metric(t(lang, "hall_count"), live_count)
        if st.session_state.pop("hall_cleared", False):
            st.success(t(lang, "hall_cleared"))
        organizer_code = os.environ.get("MEETMATCH_ORGANIZER_CODE")
        if live_count and organizer_code:
            with st.expander(t(lang, "hall_clear")):
                with st.form("clear_hall", clear_on_submit=True):
                    code = st.text_input(t(lang, "hall_code"), type="password")
                    st.caption(t(lang, "hall_clear_note"))
                    confirm = st.form_submit_button(t(lang, "hall_clear"))
                if confirm:
                    if not hmac.compare_digest(code.encode(), organizer_code.encode()):
                        st.error(t(lang, "hall_bad_code"))
                    else:
                        try:
                            with hall_lock():
                                hall_store().clear()
                                get_matcher.clear()
                            st.session_state.hall_cleared = True
                            st.rerun()
                        except OSError:
                            log.warning("hall_clear_failed", exc_info=True)
                            st.error(t(lang, "hall_clear_error"))

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
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), legend_title_text="",
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
        st.dataframe(pd.DataFrame([{"time": e["time"][11:16], "": t(lang, e["action"]),
                                    "name": names.get(e["candidate_id"], {}).get("name", "")}
                                   for e in reversed(events[-20:])]), hide_index=True, width="stretch")
    else:
        st.caption(t(lang, "dash_feedback_none"))


# ---------------------------------------------------------------- каркас
def on_lang_change() -> None:
    """Переключатель языка нельзя «отжать»: пустой выбор возвращаем к прежнему языку."""
    if st.session_state.lang_pick is None:
        st.session_state.lang_pick = st.session_state.lang
    st.session_state.lang = st.session_state.lang_pick
    clear_widgets()


lang = st.session_state.lang
st.session_state.setdefault("lang_pick", lang)
with st.container(key="topbar"):
    brand, nav, language = st.columns([3, 5, 2], vertical_alignment="center")
    brand.html('<div class="mm-brand"><span class="mm-mark" aria-hidden="true"></span>MeetMatch</div>')
    with nav:
        page = st.radio(t(lang, "navigation"), ["match", "dash"], key="main_page",
                        horizontal=True, label_visibility="collapsed",
                        format_func=lambda v: t(lang, "match_nav" if v == "match" else "org_nav"))
    with language:
        st.segmented_control("Тіл · Язык · Language", ["kk", "ru", "en"], format_func=str.upper,
                             key="lang_pick", on_change=on_lang_change, label_visibility="collapsed")

if page == "match":
    page_match(lang)
else:
    st.header(t(lang, "nav_dash"))
    page_dashboard(lang)

st.caption(t(lang, "data_note", n=sum(not p.get("live") for p in matcher.profiles)))

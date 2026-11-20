"""Подбор знакомств Wingman.

1. Фильтр взаимности целей (taxonomy.GOAL_MATCH): показываем только тех,
   чья цель отвечает цели участника.
2. Оценка кандидата: роль, стек, опыт, интересы, похожесть текста «о себе».
3. Разнообразие: топ-5 не должен состоять из одной компании.
4. Объяснение и первая фраза по шаблонам — мгновенно и без внешних API.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from scipy.sparse import vstack
from sklearn.feature_extraction.text import TfidfVectorizer

from config import (BOOTHS_PATH, MAX_ABOUT_LEN, MAX_EXPERIENCE, MAX_LIST_ITEMS, MAX_NAME_LEN,
                    PROFILES_PATH, REJECT_PENALTY, RERANK_POOL, SAME_COMPANY_PENALTY,
                    SAME_ROLE_PENALTY, TOP_K, WEIGHTS)
from taxonomy import (EVENT_SLOTS, GOAL_MATCH, GOALS, HIREABLE_ROLES, INTERESTS, LEVELS,
                      LOW_INFO_INTERESTS, NON_SPECIALIST_ROLES, ROLES, SPECIALIST_ROLES, STACK,
                      effective_roles, exp_phrase, extract_tags, interest_label, levels_in_text,
                      role_label, role_similarity, roles_from_stack, stack_label, years_ru)
from texts import ICEBREAKER, REASON, SHARED

log = logging.getLogger("meetmatch")
__all__ = ["WEIGHTS", "Matcher", "Match", "prepare", "sanitize_query", "score_parts",
           "load_profiles", "load_booths", "plan_meetings", "recommend_booths"]


@dataclass
class Match:
    profile: dict
    score: float
    parts: dict
    explanation: str
    icebreaker: str
    shared_stack: list = field(default_factory=list)
    shared_interests: list = field(default_factory=list)
    common_slots: list = field(default_factory=list)


def _load_json(path: Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(f"Нет файла {path}. Создайте базу: python scripts/generate_profiles.py") from None
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Файл {path} повреждён ({e}). Пересоздайте базу: "
                           "python scripts/generate_profiles.py") from None
    if not isinstance(data, list):
        raise RuntimeError(f"В {path} ожидается список, а не {type(data).__name__}")
    return data


def load_profiles(path: Path = PROFILES_PATH) -> list[dict]:
    return _load_json(path)


def load_booths(path: Path = BOOTHS_PATH) -> list[dict]:
    return _load_json(path)


# ---------------------------------------------------------------- анкета участника
DEFAULT_QUERY = {"name": "", "role": "backend", "experience": 1, "stack": [], "interests": [],
                 "about": "", "goal": "exchange", "seeking_roles": [], "slots": []}


def _codes(value, allowed) -> list[str]:
    """Только известные коды, без повторов, не больше MAX_LIST_ITEMS."""
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for v in value:
        if isinstance(v, str) and v in allowed and v not in out:
            out.append(v)
    return out[:MAX_LIST_ITEMS]


def sanitize_query(raw: dict) -> dict:
    """Проверка входной анкеты: неизвестные коды отбрасываются, строки обрезаются, опыт
    ограничен 0–40, неизвестная роль или цель заменяются значением по умолчанию.
    Анкету заполняет любой человек в зале, поэтому ей нельзя доверять как есть."""
    raw = raw if isinstance(raw, dict) else {}

    def _int(v) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return DEFAULT_QUERY["experience"]

    q = {
        "name": str(raw.get("name") or "").strip()[:MAX_NAME_LEN],
        "role": raw.get("role") if raw.get("role") in ROLES else DEFAULT_QUERY["role"],
        "experience": min(max(_int(raw.get("experience")), 0), MAX_EXPERIENCE),
        "stack": _codes(raw.get("stack"), STACK),
        "interests": _codes(raw.get("interests"), INTERESTS),
        "about": str(raw.get("about") or "").strip()[:MAX_ABOUT_LEN],
        "goal": raw.get("goal") if raw.get("goal") in GOALS else DEFAULT_QUERY["goal"],
        "seeking_roles": _codes(raw.get("seeking_roles"), ROLES),
        "slots": [s for s in EVENT_SLOTS if s in _codes(raw.get("slots"), EVENT_SLOTS)],
    }
    if raw.get("id"):
        q["id"] = str(raw["id"])
    return q


def prepare(raw: dict) -> dict:
    """Дополняет анкету тем, что найдено в тексте «о себе», и выводит, кого человек ищет."""
    q = sanitize_query(raw)
    found = extract_tags(q["about"])
    added_stack = [s for s in STACK if s in found["stack"] and s not in q["stack"]]
    added_interests = [i for i in found["interests"] if i not in q["interests"]]
    q["stack"] = list(q["stack"]) + added_stack
    q["interests"] = list(q["interests"]) + sorted(added_interests)

    seeking = [r for r in q.get("seeking_roles") or [] if r in ROLES]
    inferred_seeking: list[str] = []
    if not seeking and q["goal"] == "hire":
        inferred_seeking = [r for r in HIREABLE_ROLES if r in found["roles"]]
        if not inferred_seeking:
            inferred_seeking = ([q["role"]] if q["role"] in SPECIALIST_ROLES
                                else [r for r in roles_from_stack(q["stack"]) if r in SPECIALIST_ROLES][:2])
        seeking = inferred_seeking
    elif not seeking and q["goal"] == "find_cofounder":
        # «ищу CTO / продакта» — роли из текста, кроме своей собственной
        inferred_seeking = [r for r in HIREABLE_ROLES + ["founder"] if r in found["roles"] and r != q["role"]]
        seeking = inferred_seeking
    q["seeking_roles"] = seeking
    # Кем человек хочет быть: «хочу стать аналитиком данных» (разбор ошибок шага 4).
    q["target_roles"] = ([r for r in HIREABLE_ROLES if r in found["roles"]]
                         if q["goal"] in ("find_job", "find_mentor", "exchange") else [])

    # Уровень вакансии из текста: «ищем middle» -> опыт 2–5 лет
    levels = levels_in_text(q["about"]) if q["goal"] == "hire" else []
    q["hire_exp_min"] = LEVELS[levels[0]][0] if levels else None
    q["hire_exp_max"] = LEVELS[levels[-1]][1] if levels else None
    q["inferred"] = {"stack": added_stack, "interests": sorted(added_interests),
                     "seeking": inferred_seeking, "levels": levels}
    return q


def _level_fit(exp: int, lo, hi) -> float:
    if lo is None:
        return 0.7
    if lo <= exp <= hi:
        return 1.0
    return max(0.0, 1 - 0.25 * min(abs(exp - lo), abs(exp - hi)))


def _doc(p: dict) -> str:
    """Текст для TF-IDF: «о себе» + коды тегов (они одинаковы на всех языках)."""
    tags = " ".join(list(p.get("stack", [])) + list(p.get("interests", [])) + [p.get("role", "")])
    return f"{p.get('about', '')} {tags}"


# ---------------------------------------------------------------- части оценки
def _set_cosine(a, b) -> float:
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def _stack_score(a, b) -> float:
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    tags = len(a & b) / min(len(a), len(b))
    fa = set().union(*(STACK[s][1] for s in a if s in STACK))
    fb = set().union(*(STACK[s][1] for s in b if s in STACK))
    fams = len(fa & fb) / min(len(fa), len(fb)) if fa and fb else 0.0
    return 0.75 * tags + 0.25 * fams


def _role_fit(have: set, want) -> tuple[float, str]:
    """Насколько роли `have` подходят под искомые `want`."""
    want = set(want)
    if not have or not want:
        return 0.3, "none"
    if have & want:
        return 1.0, "exact"
    if any(role_similarity(h, w) >= 0.6 for h in have for w in want):
        return 0.5, "related"
    return 0.0, "none"


def _role_similarity_sets(a: set, b: set) -> float:
    if not a or not b:
        return 0.3
    return max(role_similarity(x, y) for x in a for y in b)


def _side(role: str) -> str:
    """Сторона стартапа: технарь или «не технарь» (продукт и бизнес)."""
    return "tech" if ROLES[role]["group"] == "tech" else "nontech"


def _seek_score(wanted, role: str) -> float:
    """Насколько роль подходит под «кого ищу»: точно — 1, та же сторона — 0.5, не указано — 0.5."""
    if not wanted:
        return 0.5
    if role in wanted:
        return 1.0
    return 0.5 if any(_side(r) == _side(role) for r in wanted) else 0.0


def _cofounder_fit(q: dict, c: dict) -> tuple[float, bool]:
    """Дополнение ролей (технарь + не технарь) и взаимный поиск с обеих сторон.
    Раньше учитывалось только дополнение, и у всех подходящих оценка упиралась в 1.0 —
    разбор ошибок шага 4 показал, что ранжирование внутри них было случайным."""
    complement = 1.0 if _side(q["role"]) != _side(c["role"]) else (0.5 if q["role"] != c["role"] else 0.25)
    i_seek = _seek_score(q["seeking_roles"], c["role"])
    they_seek = _seek_score(c.get("seeking_roles", []), q["role"])
    return 0.5 * complement + 0.25 * i_seek + 0.25 * they_seek, complement == 1.0


def _related_only_with_stack(role: float, stack: float) -> float:
    """Смежная роль засчитывается в менторстве и обмене опытом, только если есть общий стек:
    DevOps-ментору не нужен Data-инженер без единой общей технологии (разбор ошибок шага 4)."""
    return role if role >= 1.0 or stack > 0 else role * 0.5


def _mentor_gap(diff: int) -> float:
    return 1.0 if diff >= 3 else 0.7 if diff == 2 else 0.4


def score_parts(q: dict, c: dict, text_sim: float) -> tuple[dict, dict] | None:
    """Части оценки кандидата `c` для участника `q`. None — кандидат не подходит совсем."""
    goal = q["goal"]
    meta: dict = {}
    q_roles = effective_roles(q["role"], q["stack"])
    target = set(q.get("target_roles") or [])
    if target:  # у студента и фаундера цель из текста точнее, чем догадка по стеку
        q_roles = target if q["role"] in NON_SPECIALIST_ROLES else q_roles | target
    c_roles = effective_roles(c["role"], c["stack"])
    stack = _stack_score(q["stack"], c["stack"])

    if goal == "find_job":
        role, meta["fit"] = _role_fit(q_roles, c.get("seeking_roles", []))
        exp = _level_fit(q["experience"], c.get("hire_exp_min"), c.get("hire_exp_max"))
    elif goal == "hire":
        role, meta["fit"] = _role_fit(c_roles, q["seeking_roles"])
        exp = _level_fit(c["experience"], q.get("hire_exp_min"), q.get("hire_exp_max"))
    elif goal in ("find_mentor", "be_mentor"):
        diff = (c["experience"] - q["experience"]) if goal == "find_mentor" else (q["experience"] - c["experience"])
        if diff < 1:
            return None  # ментор должен быть опытнее подопечного
        meta["diff"] = diff
        role = _related_only_with_stack(_role_similarity_sets(q_roles, c_roles), stack)
        exp = _mentor_gap(diff)
    elif goal == "find_cofounder":
        role, meta["complement"] = _cofounder_fit(q, c)
        # Кофаундеру важнее дополнить вас, чем совпасть по стеку.
        stack = 0.5 + 0.5 * stack if meta["complement"] else 0.5 * stack
        # опыт партнёра: для CTO важен сильнее
        exp = (min(1.0, c["experience"] / 10) if "lead" in q["seeking_roles"]
               else 0.5 + 0.5 * min(c["experience"], 10) / 10)
    else:  # exchange
        role = _related_only_with_stack(_role_similarity_sets(q_roles, c_roles), stack)
        exp = 1 - min(abs(q["experience"] - c["experience"]), 8) / 8 * 0.6

    meta["role"] = role
    parts = {"role": role, "stack": stack, "experience": exp,
             "interests": _set_cosine(q["interests"], c["interests"]),
             "text": min(1.0, text_sim * 2)}
    return parts, meta


# ---------------------------------------------------------------- тексты
def _lower_first(label: str) -> str:
    """«Продакт-менеджер» -> «продакт-менеджер», но «QA-инженер» и «ML-инженер» не трогаем."""
    if len(label) > 1 and label[1].islower():
        return label[0].lower() + label[1:]
    return label


def _diff_text(diff: int, lang: str) -> str:
    if lang == "ru":
        return years_ru(diff)
    if lang == "kk":
        return str(diff)
    return f"{diff} year{'s' if diff != 1 else ''}"


def _informative(interests) -> list[str]:
    return sorted(interests, key=lambda i: i in LOW_INFO_INTERESTS)


def explain(q: dict, c: dict, meta: dict, lang: str) -> tuple[str, list, list]:
    goal = q["goal"]
    tpl = REASON[lang]
    first = c["name"].split()[0]
    fields = {
        "name": first,
        "role": role_label(c["role"], lang),
        "role_a": ROLES[c["role"]]["en_a"],
        "my_role": _lower_first(role_label(q["role"], lang)),
        "my_role_a": ROLES[q["role"]]["en_a"],
        "exp": exp_phrase(c["experience"], lang),
        "company": c.get("company") or first,
        "roles": ", ".join(role_label(r, lang) for r in c.get("seeking_roles", [])),
        "levels": ", ".join(c.get("hire_levels", [])),
    }
    if goal == "find_job":
        s1 = tpl["find_job"].format(fit=tpl["find_job_fit"][meta.get("fit", "none")], **fields)
    elif goal == "hire":
        s1 = tpl["hire"].format(fit=tpl["hire_fit"][meta.get("fit", "none")], **fields)
    elif goal == "find_mentor":
        s1 = tpl["find_mentor"].format(diff=_diff_text(meta["diff"], lang), **fields)
    elif goal == "be_mentor":
        field_txt = tpl["be_mentor_field"] if meta.get("role", 0) >= 0.6 else ""
        s1 = tpl["be_mentor"].format(field=field_txt, **fields)
    elif goal == "find_cofounder":
        if meta.get("complement"):
            fields["role"] = _lower_first(fields["role"]) if lang != "en" else fields["role"]
            s1 = tpl["find_cofounder"].format(**fields)
        else:
            s1 = tpl["find_cofounder_same"].format(**fields)
    else:
        s1 = tpl["exchange"].format(**fields)

    shared_stack = [s for s in c["stack"] if s in set(q["stack"])]
    shared_interests = _informative([i for i in c["interests"] if i in set(q["interests"])])
    stack_txt = ", ".join(stack_label(s) for s in shared_stack[:3])
    int_txt = ", ".join(interest_label(i, lang) for i in shared_interests[:2])
    sh = SHARED[lang]
    if shared_stack and shared_interests:
        s2 = sh["both"].format(stack=stack_txt, interests=int_txt)
    elif shared_stack:
        s2 = sh["stack"].format(stack=stack_txt)
    elif shared_interests:
        s2 = sh["interests"].format(interests=int_txt)
    elif c["interests"]:
        s2 = sh["theirs"].format(interest=interest_label(_informative(c["interests"])[0], lang))
    else:
        s2 = ""
    return f"{s1} {s2}".strip(), shared_stack, shared_interests


def icebreaker(q: dict, c: dict, shared_stack: list, shared_interests: list, lang: str) -> str:
    goal = q["goal"]
    key = goal
    # Тема разговора: общий стек или содержательный общий интерес
    # (не «Менторство» и не «Карьера» — они есть почти у всех).
    good_shared = [i for i in shared_interests if i not in LOW_INFO_INTERESTS]
    interest_topic = interest_label(good_shared[0], lang) if good_shared else ""
    if goal == "find_job":
        topic = ", ".join(stack_label(s) for s in (shared_stack or q["stack"])[:2])
        if not topic:
            key = "find_job_nostack"
    elif goal == "hire":
        topic = ", ".join(stack_label(s) for s in (shared_stack or c["stack"])[:2]) or role_label(c["role"], lang)
    elif goal in ("find_mentor", "be_mentor"):
        mentee = q if goal == "find_mentor" else c
        topic = (stack_label(shared_stack[0]) if shared_stack else interest_topic) or \
            (stack_label(mentee["stack"][0]) if mentee["stack"] else role_label(mentee["role"], lang))
    else:
        topic = interest_topic or (stack_label(shared_stack[0]) if shared_stack else "")
        own = [i for i in c["interests"] if i not in LOW_INFO_INTERESTS]
        if not topic and own:
            topic = interest_label(own[0], lang)
        topic = topic or role_label(c["role"], lang)
    return ICEBREAKER[lang][key].format(
        first=c["name"].split()[0], topic=topic,
        my_role=_lower_first(role_label(q["role"], lang)), my_role_a=ROLES[q["role"]]["en_a"])


# ---------------------------------------------------------------- подбор
class Matcher:
    """Индекс участников. Один экземпляр обслуживает всех пользователей Streamlit одновременно.

    Потокобезопасность (copy-on-write): `add_profiles` не меняет списки на месте, а под замком
    собирает новый «снимок» (анкеты, матрица TF-IDF, словарь id) и подменяет его одной операцией.
    `recommend` берёт снимок один раз в начале, поэтому никогда не увидит анкету без строки
    в матрице, даже если в этот момент кто-то добавляется в живой зал.
    """

    def __init__(self, profiles: list[dict]):
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        matrix = self.vectorizer.fit_transform([_doc(p) for p in profiles])
        self._snapshot = (list(profiles), matrix, {p["id"]: p for p in profiles})
        self._lock = threading.Lock()

    @property
    def profiles(self) -> list[dict]:
        return self._snapshot[0]

    @property
    def by_id(self) -> dict[str, dict]:
        return self._snapshot[2]

    def add_profiles(self, new: list[dict]) -> None:
        """Добавляет анкеты (живой зал). Словарь TF-IDF остаётся от базы — для подбора этого достаточно."""
        if not new:
            return
        with self._lock:
            profiles, matrix, by_id = self._snapshot
            fresh = [p for p in new if p["id"] not in by_id]
            if not fresh:
                return
            rows = self.vectorizer.transform([_doc(p) for p in fresh])
            self._snapshot = (profiles + fresh, vstack([matrix, rows]).tocsr(),
                              {**by_id, **{p["id"]: p for p in fresh}})
        log.info("index_add added=%d total=%d", len(fresh), len(self._snapshot[0]))

    def recommend(self, query: dict, k: int = TOP_K, lang: str = "ru", exclude=(),
                  rejected_roles=(), weights: dict | None = None,
                  reciprocity: bool = True) -> list[Match]:
        """`weights` и `reciprocity=False` нужны только для экспериментов (scripts/evaluate.py)."""
        t0 = time.perf_counter()
        profiles, matrix, _ = self._snapshot  # один согласованный снимок на весь подбор
        q = query if "inferred" in query else prepare(query)
        allowed = GOAL_MATCH[q["goal"]] if reciprocity else set(GOAL_MATCH)
        w = weights or WEIGHTS
        exclude = set(exclude) | {q.get("id")}
        sims = (matrix @ self.vectorizer.transform([_doc(q)]).T).toarray().ravel()
        rejected = list(rejected_roles)

        scored = []
        for i, c in enumerate(profiles):
            if c["id"] in exclude or c["goal"] not in allowed:
                continue
            res = score_parts(q, c, float(sims[i]))
            if res is None:
                continue
            parts, meta = res
            score = sum(w[name] * value for name, value in parts.items())
            # «Не подошло» понижает людей той же роли, но не трогает роль, которую человек ищет:
            # отказ от одного фронтендера не должен убирать всех фронтендеров.
            if parts["role"] < 1.0:
                score -= REJECT_PENALTY * rejected.count(c["role"])
            scored.append((score, parts, meta, c))
        scored.sort(key=lambda x: -x[0])

        picked: list[tuple] = []
        pool = scored[:RERANK_POOL]
        while pool and len(picked) < k:
            def adjusted(item):
                _, _, _, c = item
                pen = SAME_COMPANY_PENALTY * sum(1 for p in picked if c.get("company") and p[3].get("company") == c["company"])
                pen += SAME_ROLE_PENALTY * max(0, sum(1 for p in picked if p[3]["role"] == c["role"]) - 1)
                return item[0] - pen
            best = max(pool, key=adjusted)
            pool.remove(best)
            picked.append(best)

        q_slots = set(q.get("slots") or [])
        out = []
        for score, parts, meta, c in picked:
            text, s_stack, s_int = explain(q, c, meta, lang)
            out.append(Match(
                profile=c, score=round(max(0.0, min(1.0, score)), 3), parts=parts, explanation=text,
                icebreaker=icebreaker(q, c, s_stack, s_int, lang),
                shared_stack=s_stack, shared_interests=s_int,
                common_slots=[s for s in EVENT_SLOTS if s in q_slots and s in c.get("slots", [])],
            ))
        # Без имён и текстов анкеты: только цель, язык, размеры и время.
        log.info("recommend goal=%s lang=%s candidates=%d returned=%d excluded=%d ms=%.1f",
                 q["goal"], lang, len(scored), len(out), len(exclude) - 1,
                 (time.perf_counter() - t0) * 1000)
        return out


# ---------------------------------------------------------------- расписание и стенды
def plan_meetings(matches: list[Match]) -> tuple[list[tuple[str, Match]], list[Match]]:
    """Ставит каждую встречу в самый ранний общий слот, не занятый другой встречей."""
    used, plan, left = set(), [], []
    for m in matches:
        slot = next((s for s in m.common_slots if s not in used), None)
        if slot:
            used.add(slot)
            plan.append((slot, m))
        else:
            left.append(m)
    plan.sort(key=lambda x: EVENT_SLOTS.index(x[0]))
    return plan, left


def recommend_booths(q: dict, booths: list[dict], k: int = 2) -> list[dict]:
    roles = effective_roles(q["role"], q["stack"])

    def score(b: dict) -> float:
        s = 0.5 * _set_cosine(q["interests"], b["interests"]) + 0.3 * _stack_score(q["stack"], b["stack"])
        if q["goal"] == "find_job" and roles & set(b["hiring"]):
            s += 0.3
        if q["goal"] == "find_cofounder" and "startups" in b["interests"]:
            s += 0.3
        if q["goal"] in ("be_mentor", "find_mentor") and "mentorship" in b["interests"]:
            s += 0.2
        return s

    return sorted(booths, key=score, reverse=True)[:k]

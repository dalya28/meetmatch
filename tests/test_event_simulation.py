"""Симуляция мероприятий: 200 сценариев — 140 пар и 60 компаний по 3–4 человека в живом зале.

Пара: оба участника заполнили анкету на одном событии (имя и Telegram обязательны), видят друг друга
в подборе (взаимность целей), оба нажали «Познакомиться» → «Это взаимно!» и Telegram обоих.
Компания: участник и 2–3 человека с той же целью на том же событии записываются на одну встречу.
13 типов пар и 6 типов компаний прогоняются по всем 11 событиям Алматы.
"""
import itertools

import pytest

from events import attendee_ids, load_events
from groups import suggest_group
from matcher import Matcher, load_profiles, prepare
from social import is_mutual, telegram_url
from storage import FeedbackStore, HallStore

PROFILES = load_profiles()
EVENTS = load_events()


def person(goal, role, exp, stack, interests, slots, **extra):
    return {"goal": goal, "role": role, "experience": exp, "stack": stack, "interests": interests,
            "slots": slots, **extra}


# пары взаимных целей: (кто ищет, кто отвечает) — разные роли, стек, опыт и темы
PAIRS = [
    (person("find_job", "backend", 2, ["python", "django"], ["fintech"], ["11:00", "14:00"]),
     person("hire", "recruiter", 5, ["python"], ["fintech"], ["11:00"], seeking_roles=["backend"])),
    (person("find_mentor", "student", 0, ["sql", "python"], ["data_science"], ["12:00"]),
     person("be_mentor", "data", 9, ["sql", "python"], ["data_science"], ["12:00"])),
    (person("find_job", "frontend", 1, ["react", "typescript"], ["ecommerce"], ["13:30"]),
     person("hire", "lead", 8, ["react", "typescript"], ["ecommerce"], ["13:30"], seeking_roles=["frontend"])),
    (person("find_job", "ml", 3, ["python", "pytorch", "llm"], ["ai"], ["15:00"]),
     person("hire", "founder", 6, ["python", "llm"], ["ai", "startups"], ["15:00"], seeking_roles=["ml"])),
    (person("find_job", "designer", 2, ["figma", "user_research"], ["ux", "product"], ["16:00"]),
     person("hire", "pm", 7, ["figma", "jira"], ["product"], ["16:00"], seeking_roles=["designer"])),
    (person("find_job", "qa", 1, ["selenium", "postman"], ["fintech"], ["11:30"]),
     person("hire", "lead", 10, ["selenium", "java"], ["fintech"], ["11:30"], seeking_roles=["qa"])),
    (person("find_job", "devops", 4, ["docker", "kubernetes", "aws"], ["cloud"], ["14:30"]),
     person("hire", "recruiter", 6, ["kubernetes"], ["cloud"], ["14:30"], seeking_roles=["devops"])),
    (person("find_mentor", "frontend", 1, ["javascript", "react"], ["career"], ["12:00"]),
     person("be_mentor", "frontend", 8, ["javascript", "react"], ["mentorship"], ["12:00"])),
    (person("find_mentor", "analyst", 1, ["sql", "excel"], ["data_science"], ["15:30"]),
     person("be_mentor", "analyst", 7, ["sql", "powerbi"], ["data_science"], ["15:30"])),
    (person("find_cofounder", "backend", 5, ["go", "postgresql"], ["startups", "fintech"], ["16:30"],
            seeking_roles=["founder"]),
     person("find_cofounder", "founder", 6, ["product_analytics"], ["startups", "fintech"], ["16:30"],
            seeking_roles=["backend"])),
    (person("find_cofounder", "designer", 4, ["figma"], ["startups", "product"], ["13:30"], seeking_roles=["fullstack"]),
     person("find_cofounder", "fullstack", 5, ["react", "nodejs"], ["startups", "product"], ["13:30"],
            seeking_roles=["designer"])),
    (person("exchange", "data_engineer", 4, ["spark", "airflow", "python"], ["data_science", "cloud"], ["11:00"]),
     person("exchange", "data_engineer", 5, ["spark", "airflow"], ["data_science"], ["11:00"])),
    (person("exchange", "pm", 3, ["jira", "product_analytics"], ["product", "ai"], ["14:00"]),
     person("exchange", "pm", 5, ["jira", "product_analytics"], ["product"], ["14:00"])),
]
PAIR_CASES = list(itertools.product(range(len(EVENTS)), range(len(PAIRS))))[:140]
GROUP_TYPES = [("find_job", "backend", 3), ("exchange", "pm", 4), ("find_cofounder", "founder", 3),
               ("find_mentor", "student", 4), ("hire", "recruiter", 3), ("be_mentor", "lead", 4)]
GROUP_CASES = [(e, goal, role, size) for e, (goal, role, size)
               in itertools.product(range(len(EVENTS)), GROUP_TYPES)][:60]


@pytest.fixture
def stores(tmp_path):
    return HallStore(tmp_path / "hall.json"), FeedbackStore(tmp_path / "feedback.json")


def test_there_are_200_scenarios():
    assert len(PAIR_CASES) + len(GROUP_CASES) == 200


@pytest.mark.parametrize("event_i,pair_i", PAIR_CASES)
def test_pair_meets_mutually(stores, event_i, pair_i):
    hall, feedback = stores
    event = EVENTS[event_i]
    a_raw, b_raw = PAIRS[pair_i]
    tg_a, tg_b = f"wm_a_{event_i}_{pair_i}", f"wm_b_{event_i}_{pair_i}"
    a = hall.join({**prepare(a_raw), "name": "Арман", "telegram": tg_a}, "ru", "Гость", event=event["id"])
    b = hall.join({**prepare(b_raw), "name": "Дана", "telegram": tg_b}, "ru", "Гость", event=event["id"])
    profiles = PROFILES + hall.all()
    here = attendee_ids(event, profiles)
    assert {a["id"], b["id"]} <= here                      # оба — участники этого события

    # взаимность целей: каждый есть среди кандидатов другого на этом событии
    m = Matcher(profiles)
    not_here = {p["id"] for p in profiles} - here
    a_sees = {r.profile["id"]: r.score for r in m.recommend({**prepare(a_raw), "id": a["id"]}, k=400, exclude=not_here)}
    b_sees = {r.profile["id"]: r.score for r in m.recommend({**prepare(b_raw), "id": b["id"]}, k=400, exclude=not_here)}
    assert b["id"] in a_sees and a["id"] in b_sees

    # нажал только А — пока не взаимно; нажали оба — взаимно у обоих
    feedback.add("met", b["id"], a["goal"], from_id=a["id"])
    assert not is_mutual(b, a_sees[b["id"]], a["id"], a["id"], feedback.all())
    feedback.add("met", a["id"], b["goal"], from_id=b["id"])
    assert is_mutual(b, a_sees[b["id"]], a["id"], a["id"], feedback.all())
    assert is_mutual(a, b_sees[a["id"]], b["id"], b["id"], feedback.all())
    assert telegram_url(b["telegram"]) == f"https://t.me/{tg_b}"   # А видит Telegram Б
    assert telegram_url(a["telegram"]) == f"https://t.me/{tg_a}"   # и наоборот
    assert (a["name"], b["name"]) == ("Арман", "Дана")
    assert feedback.stats()["met"] == 2


@pytest.mark.parametrize("event_i,goal,role,size", GROUP_CASES)
def test_group_of_three_or_four_meets(stores, event_i, goal, role, size):
    hall, feedback = stores
    event = EVENTS[event_i]
    me = hall.join({**prepare(person(goal, role, 3, ["python"], ["ai"], ["14:00"])),
                    "name": "Гость", "telegram": f"wm_g_{event_i}"}, "ru", "Гость", event=event["id"])
    profiles = PROFILES + hall.all()
    here = attendee_ids(event, profiles)
    group = suggest_group(me, [p for p in profiles if p["id"] in here], size=size - 1)
    assert group is not None and len(group.members) == size - 1   # компания из 3–4 вместе со мной
    assert all(p["goal"] == goal and p["id"] in here for p in group.members)
    assert me["id"] not in {p["id"] for p in group.members}
    assert len({p["id"] for p in group.members}) == size - 1       # без повторов

    for p in [me] + group.members:                                 # все записались на одну встречу
        feedback.add("group", group.key, goal, from_id=p["id"])
    assert feedback.going(group.key) == size
    assert feedback.stats()["groups"] == size
    assert group.slot and 1 <= group.table <= 12

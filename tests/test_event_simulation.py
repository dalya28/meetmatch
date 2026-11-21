"""Симуляция мероприятий: 20 пар и 10 компаний по 3–4 человека знакомятся в живом зале.

Пара: оба участника заполнили анкету на одном событии (попали в живой зал), видят друг друга
в подборе (взаимность целей), оба нажали «Познакомиться» → «Это взаимно!» и Telegram.
Компания: участник и 2–3 человека с той же целью на том же событии записываются на одну встречу.
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
# пары взаимных целей: (кто ищет, кто отвечает)
PAIRS = [
    ({"goal": "find_job", "role": "backend", "experience": 2, "stack": ["python", "django"],
      "interests": ["fintech"], "slots": ["11:00", "14:00"]},
     {"goal": "hire", "role": "recruiter", "experience": 5, "seeking_roles": ["backend"],
      "stack": ["python"], "interests": ["fintech"], "slots": ["11:00"]}),
    ({"goal": "find_mentor", "role": "student", "experience": 0, "stack": ["sql", "python"],
      "interests": ["data_science"], "slots": ["12:00"]},
     {"goal": "be_mentor", "role": "data", "experience": 9, "stack": ["sql", "python"],
      "interests": ["data_science"], "slots": ["12:00"]}),
]
PAIR_CASES = list(itertools.product(range(len(EVENTS)), range(len(PAIRS))))[:20]
GROUP_CASES = [(e, g, size) for e, (g, size) in zip(
    range(10), itertools.cycle([("find_job", 3), ("exchange", 4), ("find_cofounder", 3),
                                ("find_mentor", 4), ("hire", 3)]))]


@pytest.fixture
def stores(tmp_path):
    return HallStore(tmp_path / "hall.json"), FeedbackStore(tmp_path / "feedback.json")


@pytest.mark.parametrize("event_i,pair_i", PAIR_CASES)
def test_pair_meets_mutually(stores, event_i, pair_i):
    hall, feedback = stores
    event = EVENTS[event_i]
    a_raw, b_raw = PAIRS[pair_i]
    a = hall.join(prepare(a_raw), "ru", "Гость", event=event["id"])
    b = hall.join({**prepare(b_raw), "telegram": f"wm_test_{event_i}_{pair_i}"}, "ru", "Гость", event=event["id"])
    profiles = PROFILES + hall.all()
    here = attendee_ids(event, profiles)
    assert {a["id"], b["id"]} <= here                      # оба — участники этого события

    # взаимность целей: каждый есть среди кандидатов другого на этом событии
    m = Matcher(profiles)
    not_here = {p["id"] for p in profiles} - here
    a_q = {**prepare(a_raw), "id": a["id"]}
    b_q = {**prepare(b_raw), "id": b["id"]}
    a_sees = {r.profile["id"]: r.score for r in m.recommend(a_q, k=400, exclude=not_here)}
    b_sees = {r.profile["id"]: r.score for r in m.recommend(b_q, k=400, exclude=not_here)}
    assert b["id"] in a_sees and a["id"] in b_sees

    # нажал только А — пока не взаимно; нажали оба — взаимно у обоих
    feedback.add("met", b["id"], a["goal"], from_id=a["id"])
    assert not is_mutual(b, a_sees[b["id"]], a["id"], a["id"], feedback.all())
    feedback.add("met", a["id"], b["goal"], from_id=b["id"])
    assert is_mutual(b, a_sees[b["id"]], a["id"], a["id"], feedback.all())
    assert is_mutual(a, b_sees[a["id"]], b["id"], b["id"], feedback.all())
    assert telegram_url(b["telegram"]) == f"https://t.me/wm_test_{event_i}_{pair_i}"
    assert feedback.stats()["met"] == 2


@pytest.mark.parametrize("event_i,goal,size", GROUP_CASES)
def test_group_of_three_or_four_meets(stores, event_i, goal, size):
    hall, feedback = stores
    event = EVENTS[event_i]
    me = hall.join(prepare({"goal": goal, "role": "backend", "experience": 3, "stack": ["python"],
                            "interests": ["ai"], "slots": ["14:00"]}), "ru", "Гость", event=event["id"])
    profiles = PROFILES + hall.all()
    here = attendee_ids(event, profiles)
    group = suggest_group(me, [p for p in profiles if p["id"] in here], size=size - 1)
    assert group is not None and len(group.members) == size - 1   # компания из 3–4 вместе со мной
    assert all(p["goal"] == goal and p["id"] in here for p in group.members)
    assert me["id"] not in {p["id"] for p in group.members}

    for person in [me] + group.members:                          # все записались на одну встречу
        feedback.add("group", group.key, goal, from_id=person["id"])
    assert feedback.going(group.key) == size
    assert feedback.stats()["groups"] == size
    assert group.slot and 1 <= group.table <= 12

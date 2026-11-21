"""Демо-активность для дашборда организатора: симуляция одного события на синтетических анкетах.

Пока на живом сайте никто не знакомился, дашборд показывал нули. Здесь участники из синтетической
базы проходят тот же путь, что и настоящие, через те же функции Wingman:
подбор пяти человек (Matcher) → «Познакомиться» / «Не подходит» → взаимный мэтч → бинго
(bingo_card / bingo_tick / bingo_lines) → встреча в компании (suggest_group) → отзыв о встрече.

Результат детерминирован (seed) и лежит в data/demo_activity.json; пересобрать:
    python demo_activity.py
Демо-события не попадают в живой зал и в подбор — только в цифры дашборда, с пометкой «демо».
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from config import DATA_DIR
from events import DEFAULT_EVENT, attendee_ids, load_events
from groups import suggest_group
from matcher import Matcher, load_profiles
from social import ACTIVITIES, bingo_card, bingo_lines, bingo_reach, bingo_tick

DEMO_PATH = DATA_DIR / "demo_activity.json"
TIME = "2026-11-20T{:02d}:{:02d}:00"

LEARNED = [
    "Узнал, как в их команде устроено код-ревью — заберу идею к себе.",
    "Договорились о тестовом задании на стажировку.",
    "Получила совет, какие пет-проекты показывать на собеседовании.",
    "Нашли общий интерес к финтеху, обменялись Telegram.",
    "Ментор разобрал моё резюме за 10 минут — очень полезно.",
    "Поняла, какие навыки нужны для перехода в аналитику данных.",
    "Обсудили идею стартапа, встречаемся ещё раз во вторник.",
    "Рассказали, как они нанимают джунов и что смотрят в GitHub.",
]


def simulate(n_people: int = 40, seed: int = 20261120) -> dict:
    rng = random.Random(seed)
    profiles = load_profiles()
    event = next(e for e in load_events() if e["id"] == DEFAULT_EVENT)
    here = attendee_ids(event, profiles)
    crowd = [p for p in profiles if p["id"] in here]
    people = rng.sample(crowd, min(n_people, len(crowd)))
    m = Matcher(profiles)
    not_here = {p["id"] for p in profiles} - here

    feedback, reviews = [], []
    clicks: dict[str, set[str]] = {}                 # кто кому нажал «Познакомиться»
    minute = 0

    def stamp() -> str:
        nonlocal minute
        minute += 1
        return TIME.format(10 + minute // 60 % 9, minute % 60)

    for person in people:
        recs = m.recommend(person, k=5, exclude=not_here | {person["id"]})
        card = bingo_card([r.profile for r in recs], f"{event['id']}:{person['id']}", event)
        reach, done = bingo_reach([r.profile for r in recs]), {}
        for r in recs:
            # чем выше совпадение, тем чаще человек нажимает «Познакомиться» — как в жизни
            if rng.random() < 0.35 + 0.6 * r.score / 100:
                feedback.append({"time": stamp(), "action": "met", "candidate_id": r.profile["id"],
                                 "goal": person["goal"], "from": person["id"]})
                clicks.setdefault(person["id"], set()).add(r.profile["id"])
                bingo_tick(card, done, r.profile, reach)
            else:
                feedback.append({"time": stamp(), "action": "not_fit", "candidate_id": r.profile["id"],
                                 "goal": person["goal"]})
        for i, task in enumerate(card):              # задания-активности отмечают сами, кнопкой
            if task in ACTIVITIES and str(i) not in done and rng.random() < 0.5:
                done[str(i)] = ""
        if bingo_lines(done):
            feedback.append({"time": stamp(), "action": "bingo", "candidate_id": event["id"],
                             "goal": person["goal"]})

    # встречи в компании: часть людей записывается вместе с 2–3 единомышленниками
    joined: set[str] = set()
    for person in people[: n_people // 3]:
        if person["id"] in joined:
            continue
        group = suggest_group(person, [p for p in people if p["id"] not in joined], size=rng.choice([2, 3]))
        if group is None:
            continue
        for member in [person] + group.members:
            joined.add(member["id"])
            feedback.append({"time": stamp(), "action": "group", "candidate_id": group.key,
                             "goal": person["goal"], "from": member["id"]})

    # отзыв после встречи: большинство тех, кто нажал «Познакомиться», встретились
    for who, picked in clicks.items():
        for pid in sorted(picked):
            if rng.random() > 0.45:
                continue
            happened = rng.random() < 0.85
            reviews.append({"time": stamp(), "event": event["id"], "candidate_id": pid, "happened": happened,
                            "rating": rng.choice([4, 5, 5, 5, 3]) if happened else None,
                            "learned": rng.choice(LEARNED) if happened and rng.random() < 0.5 else "",
                            "helped": rng.choice(["yes", "yes", "partly"]) if happened else None,
                            "next": rng.choice(["yes", "maybe"]) if happened else None})

    return {"event": event["id"], "people": [p["id"] for p in people],
            "feedback": feedback, "reviews": reviews}


def load_demo(path: Path = DEMO_PATH) -> dict:
    """Пустая активность, если файла нет или он битый: дашборд просто покажет только живые цифры."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {"event": data.get("event"), "people": list(data.get("people", [])),
                "feedback": list(data.get("feedback", [])), "reviews": list(data.get("reviews", []))}
    except (OSError, ValueError, AttributeError):
        return {"event": None, "people": [], "feedback": [], "reviews": []}


if __name__ == "__main__":
    data = simulate()
    DEMO_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    acts = [e["action"] for e in data["feedback"]]
    print(f"people={len(data['people'])} met={acts.count('met')} not_fit={acts.count('not_fit')} "
          f"group={acts.count('group')} bingo={acts.count('bingo')} reviews={len(data['reviews'])}")

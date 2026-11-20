"""Встречи в компании: 3–4 человека с той же целью встречаются вместе.

Зачем: не всем легко подойти к незнакомцу один на один. В небольшой компании с общей целью
и темой разговор начинается проще, а дальше люди сами решают, с кем продолжить.

Как собирается группа:
  1. Кандидаты — участники с ТОЙ ЖЕ целью (не взаимной, как в знакомствах 1:1).
  2. Близость к участнику: роль, интересы, стек, общий свободный слот.
  3. Связность: каждый следующий выбирается так, чтобы был близок не только ко мне,
     но и к уже выбранным — иначе получится случайный набор людей.
  4. Время — слот, в который свободно больше всего участников; тема — самый частый
     содержательный интерес; место — стол в зоне нетворкинга.
"""
from __future__ import annotations

import zlib
from collections import Counter
from dataclasses import dataclass, field

from matcher import _role_similarity_sets, _set_cosine, _stack_score
from taxonomy import EVENT_SLOTS, LOW_INFO_INTERESTS, effective_roles

GROUP_SIZE = 3      # сколько человек подбираем к участнику: вместе с ним — компания из 4
TABLES = 12         # столов в зоне нетворкинга


@dataclass
class Group:
    members: list[dict]
    slot: str | None
    topic: str | None
    table: int
    shared: dict = field(default_factory=dict)  # id участника → общие интересы с вами

    @property
    def key(self) -> str:
        return "+".join(sorted(m["id"] for m in self.members))


def _closeness(a: dict, b: dict) -> float:
    roles = _role_similarity_sets(effective_roles(a["role"], a["stack"]), effective_roles(b["role"], b["stack"]))
    slots = 1.0 if set(a.get("slots") or []) & set(b.get("slots") or []) else 0.0
    return (0.35 * roles + 0.30 * _set_cosine(a["interests"], b["interests"])
            + 0.20 * _stack_score(a["stack"], b["stack"]) + 0.15 * slots)


def suggest_group(q: dict, profiles: list[dict], exclude=(), size: int = GROUP_SIZE) -> Group | None:
    exclude = set(exclude) | {q.get("id")}
    peers = [c for c in profiles if c["goal"] == q["goal"] and c["id"] not in exclude]
    if len(peers) < 2:
        return None
    to_me = {c["id"]: _closeness(q, c) for c in peers}
    picked: list[dict] = []
    pool = sorted(peers, key=lambda c: -to_me[c["id"]])[:30]
    while pool and len(picked) < size:
        # близость ко мне + средняя близость к уже выбранным
        def score(c):
            if not picked:
                return to_me[c["id"]]
            return 0.6 * to_me[c["id"]] + 0.4 * sum(_closeness(c, p) for p in picked) / len(picked)
        best = max(pool, key=score)
        pool.remove(best)
        picked.append(best)

    everyone = [q] + picked
    counts = Counter(s for p in everyone for s in (p.get("slots") or []))
    mine = set(q.get("slots") or [])
    # слот, где свободно больше всего людей; при равенстве — тот, где свободен я, затем раньше
    slot = max(EVENT_SLOTS, key=lambda s: (counts[s], s in mine, -EVENT_SLOTS.index(s))) if counts else None

    topics = Counter(i for p in everyone for i in p["interests"] if i not in LOW_INFO_INTERESTS)
    for i in q["interests"]:  # ваши интересы — в приоритете при равенстве
        if i in topics:
            topics[i] += 0.5
    topic = topics.most_common(1)[0][0] if topics else None

    key = "+".join(sorted(p["id"] for p in picked))
    table = zlib.crc32(key.encode()) % TABLES + 1
    shared = {p["id"]: [i for i in p["interests"] if i in set(q["interests"])] for p in picked}
    return Group(members=picked, slot=slot, topic=topic, table=table, shared=shared)

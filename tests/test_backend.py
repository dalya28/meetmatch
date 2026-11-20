"""Бэкенд: проверка входных данных, хранилище на диске, живой зал, потоки, масштаб."""
import json
import statistics
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import MAX_ABOUT_LEN, MAX_LIST_ITEMS  # noqa: E402
from matcher import Matcher, load_profiles, prepare, sanitize_query  # noqa: E402
from storage import FeedbackStore, HallStore, JsonListStore  # noqa: E402

BASE = load_profiles()


# ---------------------------------------------------------------- проверка входных данных
def test_sanitize_drops_garbage():
    q = sanitize_query({"role": "astronaut", "goal": "rule_the_world", "experience": -7,
                        "stack": ["python", "cobol", "python", 42], "interests": "fintech",
                        "about": "x" * 5000, "slots": ["11:00", "03:00"], "name": "  Айгерим  "})
    assert q["role"] == "backend" and q["goal"] == "exchange"
    assert q["experience"] == 0
    assert q["stack"] == ["python"]
    assert q["interests"] == []
    assert len(q["about"]) == MAX_ABOUT_LEN
    assert q["slots"] == ["11:00"]
    assert q["name"] == "Айгерим"


def test_sanitize_limits_lists_and_survives_wrong_types():
    q = sanitize_query({"stack": [s for s in ("python", "django", "fastapi", "java", "spring", "go",
                                               "nodejs", "csharp", "dotnet", "php", "laravel", "onec",
                                               "react", "vue")],
                        "experience": "десять"})
    assert len(q["stack"]) == MAX_LIST_ITEMS
    assert q["experience"] == 1
    assert sanitize_query(None)["goal"] == "exchange"


def test_matcher_never_crashes_on_garbage_query():
    m = Matcher(BASE)
    for raw in ({}, {"goal": None, "role": None}, {"stack": None, "about": None},
                {"experience": "∞", "goal": "hire", "about": "😀" * 1000}):
        assert len(m.recommend(raw)) == 5


# ---------------------------------------------------------------- хранилище
def test_feedback_survives_restart(tmp_path):
    path = tmp_path / "feedback.json"
    FeedbackStore(path).add("met", "p001", "find_job")
    FeedbackStore(path).add("not_fit", "p002", "find_job")
    reopened = FeedbackStore(path)  # «перезапуск» приложения
    assert [e["candidate_id"] for e in reopened.all()] == ["p001", "p002"]
    assert reopened.stats() == {"total": 2, "met": 1, "not_fit": 1, "groups": 0, "bingo": 0, "met_share": 0.5}
    with pytest.raises(ValueError):
        reopened.add("hacked", "p003", "find_job")


def test_corrupt_file_is_moved_aside_not_fatal(tmp_path):
    path = tmp_path / "feedback.json"
    path.write_text("{ это не json", encoding="utf-8")
    store = FeedbackStore(path)
    assert store.all() == []
    assert list(tmp_path.glob("feedback.json.corrupt-*"))
    store.add("met", "p001", "hire")
    assert json.loads(path.read_text(encoding="utf-8"))[0]["candidate_id"] == "p001"


def test_concurrent_appends_lose_nothing(tmp_path):
    store = JsonListStore(tmp_path / "items.json")

    def worker(n):
        for i in range(25):
            store.append({"worker": n, "i": i})

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    on_disk = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    assert len(on_disk) == len(store.all()) == 200
    assert not list(tmp_path.glob("*.tmp"))  # атомарная запись не оставляет мусора


# ---------------------------------------------------------------- живой зал
def _hall_hirer():
    return prepare({"name": "Тест Рекрутер", "role": "recruiter", "experience": 5, "goal": "hire",
                    "stack": ["react", "typescript", "nextjs"], "interests": ["ecommerce", "ux"],
                    "about": "Нанимаем фронтенд-разработчика на React и Next.js, уровень middle",
                    "slots": ["11:00", "14:00"]})


def test_hall_participant_is_visible_to_others_but_not_to_self(tmp_path):
    m = Matcher(BASE)
    hall = HallStore(tmp_path / "hall.json")
    profile = hall.join(_hall_hirer(), "ru", guest_name="Участник")
    m.add_profiles([profile])
    pid = profile["id"]
    assert pid.startswith("h") and profile["hire_exp_min"] == 2

    seeker = {"role": "frontend", "experience": 3, "goal": "find_job",
              "stack": ["react", "typescript", "nextjs"], "interests": ["ecommerce", "ux"],
              "about": "Frontend на React и Next.js, хочу в e-commerce"}
    assert pid in [r.profile["id"] for r in m.recommend(seeker)]

    me = {**_hall_hirer(), "id": pid}
    assert pid not in [r.profile["id"] for r in m.recommend(me)]


def test_hall_survives_restart_and_ids_do_not_clash(tmp_path):
    path = tmp_path / "hall.json"
    first = HallStore(path).join(_hall_hirer(), "ru", guest_name="Участник")
    second = HallStore(path).join(prepare({"goal": "exchange", "role": "qa"}), "kk", guest_name="Қатысушы")
    assert second["id"] != first["id"] and second["name"] == "Қатысушы 2"
    m = Matcher(BASE)
    m.add_profiles(HallStore(path).all())
    m.add_profiles(HallStore(path).all())  # повторная загрузка не дублирует
    assert len(m.profiles) == len(BASE) + 2
    assert set(m.by_id) - {p["id"] for p in BASE} == {first["id"], second["id"]}
    hall = HallStore(path)
    hall.clear()
    third = hall.join(_hall_hirer(), "en", guest_name="Guest")
    assert third["id"] not in {first["id"], second["id"]}


def test_adding_to_hall_while_others_search_is_safe(tmp_path):
    m = Matcher(BASE)
    hall = HallStore(tmp_path / "hall.json")
    errors = []

    def joiner():
        for _ in range(30):
            m.add_profiles([hall.join(_hall_hirer(), "ru", guest_name="Участник")])

    def searcher():
        try:
            for _ in range(30):
                assert len(m.recommend({"role": "frontend", "goal": "find_job", "stack": ["react"]})) == 5
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=joiner)] + [threading.Thread(target=searcher) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors
    assert len(m.profiles) == len(BASE) + 30


# ---------------------------------------------------------------- масштаб
def _scaled(n: int) -> list[dict]:
    out = []
    while len(out) < n:
        for p in BASE:
            out.append({**p, "id": f"s{len(out):05d}"})
            if len(out) == n:
                break
    return out


@pytest.mark.parametrize("n", [1000, 5000])
def test_recommend_stays_under_3_seconds_at_scale(n):
    m = Matcher(_scaled(n))
    queries = BASE[:20]
    times = []
    for q in queries:
        t0 = time.perf_counter()
        m.recommend(q)
        times.append(time.perf_counter() - t0)
    assert max(times) < 3.0
    assert statistics.median(times) < 0.5

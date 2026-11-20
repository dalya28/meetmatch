"""Качество базы анкет: валидатор должен проходить без ошибок и ловить испорченные данные."""
import copy
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.validate_data as vd  # noqa: E402
from taxonomy import extract_tags  # noqa: E402

PROFILES = json.loads((ROOT / "data" / "profiles.json").read_text(encoding="utf-8"))


def test_dataset_passes_validation():
    errors, info = vd.validate()
    assert errors == [], errors
    assert info["profiles"] >= 100


def test_validator_catches_broken_data():
    bad = copy.deepcopy(PROFILES)
    bad[0]["about"] = "Пишите мне: test.user@example.com или +7 701 123 45 67"
    bad[1]["role"] = "astronaut"
    next(p for p in bad if p["goal"] == "be_mentor")["experience"] = 2
    next(p for p in bad if p["goal"] == "hire")["seeking_roles"] = []
    bad[5]["name"] = bad[6]["name"]
    schema_errors = list(jsonschema.Draft202012Validator(vd.build_schema()).iter_errors(bad))
    rule_errors = vd.check_rules(bad)
    assert len(schema_errors) == 1
    assert len(rule_errors) == 4


def test_roles_from_free_text_in_three_languages():
    cases = {
        "Ищу data engineer позицию, Airflow и ClickHouse": "data_engineer",
        "Деректер инженерімін, Spark қолданамын": "data_engineer",
        "Пентестер, работаю в SOC": "security",
        "Системный аналитик в банке, BPMN": "analyst",
        "Нужен CTO в кофаундеры": "lead",
        "Game developer, Unity": "gamedev",
    }
    for text, role in cases.items():
        assert role in extract_tags(text)["roles"], text

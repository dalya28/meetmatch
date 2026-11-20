"""Настройки Wingman в одном месте.

Всё, что зависит от окружения, можно переопределить переменными окружения (12-factor):

    MEETMATCH_DATA_DIR    папка с базой анкет и стендами        (по умолчанию ./data)
    MEETMATCH_STATE_DIR   папка с живыми данными: отзывы, живой зал (по умолчанию ./data/state)
    MEETMATCH_LOG_LEVEL   уровень логов: DEBUG / INFO / WARNING  (по умолчанию INFO)
    MEETMATCH_HALL        «живой зал» включён: 1 / 0              (по умолчанию 1)

База анкет — только для чтения. Живые данные пишутся отдельно, в STATE_DIR: в Docker это том,
который переживает перезапуск контейнера, а в git эта папка не попадает.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


# ---------------------------------------------------------------- пути
DATA_DIR = _env_path("MEETMATCH_DATA_DIR", ROOT / "data")
STATE_DIR = _env_path("MEETMATCH_STATE_DIR", DATA_DIR / "state")
PROFILES_PATH = DATA_DIR / "profiles.json"
BOOTHS_PATH = DATA_DIR / "booths.json"
FEEDBACK_PATH = STATE_DIR / "feedback.json"
HALL_PATH = STATE_DIR / "hall.json"

# ---------------------------------------------------------------- подбор
# Веса после офлайн-оценки шага 4 (docs/04-evaluation.md): интересы 0.20 → 0.10 улучшили nDCG@5
# на всех трёх фолдах кросс-валидации; остальные веса пропорционально нормированы.
WEIGHTS = {"role": 0.34, "stack": 0.28, "experience": 0.17, "interests": 0.10, "text": 0.11}
REJECT_PENALTY = 0.05        # «не подошло»: понижаем людей той же (не искомой) роли
SAME_COMPANY_PENALTY = 0.08  # разнообразие топ-5: не больше одного человека из компании подряд
SAME_ROLE_PENALTY = 0.03
TOP_K = 5
RERANK_POOL = 40             # из скольких лучших собираем разнообразный топ-5

# ---------------------------------------------------------------- лимиты анкеты
# Защита от мусора и злоупотреблений: анкету заполняет кто угодно в зале.
MAX_NAME_LEN = 60
MAX_ABOUT_LEN = 600
MAX_LIST_ITEMS = 12          # стек, интересы, «кого ищу»
MAX_EXPERIENCE = 40
MAX_HALL_SIZE = 2000         # живой зал больше этого — значит, что-то пошло не так

# ---------------------------------------------------------------- живой зал и логи
HALL_ENABLED = os.environ.get("MEETMATCH_HALL", "1") != "0"
LOG_LEVEL = os.environ.get("MEETMATCH_LOG_LEVEL", "INFO").upper()


def setup_logging() -> logging.Logger:
    """Логи в stdout в формате ключ=значение: их собирают Docker и Streamlit Cloud.
    Персональные данные (имена, тексты анкет) в логи не пишем — только id и числа."""
    logger = logging.getLogger("meetmatch")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(LOG_LEVEL)
    return logger

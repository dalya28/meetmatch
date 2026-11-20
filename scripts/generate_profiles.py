"""Генератор синтетических анкет MeetMatch.

Все имена и компании вымышлены, реальные профили не используются.
Скрипт детерминированный (seed=42): повторный запуск даёт ту же базу.

Запуск из корня проекта:  python scripts/generate_profiles.py
Результат: data/profiles.json, data/profiles.csv, data/booths.json
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from taxonomy import (EVENT_SLOTS, INTERESTS, LEVELS, LOW_INFO_INTERESTS, ROLES,  # noqa: E402
                      SPECIALIST_ROLES, exp_phrase, interest_label, role_label, stack_label)

rng = random.Random(42)

COUNTS = {"find_job": 58, "hire": 48, "find_mentor": 36, "be_mentor": 34,
          "find_cofounder": 29, "exchange": 46}
LANG_WEIGHTS = [("ru", 0.55), ("kk", 0.20), ("en", 0.25)]
# Сколько «лишних» анкет сверх минимального покрытия получает роль — по популярности на рынке.
ROLE_WEIGHTS = {"backend": 4, "frontend": 3, "ml": 3, "data": 2, "mobile": 2, "qa": 2,
                "devops": 2, "fullstack": 2, "pm": 1, "designer": 2, "data_engineer": 2,
                "analyst": 2, "security": 1, "gamedev": 1}

# ---------------------------------------------------------------- имена (вымышленные сочетания)
MALE = ["Данияр", "Алихан", "Нурлан", "Ерлан", "Арман", "Тимур", "Ержан", "Бекзат", "Санжар",
        "Асхат", "Айбек", "Мирас", "Ильяс", "Дамир", "Руслан", "Азамат", "Жандос", "Олжас",
        "Темирлан", "Дмитрий", "Алексей", "Максим", "Артём", "Никита"]
FEMALE = ["Айгерим", "Мадина", "Асель", "Жанна", "Динара", "Камила", "Айдана", "Аружан",
          "Томирис", "Дана", "Алия", "Жансая", "Сабина", "Акмарал", "Гульнара", "Меруерт",
          "Назерке", "Дария", "Анна", "Екатерина", "Мария", "Ксения", "Полина", "Виктория"]
SURNAMES = [("Сапаров", "Сапарова"), ("Нурланов", "Нурланова"), ("Ахметов", "Ахметова"),
            ("Жумабаев", "Жумабаева"), ("Касымов", "Касымова"), ("Омаров", "Омарова"),
            ("Бекетов", "Бекетова"), ("Туребаев", "Туребаева"), ("Абенов", "Абенова"),
            ("Кенжебаев", "Кенжебаева"), ("Исаев", "Исаева"), ("Байжанов", "Байжанова"),
            ("Есенов", "Есенова"), ("Тлеубаев", "Тлеубаева"), ("Мусин", "Мусина"),
            ("Сейткали", "Сейткали"), ("Ким", "Ким"), ("Пак", "Пак"), ("Цой", "Цой"),
            ("Иванов", "Иванова"), ("Смирнов", "Смирнова"), ("Попов", "Попова")]
TRANSLIT = {"а": "a", "ә": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e",
            "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q", "л": "l",
            "м": "m", "н": "n", "ң": "ng", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s",
            "т": "t", "у": "u", "ұ": "u", "ү": "u", "ф": "f", "х": "kh", "һ": "h", "ц": "ts",
            "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "і": "i", "ь": "", "э": "e",
            "ю": "yu", "я": "ya"}


def translit(text: str) -> str:
    out = "".join(TRANSLIT.get(ch.lower(), ch) for ch in text)
    return " ".join(w[:1].upper() + w[1:] for w in out.split())


_used_names: set[str] = set()


def make_name(lang: str) -> str:
    while True:
        female = rng.random() < 0.5
        first = rng.choice(FEMALE if female else MALE)
        last = rng.choice(SURNAMES)[1 if female else 0]
        name = f"{first} {last}"
        if lang == "en":
            name = translit(name)
        if name not in _used_names:
            _used_names.add(name)
            return name


# ---------------------------------------------------------------- компании (вымышленные)
COMPANIES = {
    "Altyn Soft": None, "Nomad Pay": "fintech", "Steppe Labs": "startups",
    "QazCode Studio": None, "Tulpar Tech": None, "Baiterek Data": "data_science",
    "Shanyraq Apps": "ecommerce", "Saryarka Systems": "iot", "Medeu Digital": "govtech",
    "Aral Cloud": "cloud", "Zhetisu Games": "gamedev", "Orda Fintech": "fintech",
    "Kok Tobe AI": "ai", "Irbis Logistics": "logistics", "Dala Agro Tech": "agritech",
    "Samal Health": "healthtech", "Turan EdTech": "edtech", "Kaspian Commerce": "ecommerce",
    "Astra Security": "security", "Ulytau Mobile": None,
}

# ---------------------------------------------------------------- стек и интересы по ролям
ROLE_STACKS = {
    "backend": [["python", "django", "postgresql", "redis", "docker"],
                ["python", "fastapi", "postgresql", "docker", "kafka"],
                ["java", "spring", "postgresql", "kafka", "docker"],
                ["go", "postgresql", "redis", "kafka", "kubernetes"],
                ["csharp", "dotnet", "sql", "docker"],
                ["php", "laravel", "sql", "redis"],
                ["nodejs", "typescript", "mongodb", "redis", "docker"],
                ["onec", "sql", "excel"]],
    "frontend": [["typescript", "react", "nextjs", "javascript", "html_css"],
                 ["javascript", "vue", "typescript", "html_css", "figma"],
                 ["typescript", "angular", "javascript", "html_css"],
                 ["react", "typescript", "html_css", "figma"]],
    "fullstack": [["typescript", "react", "nodejs", "postgresql", "docker"],
                  ["python", "django", "react", "postgresql", "docker"],
                  ["php", "laravel", "vue", "sql"]],
    "mobile": [["kotlin", "ci_cd", "figma"], ["swift", "ci_cd", "figma"],
               ["flutter", "figma", "ci_cd"], ["react_native", "typescript", "javascript"]],
    "ml": [["python", "pytorch", "llm", "nlp", "docker"], ["python", "pytorch", "cv", "docker"],
           ["python", "sklearn", "pandas", "sql"], ["python", "tensorflow", "cv", "pandas"],
           ["python", "llm", "fastapi", "docker"]],
    "data": [["sql", "python", "pandas", "powerbi", "excel"],
             ["sql", "tableau", "excel", "product_analytics"],
             ["sql", "python", "airflow", "spark", "pandas"], ["sql", "powerbi", "excel"]],
    "devops": [["docker", "kubernetes", "terraform", "aws", "linux", "ci_cd"],
               ["docker", "kubernetes", "gcp", "linux", "ci_cd"],
               ["kubernetes", "azure", "terraform", "grafana", "ci_cd"],
               ["linux", "ansible", "docker", "ci_cd", "python"]],
    "qa": [["selenium", "python", "postman", "sql", "jira"],
           ["playwright", "typescript", "javascript", "ci_cd"],
           ["postman", "sql", "jira"], ["selenium", "java", "ci_cd", "jira"]],
    "pm": [["jira", "product_analytics", "figma", "sql"],
           ["jira", "product_analytics", "user_research"],
           ["jira", "excel", "product_analytics"]],
    "designer": [["figma", "user_research", "html_css"],
                 ["figma", "user_research", "product_analytics"], ["figma", "html_css"]],
    "founder": [["product_analytics", "excel", "jira"], ["product_analytics", "figma"],
                ["excel", "jira", "sql"]],
    "data_engineer": [["python", "airflow", "spark", "sql", "kafka"],
                      ["sql", "dbt", "clickhouse", "airflow", "python"],
                      ["python", "spark", "kafka", "postgresql", "docker"]],
    "security": [["linux", "siem", "python", "owasp"], ["burp", "owasp", "python", "linux"],
                 ["siem", "linux", "docker", "grafana"]],
    "gamedev": [["unity", "csharp", "figma"], ["unreal", "cpp", "figma"], ["godot", "csharp"]],
    "analyst": [["sql", "bpmn", "uml", "jira"], ["sql", "excel", "bpmn", "jira"],
                ["uml", "jira", "postman", "sql"]],
    "lead": [["python", "django", "kubernetes", "jira", "postgresql"],
             ["java", "spring", "kafka", "jira", "kubernetes"],
             ["typescript", "react", "nodejs", "jira", "aws"],
             ["go", "kubernetes", "azure", "grafana", "jira"],
             ["rust", "cpp", "linux", "jira"], ["ruby", "postgresql", "redis", "jira"]],
}
ROLE_INTERESTS = {
    "backend": ["cloud", "opensource", "fintech", "ecommerce", "security"],
    "frontend": ["ux", "opensource", "ecommerce", "edtech", "product"],
    "fullstack": ["startups", "opensource", "ecommerce", "cloud"],
    "mobile": ["ux", "ecommerce", "gamedev", "product"],
    "ml": ["ai", "data_science", "healthtech", "opensource", "agritech"],
    "data": ["data_science", "ai", "fintech", "product", "ecommerce"],
    "devops": ["cloud", "security", "opensource"],
    "qa": ["security", "fintech", "edtech", "opensource"],
    "pm": ["product", "ux", "startups", "ecommerce", "fintech"],
    "designer": ["ux", "product", "edtech", "gamedev"],
    "founder": ["startups", "product", "fintech", "edtech", "agritech", "healthtech"],
    "recruiter": ["career", "community", "remote"],
    "student": ["career", "ai", "gamedev", "edtech", "community"],
    "data_engineer": ["data_science", "cloud", "opensource", "fintech", "ecommerce"],
    "security": ["security", "fintech", "govtech", "opensource", "blockchain"],
    "gamedev": ["gamedev", "ux", "startups", "iot"],
    "analyst": ["fintech", "govtech", "product", "ecommerce", "logistics"],
    "lead": ["product", "cloud", "community", "startups", "opensource"],
}
DOMAINS = ["fintech", "edtech", "ecommerce", "gamedev", "govtech", "healthtech",
           "logistics", "agritech", "blockchain", "iot", "ai"]
# Отрасли — то, что подставляется в «в сфере / в направлении / бағыт». Остальные интересы —
# темы (продуктовый подход, open source, облака…): у них свои формулировки (ревью разработчика 1).
INDUSTRIES = set(DOMAINS) | {"security"}
GOAL_INTERESTS = {"find_job": ["career", "remote"], "find_mentor": ["career", "mentorship"],
                  "be_mentor": ["mentorship", "community"], "find_cofounder": ["startups"],
                  "exchange": ["community", "opensource"], "hire": []}


FRONTEND_TECH = {"react", "vue", "angular", "nextjs", "html_css", "javascript", "typescript"}


def pick_stack(role: str, exp: int) -> list[str]:
    variant = rng.choice(ROLE_STACKS[role])
    n = len(variant)
    k = rng.randint(min(2, n), min(3, n)) if exp <= 1 else rng.randint(min(3, n), min(5, n))
    stack = variant[:2] + rng.sample(variant[2:], k - 2)
    # Ревью разработчика 1: fullstack без единой фронтенд-технологии (p233: PHP, Laravel, SQL).
    if role == "fullstack" and not FRONTEND_TECH & set(stack):
        front = next(s for s in variant if s in FRONTEND_TECH)
        stack = stack[:-1] + [front] if len(stack) > 2 else stack + [front]
    return stack


def pick_interests(role: str, goal: str, company: str | None) -> list[str]:
    # Сфера компании идёт первой: её и упоминаем в тексте «о себе».
    out = [COMPANIES[company]] if company and COMPANIES.get(company) else []
    out += rng.sample(ROLE_INTERESTS[role], rng.randint(1, 2))
    if rng.random() < 0.7:
        out.append(rng.choice(DOMAINS))
    if GOAL_INTERESTS[goal] and rng.random() < 0.6:
        out.append(rng.choice(GOAL_INTERESTS[goal]))
    seen: list[str] = []
    for code in out:
        if code in INTERESTS and code not in seen:
            seen.append(code)
    return seen[:4]


def weighted_roles(n: int) -> list[str]:
    roles, weights = zip(*ROLE_WEIGHTS.items())
    return rng.choices(roles, weights=weights, k=n)


def covered_roles(total: int, students: int = 0, min_each: int = 2) -> list[str]:
    """Каждая роль минимум `min_each` раз, остальное — по популярности."""
    roles = SPECIALIST_ROLES * min_each
    roles += weighted_roles(total - len(roles) - students)
    roles += ["student"] * students
    rng.shuffle(roles)
    return roles


# ---------------------------------------------------------------- тексты «о себе»
ABOUT = {
    "find_job": {
        "ru": ["{role} {exp}. Работаю с {stack}. Ищу команду, где можно расти, интересна тема «{interest}».",
               "Ищу работу: {role}, стек — {stack}. Больше всего интересно направление «{interest}».",
               "{role} {exp}, последние проекты на {stack}. Рассматриваю предложения, особенно в сфере «{interest}»."],
        "kk": ["{role}, {exp}. {stack} қолданамын. Өсуге мүмкіндік беретін команда іздеймін, «{interest}» тақырыбы қызықтырады.",
               "Жұмыс іздеп жүрмін: {role}, стек — {stack}. Ең қызықты бағыт — «{interest}».",
               "{role}, {exp}. Соңғы жобаларым {stack} негізінде. Ұсыныстарды қарастырамын, әсіресе «{interest}» саласында."],
        "en": ["{role} {exp}. I work with {stack}. Looking for a team where I can grow; interested in {interest}.",
               "Open to new roles: {role}, stack — {stack}. Most excited about {interest}.",
               "{role} {exp}; recent projects built with {stack}. Considering offers, especially in {interest}."],
    },
    "hire": {
        "ru": ["{role} в {company}. Нанимаем: {seeking} ({levels}). Стек команды — {stack}.",
               "Собираю команду в {company}. Ищем: {seeking}; уровень — {levels}. Работаем с {stack}, направление — «{interest}»."],
        "kk": ["{company} компаниясында {role}. Маман іздейміз: {seeking} ({levels}). Команда стегі — {stack}.",
               "{company} командасын жинап жатырмын: {seeking}, деңгейі — {levels}. {stack} қолданамыз, бағыт — «{interest}»."],
        "en": ["{role} at {company}. We're hiring: {seeking} ({levels}). Team stack — {stack}.",
               "Building the team at {company}: looking for {seeking}, {levels} level. We use {stack}; focus — {interest}."],
    },
    "find_mentor": {
        "ru": ["{role} {exp}. Изучаю {stack}. Ищу ментора, который поможет вырасти в направлении «{interest}».",
               "Хочу расти быстрее: {role}, стек — {stack}. Нужен опытный ментор, интересна тема «{interest}»."],
        "kk": ["{role}, {exp}. {stack} үйреніп жүрмін. «{interest}» бағытында өсуге көмектесетін тәлімгер іздеймін.",
               "Тезірек дамығым келеді: {role}, стек — {stack}. Тәжірибелі тәлімгер керек, «{interest}» тақырыбы қызықты."],
        "en": ["{role} {exp}. Learning {stack}. Looking for a mentor to help me grow in {interest}.",
               "Want to grow faster: {role}, stack — {stack}. Looking for an experienced mentor; into {interest}."],
    },
    "be_mentor": {
        "ru": ["{role} {exp}, сейчас в {company}. Могу менторить по {stack} и помочь с карьерой в IT.",
               "{role} в {company}, {exp}. Хочу делиться опытом: {stack}, тема «{interest}»."],
        "kk": ["{role}, {exp}, қазір {company} компаниясында. {stack} бойынша тәлімгер бола аламын, IT-дағы мансапқа көмектесемін.",
               "{company} компаниясында {role}, {exp}. Тәжірибеммен бөліскім келеді: {stack}, «{interest}» тақырыбы."],
        "en": ["{role} {exp}, currently at {company}. Happy to mentor on {stack} and IT careers.",
               "{role} at {company}, {exp}. I'd like to share my experience: {stack}, {interest}."],
    },
    "find_cofounder": {
        "ru": ["{role} {exp}. Есть идея в сфере «{interest}», ищу кофаундера: {seeking}.",
               "Хочу запустить стартап в направлении «{interest}». Я — {role}, нужен партнёр: {seeking}."],
        "kk": ["{role}, {exp}. «{interest}» саласында идеям бар, кофаундер іздеймін: {seeking}.",
               "«{interest}» бағытында стартап ашқым келеді. Мен — {role}, серіктес керек: {seeking}."],
        "en": ["{role} {exp}. I have an idea in {interest} and I'm looking for a co-founder: {seeking}.",
               "Want to launch a startup in {interest}. I'm {role_a}; looking for a partner: {seeking}."],
    },
    "exchange": {
        "ru": ["{role} в {company}, {exp}. Люблю обсуждать {stack} и тему «{interest}».",
               "{role} {exp}. Хочу обменяться опытом с коллегами: {stack}, «{interest}»."],
        "kk": ["{company} компаниясында {role}, {exp}. {stack} және «{interest}» тақырыбын талқылағанды ұнатамын.",
               "{role}, {exp}. Әріптестермен тәжірибе алмасқым келеді: {stack}, «{interest}»."],
        "en": ["{role} at {company}, {exp}. Love talking about {stack} and {interest}.",
               "{role} {exp}. Here to swap experience with peers: {stack}, {interest}."],
    },
}
LEAD = {"ru": "Тимлид ({role})", "kk": "Тимлид ({role})", "en": "Team lead ({role})"}

# Шаблоны со слотом «отрасль» («в сфере», «в направлении», «бағыт», «стартап в …») и их пары
# со слотом «тема» — для анкет, у которых среди интересов нет отрасли (ревью разработчика 1:
# «стартап в направлении «Продуктовый подход»» звучал абсурдно).
TOPIC_ALT = {
    "Ищу работу: {role}, стек — {stack}. Больше всего интересно направление «{interest}».":
        "Ищу работу: {role}, стек — {stack}. Больше всего интересна тема «{interest}».",
    "{role} {exp}, последние проекты на {stack}. Рассматриваю предложения, особенно в сфере «{interest}».":
        "{role} {exp}, последние проекты на {stack}. Рассматриваю предложения, интересна тема «{interest}».",
    "Жұмыс іздеп жүрмін: {role}, стек — {stack}. Ең қызықты бағыт — «{interest}».":
        "Жұмыс іздеп жүрмін: {role}, стек — {stack}. Ең қызықты тақырып — «{interest}».",
    "{role}, {exp}. Соңғы жобаларым {stack} негізінде. Ұсыныстарды қарастырамын, әсіресе «{interest}» саласында.":
        "{role}, {exp}. Соңғы жобаларым {stack} негізінде. Ұсыныстарды қарастырамын, «{interest}» тақырыбы қызықтырады.",
    "{role} {exp}; recent projects built with {stack}. Considering offers, especially in {interest}.":
        "{role} {exp}; recent projects built with {stack}. Considering offers; into {interest}.",
    "Собираю команду в {company}. Ищем: {seeking}; уровень — {levels}. Работаем с {stack}, направление — «{interest}».":
        "Собираю команду в {company}. Ищем: {seeking}; уровень — {levels}. Работаем с {stack}, нам близка тема «{interest}».",
    "{company} командасын жинап жатырмын: {seeking}, деңгейі — {levels}. {stack} қолданамыз, бағыт — «{interest}».":
        "{company} командасын жинап жатырмын: {seeking}, деңгейі — {levels}. {stack} қолданамыз, бізге «{interest}» тақырыбы жақын.",
    "Building the team at {company}: looking for {seeking}, {levels} level. We use {stack}; focus — {interest}.":
        "Building the team at {company}: looking for {seeking}, {levels} level. We use {stack}; we care about {interest}.",
    "{role} {exp}. Изучаю {stack}. Ищу ментора, который поможет вырасти в направлении «{interest}».":
        "{role} {exp}. Изучаю {stack}. Ищу ментора, интересна тема «{interest}».",
    "{role}, {exp}. {stack} үйреніп жүрмін. «{interest}» бағытында өсуге көмектесетін тәлімгер іздеймін.":
        "{role}, {exp}. {stack} үйреніп жүрмін. Тәлімгер іздеймін, «{interest}» тақырыбы қызықты.",
    "{role} {exp}. Learning {stack}. Looking for a mentor to help me grow in {interest}.":
        "{role} {exp}. Learning {stack}. Looking for a mentor; into {interest}.",
    "{role} {exp}. Есть идея в сфере «{interest}», ищу кофаундера: {seeking}.":
        "{role} {exp}. Есть идея стартапа, ищу кофаундера: {seeking}. Близка тема «{interest}».",
    "Хочу запустить стартап в направлении «{interest}». Я — {role}, нужен партнёр: {seeking}.":
        "Хочу запустить стартап, близка тема «{interest}». Я — {role}, нужен партнёр: {seeking}.",
    "{role}, {exp}. «{interest}» саласында идеям бар, кофаундер іздеймін: {seeking}.":
        "{role}, {exp}. Стартап идеям бар, кофаундер іздеймін: {seeking}. «{interest}» тақырыбы жақын.",
    "«{interest}» бағытында стартап ашқым келеді. Мен — {role}, серіктес керек: {seeking}.":
        "Стартап ашқым келеді, «{interest}» тақырыбы жақын. Мен — {role}, серіктес керек: {seeking}.",
    "{role} {exp}. I have an idea in {interest} and I'm looking for a co-founder: {seeking}.":
        "{role} {exp}. I have a startup idea and I'm looking for a co-founder: {seeking}. Into {interest}.",
    "Want to launch a startup in {interest}. I'm {role_a}; looking for a partner: {seeking}.":
        "Want to launch a startup; into {interest}. I'm {role_a}; looking for a partner: {seeking}.",
}
# Без коммерческого опыта не «работают с» стеком, а изучают его (ревью: p130).
NO_EXP_FIX = {
    "ru": [("Работаю с", "Изучаю"), ("последние проекты на", "учебные проекты на")],
    "kk": [("қолданамын", "үйреніп жүрмін"), ("Соңғы жобаларым", "Оқу жобаларым")],
    "en": [("I work with", "I'm learning"), ("recent projects built with", "study projects built with")],
}


def write_about(p: dict, template: str) -> str:
    """Текст «о себе» по выбранному шаблону. Случайности внутри нет: шаблон выбирает finish()."""
    lang = p["lang"]
    role = role_label(p["role"], lang)
    informative = [i for i in p["interests"] if i not in LOW_INFO_INTERESTS] or p["interests"]
    interest = informative[0] if informative else None
    if template in TOPIC_ALT:  # слот «отрасль»: подставляем отрасль или берём формулировку «тема»
        industry = next((i for i in p["interests"] if i in INDUSTRIES), None)
        if industry:
            interest = industry
        else:
            template = TOPIC_ALT[template]
    text = template.format(
        role=role,
        role_a=ROLES[p["role"]]["en_a"],
        exp=exp_phrase(p["experience"], lang),
        stack=", ".join(stack_label(s) for s in p["stack"][:3]),
        interest=interest_label(interest, lang) if interest else "IT",
        company=p["company"] or "",
        seeking=", ".join(role_label(r, lang) for r in p["seeking_roles"]),
        levels=", ".join(p["hire_levels"]),
    )
    if p["experience"] == 0:
        for old, new in NO_EXP_FIX[lang]:
            text = text.replace(old, new)
    return text


# ---------------------------------------------------------------- сборка анкет
def base(goal: str, role: str, exp: int, company: str | None = None) -> dict:
    lang = rng.choices([l for l, _ in LANG_WEIGHTS], weights=[w for _, w in LANG_WEIGHTS])[0]
    return {
        "id": "", "name": make_name(lang), "lang": lang, "role": role, "experience": exp,
        "stack": [], "interests": [], "about": "", "goal": goal, "seeking_roles": [],
        "hire_levels": [], "hire_exp_min": None, "hire_exp_max": None, "company": company,
        "slots": sorted(rng.sample(EVENT_SLOTS, rng.randint(3, 5)), key=EVENT_SLOTS.index),
    }


def finish(p: dict, stack_role: str | None = None) -> dict:
    if not p["stack"]:
        p["stack"] = pick_stack(stack_role or p["role"], p["experience"])
    p["interests"] = pick_interests(p["role"], p["goal"], p["company"])
    templates = ABOUT[p["goal"]][p["lang"]]
    first = rng.choice(templates)  # единственный случайный выбор текста — как и раньше
    order = [first] + [t for t in templates if t != first]
    # Повторы текста «о себе» убираем без случайности: следующий шаблон, затем сдвиг стека.
    # Так правка текстов не сдвигает остальные анкеты и ручная разметка шага 4 остаётся верной.
    for attempt in range(len(order) * max(1, len(p["stack"]))):
        p["about"] = write_about(p, order[attempt % len(order)])
        if p["about"] not in _used_abouts:
            break
        if attempt % len(order) == len(order) - 1:
            p["stack"] = p["stack"][1:] + p["stack"][:1]
    _used_abouts.add(p["about"])
    return p


_used_abouts: set[str] = set()
STUDENT_SKIP = {"ci_cd", "docker", "jira", "excel"}  # инструменты, а не то, с чего начинают учиться


def student_stack() -> tuple[list[str], str]:
    """Связная пара «язык + основной инструмент» (ревью: у студентов были пары вроде CI/CD + Swift).
    Случайные вызовы те же, что раньше, — чтобы не сдвинуть остальные анкеты."""
    target = rng.choice(["backend", "frontend", "ml", "data", "mobile"])
    variant = rng.choice(ROLE_STACKS[target])
    rng.sample(variant, 2)  # прежний вызов оставлен ради той же последовательности случайных чисел
    core = [s for s in variant if s not in STUDENT_SKIP]
    return [core[0], core[1] if len(core) > 1 else variant[1]], target


def gen_find_job() -> list[dict]:
    out = []
    # + 3 тимлида, которые ищут новую команду: на вакансию тимлида должны находиться тимлиды
    for role in covered_roles(COUNTS["find_job"] - 3, students=3, min_each=3) + ["lead"] * 3:
        if role == "student":
            p = base("find_job", "student", 0)
            p["stack"], _ = student_stack()
        elif role == "lead":
            p = base("find_job", "lead", rng.randint(6, 12))
        else:
            p = base("find_job", role, rng.choice([1, 1, 2, 2, 3, 3, 4, 5, 6, 7]))
        out.append(finish(p))
    return out


def gen_hire() -> list[dict]:
    # Каждую специализацию нанимают минимум 3 раза + популярные роли + 2 вакансии тимлида.
    primaries = SPECIALIST_ROLES * 3 + ["backend", "frontend", "ml", "mobile"] + ["lead"] * 2
    rng.shuffle(primaries)
    out = []
    for primary in primaries:
        company = rng.choice(list(COMPANIES))
        kind = "recruiter" if primary in ("pm", "designer", "analyst", "lead") else rng.choices(
            ["recruiter", "lead", "founder"], weights=[0.4, 0.45, 0.15])[0]
        seeking = [primary]
        if kind == "recruiter":
            for chance in (0.8, 0.3):  # рекрутеры обычно закрывают 2–3 вакансии
                if rng.random() < chance:
                    options = [r for r in ROLE_WEIGHTS if r not in seeking]
                    seeking.append(rng.choices(options, weights=[ROLE_WEIGHTS[r] for r in options])[0])
        if kind == "founder" and rng.random() < 0.4:
            seeking.append(rng.choice([r for r in ("backend", "frontend", "mobile", "ml") if r != primary]))
        if kind == "lead":  # тимлид нанимает в свою команду, стек — команды
            p = base("hire", "lead", rng.randint(6, 14), company)
            p["stack"] = pick_stack(primary, 6)
        else:
            role = "recruiter" if kind == "recruiter" else "founder"
            p = base("hire", role, rng.randint(2, 8) if role == "recruiter" else rng.randint(3, 12), company)
            stack: list[str] = []
            for r in seeking:
                stack += [s for s in pick_stack(r, 3) if s not in stack]
            p["stack"] = stack[:6]
        levels = rng.choices([["junior"], ["junior", "middle"], ["middle"], ["middle", "senior"], ["senior"]],
                             weights=[2, 3, 3, 3, 2])[0]
        p["seeking_roles"] = seeking
        p["hire_levels"] = levels
        p["hire_exp_min"] = LEVELS[levels[0]][0]
        p["hire_exp_max"] = LEVELS[levels[-1]][1]
        out.append(finish(p))
    return out


def gen_find_mentor() -> list[dict]:
    out = []
    for role in covered_roles(COUNTS["find_mentor"], students=4):
        if role == "student":
            p = base("find_mentor", "student", 0)
            p["stack"], _ = student_stack()
        else:
            p = base("find_mentor", role, rng.choice([0, 1, 1, 2, 2, 3]))
        out.append(finish(p))
    return out


def gen_be_mentor() -> list[dict]:
    out = []
    # тимлиды и опытные фаундеры — частые менторы
    for role in covered_roles(COUNTS["be_mentor"] - 6) + ["lead"] * 4 + ["founder"] * 2:
        p = base("be_mentor", role, rng.randint(6, 15), rng.choice(list(COMPANIES)))
        out.append(finish(p))
    return out


def gen_cofounder() -> list[dict]:
    roles = (["backend"] * 3 + ["fullstack"] * 3 + ["ml"] * 3 + ["lead"] * 3
             + ["mobile", "frontend", "data", "data_engineer", "gamedev"]
             + ["pm"] * 4 + ["analyst"] + ["designer"] * 2 + ["founder"] * 5)
    tech = ["backend", "fullstack", "ml", "mobile", "frontend", "lead"]
    out = []
    for role in roles:
        p = base("find_cofounder", role, rng.randint(2, 12))
        if ROLES[role]["group"] == "tech":
            p["seeking_roles"] = rng.sample(["pm", "founder", "designer"], rng.randint(1, 2))
        elif role == "designer":
            p["seeking_roles"] = rng.sample(["backend", "fullstack", "frontend", "founder"], 2)
        else:
            p["seeking_roles"] = rng.sample(tech, rng.randint(1, 2))
        out.append(finish(p))
    return out


def gen_exchange() -> list[dict]:
    out = []
    for role in covered_roles(COUNTS["exchange"] - 6) + ["lead"] * 4 + ["founder"] * 2:
        p = base("exchange", role, rng.randint(2, 12), rng.choice(list(COMPANIES)))
        out.append(finish(p))
    return out


BOOTHS = [
    {"id": "b1", "name": "Nomad Pay",
     "desc": {"ru": "Платёжная платформа: показывают, как устроен процессинг карт",
              "kk": "Төлем платформасы: карталар процессингі қалай жұмыс істейтінін көрсетеді",
              "en": "Payments platform: a look inside card processing"},
     "interests": ["fintech", "security", "cloud"], "stack": ["java", "kafka", "kubernetes", "postgresql"],
     "hiring": ["backend", "devops", "qa", "analyst"]},
    {"id": "b2", "name": "Kok Tobe AI",
     "desc": {"ru": "Лаборатория ИИ: демо LLM-ассистентов на казахском языке",
              "kk": "ЖИ зертханасы: қазақ тіліндегі LLM-ассистенттердің демосы",
              "en": "AI lab: demos of Kazakh-language LLM assistants"},
     "interests": ["ai", "data_science", "opensource"], "stack": ["python", "pytorch", "llm", "nlp"],
     "hiring": ["ml", "data", "data_engineer"]},
    {"id": "b3", "name": "Zhetisu Games",
     "desc": {"ru": "Игровая студия: можно поиграть в прототипы",
              "kk": "Ойын студиясы: прототиптерді ойнап көруге болады",
              "en": "Game studio: play their prototypes"},
     "interests": ["gamedev", "ux"], "stack": ["unity", "unreal", "csharp", "cpp", "figma"],
     "hiring": ["gamedev", "mobile", "designer"]},
    {"id": "b4", "name": "Turan EdTech",
     "desc": {"ru": "Онлайн-образование: ищут менторов и авторов курсов",
              "kk": "Онлайн білім беру: тәлімгерлер мен курс авторларын іздейді",
              "en": "Online education: looking for mentors and course authors"},
     "interests": ["edtech", "mentorship", "career"], "stack": ["typescript", "react", "python"],
     "hiring": ["frontend", "pm"]},
    {"id": "b5", "name": "Aral Cloud",
     "desc": {"ru": "Облачный провайдер: бесплатные кредиты для стартапов",
              "kk": "Бұлтты провайдер: стартаптарға тегін кредиттер",
              "en": "Cloud provider: free credits for startups"},
     "interests": ["cloud", "startups", "security"], "stack": ["kubernetes", "terraform", "linux", "docker"],
     "hiring": ["devops", "backend"]},
    {"id": "b6", "name": "Kaspian Commerce",
     "desc": {"ru": "Маркетплейс: рассказывают про рекомендации и A/B-тесты",
              "kk": "Маркетплейс: ұсыныстар мен A/B тесттер туралы айтады",
              "en": "Marketplace: talks on recommendations and A/B tests"},
     "interests": ["ecommerce", "product", "data_science"],
     "stack": ["product_analytics", "sql", "react", "kotlin", "swift"], "hiring": ["data", "mobile", "pm"]},
    {"id": "b7", "name": "Astra Security",
     "desc": {"ru": "Кибербезопасность: мини-CTF прямо на стенде",
              "kk": "Киберқауіпсіздік: стендте шағын CTF жарысы",
              "en": "Cybersecurity: a mini CTF right at the booth"},
     "interests": ["security", "opensource"], "stack": ["linux", "python", "go", "siem", "owasp", "burp"],
     "hiring": ["security", "backend", "qa"]},
    {"id": "b8", "name": "Steppe Labs",
     "desc": {"ru": "Акселератор: помогают найти кофаундера и первых инвесторов",
              "kk": "Акселератор: кофаундер мен алғашқы инвесторларды табуға көмектеседі",
              "en": "Accelerator: helps find co-founders and first investors"},
     "interests": ["startups", "product", "fintech", "agritech"], "stack": ["product_analytics"],
     "hiring": []},
]


def gen_niche_topup(profiles: list[dict]) -> list[dict]:
    """Добор по итогам разбора ошибок шага 4: в каждой специализации минимум 3 ищущих ментора
    и 3 ментора (раньше ментору по кибербезопасности хватало только 2 подопечных).
    Анкеты добавляются в конец, поэтому id прежних анкет и ручная разметка не сдвигаются."""
    out: list[dict] = []
    for goal, exps in (("find_mentor", [0, 1, 1, 2, 3]), ("be_mentor", list(range(6, 16)))):
        for role in SPECIALIST_ROLES:
            have = sum(p["goal"] == goal and p["role"] == role for p in profiles + out)
            for _ in range(3 - have):
                company = rng.choice(list(COMPANIES)) if goal == "be_mentor" else None
                out.append(finish(base(goal, role, rng.choice(exps), company)))
    return out


def main() -> None:
    profiles = (gen_find_job() + gen_hire() + gen_find_mentor() + gen_be_mentor()
                + gen_cofounder() + gen_exchange())
    rng.shuffle(profiles)
    profiles += gen_niche_topup(profiles)  # в конец: прежние id не меняются
    for i, p in enumerate(profiles, 1):
        p["id"] = f"p{i:03d}"

    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    (data / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
    (data / "booths.json").write_text(json.dumps(BOOTHS, ensure_ascii=False, indent=1), encoding="utf-8")

    fields = list(profiles[0].keys())
    with open(data / "profiles.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for p in profiles:
            w.writerow({k: ";".join(v) if isinstance(v, list) else ("" if v is None else v)
                        for k, v in p.items()})
    print(f"Готово: {len(profiles)} анкет -> data/profiles.json, data/profiles.csv")


if __name__ == "__main__":
    main()

"""Справочники Wingman: цели, роли, стек, интересы, слоты и их переводы.

Все поля анкеты хранятся как внутренние коды (например, "python", "fintech"),
поэтому язык анкеты не мешает подбору: казахская, русская и английская анкеты
сравниваются по одним и тем же кодам.
"""
from __future__ import annotations

import re
from collections import Counter

LANGS = ("ru", "kk", "en")

# ---------------------------------------------------------------- цели
GOALS = {
    "find_job": {"ru": "Найти работу", "kk": "Жұмыс табу", "en": "Find a job"},
    "hire": {"ru": "Нанять", "kk": "Маман жалдау", "en": "Hire"},
    "find_mentor": {"ru": "Найти ментора", "kk": "Тәлімгер табу", "en": "Find a mentor"},
    "be_mentor": {"ru": "Стать ментором", "kk": "Тәлімгер болу", "en": "Become a mentor"},
    "find_cofounder": {"ru": "Найти кофаундера", "kk": "Кофаундер табу", "en": "Find a co-founder"},
    "exchange": {"ru": "Обмен опытом", "kk": "Тәжірибе алмасу", "en": "Share experience"},
}

# Взаимность: цель участника -> цели, которые ей отвечают.
# Это жёсткий фильтр: ищущему работу никогда не покажем другого соискателя.
GOAL_MATCH = {
    "find_job": {"hire"},
    "hire": {"find_job"},
    "find_mentor": {"be_mentor"},
    "be_mentor": {"find_mentor"},
    "find_cofounder": {"find_cofounder"},
    "exchange": {"exchange"},
}

# ---------------------------------------------------------------- роли
ROLES = {
    "backend": {"ru": "Backend-разработчик", "kk": "Backend-әзірлеуші", "en": "Backend developer",
                "en_a": "a backend developer", "group": "tech"},
    "frontend": {"ru": "Frontend-разработчик", "kk": "Frontend-әзірлеуші", "en": "Frontend developer",
                 "en_a": "a frontend developer", "group": "tech"},
    "fullstack": {"ru": "Fullstack-разработчик", "kk": "Fullstack-әзірлеуші", "en": "Fullstack developer",
                  "en_a": "a fullstack developer", "group": "tech"},
    "mobile": {"ru": "Мобильный разработчик", "kk": "Мобильді әзірлеуші", "en": "Mobile developer",
               "en_a": "a mobile developer", "group": "tech"},
    "gamedev": {"ru": "Разработчик игр", "kk": "Ойын әзірлеушісі", "en": "Game developer",
                "en_a": "a game developer", "group": "tech"},
    "ml": {"ru": "ML-инженер", "kk": "ML-инженер", "en": "ML engineer",
           "en_a": "an ML engineer", "group": "tech"},
    "data": {"ru": "Аналитик данных", "kk": "Деректер талдаушысы", "en": "Data analyst",
             "en_a": "a data analyst", "group": "tech"},
    "data_engineer": {"ru": "Data-инженер", "kk": "Деректер инженері", "en": "Data engineer",
                      "en_a": "a data engineer", "group": "tech"},
    "devops": {"ru": "DevOps-инженер", "kk": "DevOps-инженер", "en": "DevOps engineer",
               "en_a": "a DevOps engineer", "group": "tech"},
    "security": {"ru": "Специалист по кибербезопасности", "kk": "Киберқауіпсіздік маманы",
                 "en": "Security engineer", "en_a": "a security engineer", "group": "tech"},
    "qa": {"ru": "QA-инженер", "kk": "QA-инженер", "en": "QA engineer",
           "en_a": "a QA engineer", "group": "tech"},
    "pm": {"ru": "Продакт-менеджер", "kk": "Өнім менеджері", "en": "Product manager",
           "en_a": "a product manager", "group": "product"},
    "analyst": {"ru": "Бизнес-аналитик", "kk": "Бизнес-талдаушы", "en": "Business analyst",
                "en_a": "a business analyst", "group": "product"},
    "designer": {"ru": "UX/UI-дизайнер", "kk": "UX/UI дизайнер", "en": "UX/UI designer",
                 "en_a": "a UX/UI designer", "group": "product"},
    "lead": {"ru": "Тимлид / CTO", "kk": "Тимлид / CTO", "en": "Team lead / CTO",
             "en_a": "a team lead / CTO", "group": "tech"},
    "recruiter": {"ru": "IT-рекрутер", "kk": "IT-рекрутер", "en": "IT recruiter",
                  "en_a": "an IT recruiter", "group": "business"},
    "founder": {"ru": "Фаундер", "kk": "Фаундер", "en": "Founder",
                "en_a": "a founder", "group": "business"},
    "student": {"ru": "Студент", "kk": "Студент", "en": "Student",
                "en_a": "a student", "group": "other"},
}

# Роли без одной специализации: её определяем по стеку. Тимлид/CTO — руководитель,
# у него есть и своя роль (его можно нанять), и специализация из стека.
NON_SPECIALIST_ROLES = {"recruiter", "founder", "student", "lead"}
SPECIALIST_ROLES = [r for r in ROLES if r not in NON_SPECIALIST_ROLES]
HIREABLE_ROLES = SPECIALIST_ROLES + ["lead"]

# Близкие роли: опыт одной частично подходит другой.
RELATED = {
    "backend": {"fullstack", "devops", "data", "data_engineer"},
    "frontend": {"fullstack", "mobile", "designer"},
    "fullstack": {"backend", "frontend"},
    "mobile": {"frontend", "gamedev"},
    "gamedev": {"mobile", "frontend", "backend"},
    "ml": {"data", "backend", "data_engineer"},
    "data": {"ml", "backend", "pm", "data_engineer", "analyst"},
    "data_engineer": {"data", "backend", "ml", "devops"},
    "devops": {"backend", "security"},
    "security": {"devops", "backend", "qa"},
    "qa": {"backend", "frontend", "analyst"},
    "pm": {"designer", "founder", "data", "analyst"},
    "analyst": {"pm", "data", "qa"},
    "designer": {"frontend", "pm"},
    # Продакт — партнёр тимлида, а не замена ему (разбор ошибок шага 4: фаундеру, ищущему CTO,
    # предлагался продакт).
    "lead": {"backend", "frontend", "fullstack", "mobile", "ml", "devops", "data_engineer"},
    "founder": {"pm", "lead"},
    "recruiter": set(),
    "student": set(),
}


def role_similarity(a: str, b: str) -> float:
    """1 — та же роль, 0.6 — близкая, 0.15 — другая."""
    if a == b:
        return 1.0
    if b in RELATED.get(a, set()) or a in RELATED.get(b, set()):
        return 0.6
    return 0.15


# ---------------------------------------------------------------- стек
# код -> (название, семейства)
STACK = {
    "python": ("Python", {"backend", "ml", "data"}),
    "django": ("Django", {"backend"}),
    "fastapi": ("FastAPI", {"backend"}),
    "java": ("Java", {"backend"}),
    "spring": ("Spring", {"backend"}),
    "go": ("Go", {"backend"}),
    "nodejs": ("Node.js", {"backend", "frontend"}),
    "csharp": ("C#", {"backend"}),
    "dotnet": (".NET", {"backend"}),
    "php": ("PHP", {"backend"}),
    "laravel": ("Laravel", {"backend"}),
    "onec": ("1C", {"backend"}),
    "javascript": ("JavaScript", {"frontend"}),
    "typescript": ("TypeScript", {"frontend"}),
    "react": ("React", {"frontend"}),
    "vue": ("Vue", {"frontend"}),
    "angular": ("Angular", {"frontend"}),
    "nextjs": ("Next.js", {"frontend"}),
    "html_css": ("HTML/CSS", {"frontend", "design"}),
    "kotlin": ("Kotlin", {"mobile"}),
    "swift": ("Swift", {"mobile"}),
    "flutter": ("Flutter", {"mobile"}),
    "react_native": ("React Native", {"mobile", "frontend"}),
    "sql": ("SQL", {"data", "backend"}),
    "postgresql": ("PostgreSQL", {"backend", "data"}),
    "mongodb": ("MongoDB", {"backend"}),
    "redis": ("Redis", {"backend"}),
    "kafka": ("Kafka", {"backend", "data"}),
    "docker": ("Docker", {"devops", "backend"}),
    "kubernetes": ("Kubernetes", {"devops"}),
    "aws": ("AWS", {"devops"}),
    "gcp": ("GCP", {"devops"}),
    "terraform": ("Terraform", {"devops"}),
    "linux": ("Linux", {"devops"}),
    "ci_cd": ("CI/CD", {"devops", "qa"}),
    "pytorch": ("PyTorch", {"ml"}),
    "tensorflow": ("TensorFlow", {"ml"}),
    "sklearn": ("scikit-learn", {"ml"}),
    "llm": ("LLM", {"ml"}),
    "cv": ("Computer Vision", {"ml"}),
    "nlp": ("NLP", {"ml"}),
    "pandas": ("pandas", {"data", "ml"}),
    "spark": ("Spark", {"data"}),
    "airflow": ("Airflow", {"data"}),
    "powerbi": ("Power BI", {"data"}),
    "tableau": ("Tableau", {"data"}),
    "excel": ("Excel", {"data", "management"}),
    "figma": ("Figma", {"design"}),
    "user_research": ("User Research", {"design", "management"}),
    "selenium": ("Selenium", {"qa"}),
    "playwright": ("Playwright", {"qa"}),
    "postman": ("Postman", {"qa", "backend"}),
    "jira": ("Jira", {"management"}),
    "product_analytics": ("Product Analytics", {"management", "data"}),
    "unity": ("Unity", {"gamedev"}),
    "unreal": ("Unreal Engine", {"gamedev"}),
    "godot": ("Godot", {"gamedev"}),
    "cpp": ("C++", {"backend", "gamedev"}),
    "rust": ("Rust", {"backend"}),
    "ruby": ("Ruby", {"backend"}),
    "clickhouse": ("ClickHouse", {"data"}),
    "dbt": ("dbt", {"data"}),
    "azure": ("Azure", {"devops"}),
    "ansible": ("Ansible", {"devops"}),
    "grafana": ("Grafana", {"devops"}),
    "siem": ("SIEM", {"security"}),
    "owasp": ("OWASP", {"security"}),
    "burp": ("Burp Suite", {"security"}),
    "bpmn": ("BPMN", {"analysis"}),
    "uml": ("UML", {"analysis"}),
}

# Какую роль обычно выдаёт инструмент: нужно, чтобы понять, кого ищет
# рекрутер, указавший только стек вакансии.
STACK_ROLES = {
    "python": ("backend", "ml"), "django": ("backend",), "fastapi": ("backend",),
    "java": ("backend",), "spring": ("backend",), "go": ("backend",),
    "nodejs": ("backend", "fullstack"), "csharp": ("backend",), "dotnet": ("backend",),
    "php": ("backend",), "laravel": ("backend",), "onec": ("backend",),
    "javascript": ("frontend",), "typescript": ("frontend",), "react": ("frontend",),
    "vue": ("frontend",), "angular": ("frontend",), "nextjs": ("frontend",),
    "html_css": ("frontend",),
    "kotlin": ("mobile",), "swift": ("mobile",), "flutter": ("mobile",),
    "react_native": ("mobile",),
    "sql": ("data",), "pandas": ("data", "ml"), "spark": ("data_engineer", "data"),
    "airflow": ("data_engineer",), "kafka": ("backend", "data_engineer"),
    "clickhouse": ("data_engineer",), "dbt": ("data_engineer",),
    "powerbi": ("data",), "tableau": ("data",), "excel": ("data",),
    "unity": ("gamedev",), "unreal": ("gamedev",), "godot": ("gamedev",), "cpp": ("backend", "gamedev"),
    "rust": ("backend",), "ruby": ("backend",),
    "azure": ("devops",), "ansible": ("devops",), "grafana": ("devops",),
    "siem": ("security",), "owasp": ("security",), "burp": ("security",),
    "bpmn": ("analyst",), "uml": ("analyst",),
    "pytorch": ("ml",), "tensorflow": ("ml",), "sklearn": ("ml",), "llm": ("ml",),
    "cv": ("ml",), "nlp": ("ml",),
    "docker": ("devops",), "kubernetes": ("devops",), "aws": ("devops",),
    "gcp": ("devops",), "terraform": ("devops",), "linux": ("devops",), "ci_cd": ("devops",),
    "selenium": ("qa",), "playwright": ("qa",), "postman": ("qa",),
    "figma": ("designer",), "user_research": ("designer",),
    "jira": ("pm",), "product_analytics": ("pm",),
}

# ---------------------------------------------------------------- интересы
INTERESTS = {
    "ai": {"ru": "Искусственный интеллект", "kk": "Жасанды интеллект", "en": "AI"},
    "fintech": {"ru": "Финтех", "kk": "Финтех", "en": "Fintech"},
    "edtech": {"ru": "EdTech", "kk": "EdTech", "en": "EdTech"},
    "ecommerce": {"ru": "E-commerce", "kk": "E-commerce", "en": "E-commerce"},
    "gamedev": {"ru": "Геймдев", "kk": "Геймдев", "en": "Game dev"},
    "govtech": {"ru": "GovTech", "kk": "GovTech", "en": "GovTech"},
    "healthtech": {"ru": "Медтех", "kk": "Медтех", "en": "HealthTech"},
    "logistics": {"ru": "Логистика", "kk": "Логистика", "en": "Logistics"},
    "agritech": {"ru": "Агротех", "kk": "Агротех", "en": "AgriTech"},
    "blockchain": {"ru": "Блокчейн", "kk": "Блокчейн", "en": "Blockchain"},
    "security": {"ru": "Кибербезопасность", "kk": "Киберқауіпсіздік", "en": "Cybersecurity"},
    "cloud": {"ru": "Облачные технологии", "kk": "Бұлтты технологиялар", "en": "Cloud"},
    "data_science": {"ru": "Data Science", "kk": "Data Science", "en": "Data Science"},
    "opensource": {"ru": "Open source", "kk": "Open source", "en": "Open source"},
    "iot": {"ru": "IoT и железо", "kk": "IoT және құрылғылар", "en": "IoT & hardware"},
    "product": {"ru": "Продуктовый подход", "kk": "Өнімдік тәсіл", "en": "Product thinking"},
    "ux": {"ru": "UX-исследования", "kk": "UX зерттеулер", "en": "UX research"},
    "startups": {"ru": "Стартапы", "kk": "Стартаптар", "en": "Startups"},
    "career": {"ru": "Карьера в IT", "kk": "IT-дағы мансап", "en": "IT careers"},
    "mentorship": {"ru": "Менторство", "kk": "Тәлімгерлік", "en": "Mentorship"},
    "community": {"ru": "IT-сообщества", "kk": "IT-қауымдастықтар", "en": "Tech communities"},
    "remote": {"ru": "Удалённая работа", "kk": "Қашықтан жұмыс", "en": "Remote work"},
}
# Интересы, которые почти у всех и мало что говорят о паре: в объяснениях — в конце.
LOW_INFO_INTERESTS = {"career", "mentorship", "startups", "community", "remote"}

# ---------------------------------------------------------------- уровни и слоты
LEVELS = {"junior": (0, 2), "middle": (2, 5), "senior": (5, 15)}
LEVEL_ALIASES = {
    "junior": re.compile(r"junior|джун|начинающ|стажёр|стажер|intern", re.IGNORECASE),
    "middle": re.compile(r"middle|мидл|миддл", re.IGNORECASE),
    "senior": re.compile(r"senior|сеньор|синьор|сениор", re.IGNORECASE),
}


def levels_in_text(text: str) -> list[str]:
    return [lvl for lvl, rx in LEVEL_ALIASES.items() if rx.search(text or "")]
EVENT_SLOTS = ["11:00", "11:30", "12:00", "13:30", "14:00", "14:30",
               "15:00", "15:30", "16:00", "16:30"]

# ---------------------------------------------------------------- распознавание текста
# Слова из «о себе» на трёх языках -> коды. Так учитываем то, что человек
# написал текстом, а не выбрал в списке (например, рекрутер: «ищем React-разработчика»).
_ALIASES = {
    "stack": {
        "python": r"\bpython\b|питон|пайтон",
        "django": r"django|джанго",
        "fastapi": r"fastapi",
        "java": r"\bjava\b|джава\b",
        "spring": r"\bspring\b",
        "go": r"\bgolang\b|\bgo[- ]?(?:developer|разработ|әзірле)|\bна go\b",
        "nodejs": r"node\.?js|\bnode\b",
        "csharp": r"c#|си шарп",
        "dotnet": r"\.net\b|дотнет",
        "php": r"\bphp\b",
        "laravel": r"laravel",
        "onec": r"\b1[сc]\b",
        "javascript": r"javascript|\bjs\b",
        "typescript": r"typescript|\bts\b",
        "react": r"\breact\b(?!\s*native)|реакт",
        "vue": r"\bvue|\bвью\b",
        "angular": r"angular|ангуляр",
        "nextjs": r"next\.?js",
        "html_css": r"\bhtml|\bcss|вёрстк|верстк",
        "kotlin": r"kotlin|котлин",
        "swift": r"\bswift\b|\bios\b",
        "flutter": r"flutter|флаттер",
        "react_native": r"react\s*native",
        "sql": r"\bsql\b",
        "postgresql": r"postgres|постгр",
        "mongodb": r"mongo",
        "redis": r"redis",
        "kafka": r"kafka|кафк",
        "docker": r"docker|докер",
        "kubernetes": r"kubernetes|\bk8s\b|кубер",
        "aws": r"\baws\b",
        "gcp": r"\bgcp\b|google cloud",
        "terraform": r"terraform",
        "linux": r"linux|линукс",
        "ci_cd": r"ci/cd|github actions|gitlab ci",
        "pytorch": r"pytorch|\btorch\b",
        "tensorflow": r"tensorflow|keras",
        "sklearn": r"scikit|sklearn",
        "llm": r"\bllm|\bgpt|chatgpt|\brag\b|нейросет|языков\w* модел",
        "cv": r"computer vision|компьютерн\w* зрени|компьютерлік көру",
        "nlp": r"\bnlp\b|обработк\w* (?:естественного )?языка",
        "pandas": r"pandas",
        "spark": r"\bspark\b",
        "airflow": r"airflow",
        "powerbi": r"power\s?bi",
        "tableau": r"tableau",
        "excel": r"excel|эксель",
        "figma": r"figma|фигм",
        "user_research": r"user research|custdev|кастдев|исследовани\w* пользовател",
        "selenium": r"selenium",
        "playwright": r"playwright",
        "postman": r"postman",
        "jira": r"jira|джир",
        "product_analytics": r"продуктов\w* аналитик|product analytics|a/b|\bab[- ]тест",
        "unity": r"unity|юнити",
        "unreal": r"unreal|анриал",
        "godot": r"godot|годот",
        "cpp": r"c\+\+|\bcpp\b|си плюс плюс",
        "rust": r"\brust\b|\bраст\b",
        "ruby": r"\bruby\b|\brails\b|руби\b",
        "clickhouse": r"clickhouse|кликхаус",
        "dbt": r"\bdbt\b",
        "azure": r"azure|ажур",
        "ansible": r"ansible|ансибл",
        "grafana": r"grafana|prometheus|графан|прометеус",
        "siem": r"\bsiem\b|\bsoc\b|\bsplunk\b",
        "owasp": r"owasp",
        "burp": r"\bburp\b|пентест|pentest|пен-тест",
        "bpmn": r"\bbpmn\b",
        "uml": r"\buml\b",
    },
    "interests": {
        "ai": r"искусственн\w* интеллект|\bai\b|\bии\b|жасанды интеллект|machine learning|машинн\w* обучени"
              r"|машиналық оқыту|нейросет|нейрожелі",
        "fintech": r"финтех|fintech|банк|платеж|платёж|төлем|payments|қаржы",
        "edtech": r"edtech|образован|білім беру|обучени|школ|университет|оқыту платформ",
        "ecommerce": r"e-?commerce|маркетплейс|интернет-магазин|ритейл|retail|онлайн-сауда|сауда",
        "gamedev": r"геймдев|gamedev|game ?dev|\bигр|ойын",
        "govtech": r"govtech|госуслуг|госсектор|мемлекеттік|egov|акимат|әкімдік",
        "healthtech": r"медтех|healthtech|медицин|денсаулық|клиник",
        "logistics": r"логистик|logistics|доставк|жеткізу",
        "agritech": r"агротех|agritech|\bагро|сельск|ауыл шаруашылығ",
        "blockchain": r"блокчейн|blockchain|web3|крипт|crypto",
        "security": r"безопасност|security|киберқауіпсіз|пентест|pentest",
        "cloud": r"облак|облачн|\bcloud|бұлт",
        "data_science": r"data science|дата сайенс|анализ данных|деректерді талдау|деректер ғылымы",
        "opensource": r"open[- ]?source|опенсорс|опен сорс",
        "iot": r"\biot\b|интернет вещей|заттар интернеті|железо|hardware|arduino|embedded",
        "product": r"продуктов|product|өнімдік|өнім жаса",
        "ux": r"\bux\b|юзабилити|usability",
        "startups": r"стартап|startup",
        "career": r"карьер|мансап|career",
        "mentorship": r"ментор|тәлімгер|mentor",
        "community": r"сообществ|community|қауымдастық|митап|meetup",
        "remote": r"удалён|удален|remote|қашықтан",
    },
    "roles": {
        "backend": r"backend|бэкенд|бекенд|бэк-?енд|серверн",
        "frontend": r"frontend|фронтенд|фронт-?енд|\bфронт",
        "fullstack": r"full-?stack|фулл?стек",
        "mobile": r"\bmobile|мобильн|мобильді|android|андроид|\bios\b",
        "gamedev": r"game ?dev|game developer|геймдев|разработчик\w* игр|ойын әзірле",
        "ml": r"\bml\b|machine learning|data scientist|дата сайентист|ml-инженер|машиналық оқыту",
        "data": r"аналитик\w* данных|data analyst|bi-аналитик|деректер талдау",
        "data_engineer": r"data[- ]?engineer|дата[- ]инженер|data-инженер|инженер\w* данных|деректер инженер",
        "devops": r"devops|девопс|\bsre\b",
        "security": r"security|кибербезопасн|информационн\w* безопасн|\bиб\b|пентест|pentest|\bsoc\b"
                    r"|киберқауіпсіз|ақпараттық қауіпсіз",
        "qa": r"\bqa\b|тестировщик|тестирован|тестілеу",
        "pm": r"product manager|продакт|продукт-менеджер|менеджер продукт|өнім менеджер",
        "analyst": r"системн\w* аналитик|бизнес[- ]аналитик|business analyst|system analyst"
                   r"|жүйелік талдау|бизнес[- ]талдау",
        "designer": r"дизайнер|designer|ux/ui|ui/ux",
        "lead": r"тимлид|техлид|team ?lead|tech ?lead|\bcto\b|техническ\w* директор|техникалық директор"
                r"|руководител\w* разработ",
        # «кофаундер» сам по себе не роль: ищем «фаундер» отдельным словом и «бизнес-кофаундер»
        "founder": r"\bфаундер|(?<![-\w])founder|бизнес[- ]кофаундер|бизнес[- ]партн|business co-?founder"
                   r"|основател|құрылтайшы",
    },
}
ALIASES = {kind: {code: re.compile(p, re.IGNORECASE) for code, p in table.items()}
           for kind, table in _ALIASES.items()}


def extract_tags(text: str) -> dict[str, set[str]]:
    """Находит в свободном тексте стек, интересы и упомянутые роли."""
    text = (text or "").lower()
    return {kind: {code for code, rx in table.items() if rx.search(text)}
            for kind, table in ALIASES.items()}


def roles_from_stack(stack) -> list[str]:
    """Роли, на которые указывает стек, от самой вероятной."""
    counts = Counter(r for tag in stack for r in STACK_ROLES.get(tag, ()))
    return [r for r, _ in counts.most_common()]


def effective_roles(role: str, stack) -> set[str]:
    """Специализация человека. У студента, фаундера и рекрутера берём её из стека;
    у тимлида — и саму роль «тимлид», и специализацию из стека."""
    if role not in NON_SPECIALIST_ROLES:
        return {role}
    from_stack = set(roles_from_stack(stack)[:2])
    return from_stack | {"lead"} if role == "lead" else from_stack


# ---------------------------------------------------------------- подписи
def role_label(code: str, lang: str) -> str:
    return ROLES.get(code, {}).get(lang, code)


def goal_label(code: str, lang: str) -> str:
    return GOALS.get(code, {}).get(lang, code)


def interest_label(code: str, lang: str) -> str:
    return INTERESTS.get(code, {}).get(lang, code)


def stack_label(code: str) -> str:
    return STACK.get(code, (code, set()))[0]


def years_ru(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} год"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} года"
    return f"{n} лет"


def exp_phrase(n: int, lang: str) -> str:
    """«с опытом 4 года» / «4 жыл тәжірибесі бар» / «with 4 years of experience»."""
    if lang == "ru":
        return "без коммерческого опыта" if n <= 0 else f"с опытом {years_ru(n)}"
    if lang == "kk":
        return "коммерциялық тәжірибесі жоқ" if n <= 0 else f"{n} жыл тәжірибесі бар"
    if n <= 0:
        return "with no commercial experience"
    return f"with {n} year{'s' if n != 1 else ''} of experience"

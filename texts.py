"""Тексты интерфейса и шаблоны объяснений на казахском, русском и английском."""
from __future__ import annotations

LANG_NAMES = {"kk": "Қазақша", "ru": "Русский", "en": "English"}

UI = {
    "ru": {
        "tagline": "Пять человек в зале, которым вы нужны так же, как они вам",
        "goal_q": "Что вы ищете на мероприятии?",
        "more": "Дополнительно: имя, кого ищете, свободное время",
        "data_note": "База: {n} синтетических анкет. Имена и компании вымышлены.",
        "choose": "Выберите",
        "guest": "Участник",
        "navigation": "Раздел приложения",
        "loading": "Ищем людей с подходящей целью…",
        "match_error": "Не удалось подобрать участников. Ваша анкета сохранена в этой вкладке.",
        "retry": "Повторить подбор",
        "hall_consent": "Добавьте анкету в зал, чтобы другие участники могли найти вас в рекомендациях.",
        "hall_join": "Добавить меня в зал",
        "hall_joined": "Вы в зале. Другие участники могут увидеть анкету, с которой вы присоединились.",
        "hall_error": "Не удалось добавить анкету. Попробуйте позже.",
        "hall_count": "Участников в живом зале",
        "hall_clear": "Очистить живой зал",
        "hall_code": "Код организатора",
        "hall_bad_code": "Проверьте код организатора.",
        "hall_clear_note": "Будут удалены все анкеты, которые участники добавили в зал.",
        "hall_cleared": "Живой зал очищен.",
        "hall_clear_error": "Не удалось очистить живой зал. Повторите попытку.",
        "ex_find_job": "Соискатель", "ex_hire": "Рекрутер", "ex_find_mentor": "Студент",
        "no_exp": "без опыта",
        "nav_match": "Подбор знакомств",
        "nav_dash": "Дашборд организатора",
        "form_title": "Ваша анкета",
        "examples": "Попробовать на примере",
        "name": "Имя (необязательно)",
        "role": "Роль",
        "experience": "Опыт, лет",
        "stack": "Стек",
        "stack_help": "Для цели «Нанять» — стек вакансии",
        "interests": "Интересы",
        "about": "О себе",
        "about_ph": "Пара предложений: чем занимаетесь и что ищете. "
                    "Можно на казахском, русском или английском.",
        "goal": "Цель на мероприятии",
        "seeking": "Кого ищете (для «Нанять» и «Найти кофаундера»)",
        "slots": "Когда свободны — для расписания встреч",
        "submit": "Показать 5 человек",
        "need_more": "Укажите стек или напишите пару слов о себе — так подбор будет точнее.",
        "results_title": "С кем познакомиться",
        "results_empty": "Выберите цель и заполните анкету — здесь появятся 5 человек "
                         "и объяснение, почему стоит подойти к каждому.",
        "found_in": "Подобрано за {ms} мс, участников в базе: {n}",
        "inferred": "Из текста «о себе» также учли: {tags}",
        "match": "совпадение",
        "icebreaker": "Первая фраза",
        "slot": "Оба свободны: {slots}",
        "no_slot": "Нет общего свободного времени",
        "met": "Познакомились",
        "not_fit": "Не подошло",
        "toast_met": "Отлично! Подобрали следующего человека.",
        "toast_not_fit": "Учли отзыв и пересчитали рекомендации.",
        "met_list": "Уже познакомились: {names}",
        "reset": "Сбросить отзывы",
        "no_more": "Подходящих людей больше нет — попробуйте изменить анкету.",
        "schedule_title": "Расписание встреч 1:1",
        "schedule_none": "Отметьте свободное время в разделе «Дополнительно» — составим расписание встреч.",
        "col_time": "Время",
        "col_with": "С кем",
        "col_why": "Зачем",
        "schedule_left": "Без общего времени: {names} — договоритесь лично.",
        "booths_title": "Стенды партнёров для вас",
        "booth_hiring": "Нанимают: {roles}",
        "how_title": "Как работает подбор",
        "how_text": (
            "1. **Взаимность целей.** Оставляем только тех, чья цель отвечает вашей: "
            "ищущему работу — нанимающих, ищущему ментора — менторов опытнее вас.\n"
            "2. **Оценка.** Каждого оцениваем по роли (34%), стеку (28%), опыту (17%), "
            "тексту «о себе» (11%) и интересам (10%). Текст понимаем на трёх языках. "
            "Веса подобраны по ручной разметке: точность 98% на тестовых анкетах.\n"
            "3. **Разнообразие.** Из лучших выбираем 5 так, чтобы список не состоял из одной компании.\n"
            "4. **Объяснение.** Пишем, почему именно этот человек, и предлагаем первую фразу.\n"
            "5. **Обратная связь.** «Не подошло» убирает человека и понижает похожих, "
            "«Познакомились» — показывает следующего."
        ),
        # дашборд
        "dash_people": "Участников",
        "dash_feedback": "Отзывов о знакомствах",
        "dash_met_rate": "Доля «познакомились»",
        "dash_balance": "Спрос и предложение по целям",
        "dash_map": "Карта интересов зала: роли × интересы",
        "dash_stack": "Популярный стек",
        "dash_tips": "Подсказки организатору",
        "dash_count": "Человек",
        "dash_feedback_none": "Отзывов пока нет: они появятся, когда участники нажмут "
                              "«Познакомились» или «Не подошло».",
        "tip_jobs": "Соискателей в {x} раза больше, чем нанимающих. "
                    "Пригласите больше компаний с вакансиями.",
        "tip_jobs_rev": "Нанимающих больше, чем соискателей: стоит позвать студентов и джунов.",
        "tip_mentors": "На одного ментора приходится {x} ищущих ментора. "
                       "Позовите опытных специалистов в менторы.",
        "tip_topic": "Самая популярная тема в зале — «{topic}». Хорошая идея для круглого стола.",
        "tip_cofounder": "Кофаундера ищут {n} человек — стоит сделать отдельную зону для стартапов.",
        "pair": {"job": "Работа", "mentor": "Менторство",
                 "cofounder": "Кофаундеры", "exchange": "Обмен опытом"},
    },
    "kk": {
        "tagline": "Залдағы сізбен танысуға мүдделі бес адам",
        "goal_q": "Іс-шарада не іздейсіз?",
        "more": "Қосымша: аты, кімді іздейсіз, бос уақыт",
        "data_note": "Дерекқор: {n} синтетикалық сауалнама. Аттар мен компаниялар ойдан шығарылған.",
        "choose": "Таңдаңыз",
        "guest": "Қатысушы",
        "navigation": "Қолданба бөлімі",
        "loading": "Мақсатыңызға сай қатысушыларды іздеп жатырмыз…",
        "match_error": "Қатысушыларды іріктеу мүмкін болмады. Сауалнамаңыз осы қойындыда сақталды.",
        "retry": "Қайта іздеу",
        "hall_consent": "Басқа қатысушылар сізді ұсыныстардан таба алуы үшін сауалнамаңызды залға қосыңыз.",
        "hall_join": "Мені залға қосу",
        "hall_joined": "Сіз залдасыз. Басқа қатысушылар залға қосылған кездегі сауалнамаңызды көре алады.",
        "hall_error": "Сауалнаманы қосу мүмкін болмады. Кейінірек қайталап көріңіз.",
        "hall_count": "Залға қосылған қатысушылар",
        "hall_clear": "Залды тазарту",
        "hall_code": "Ұйымдастырушының коды",
        "hall_bad_code": "Ұйымдастырушының кодын тексеріңіз.",
        "hall_clear_note": "Қатысушылар залға қосқан барлық сауалнама жойылады.",
        "hall_cleared": "Зал тазартылды.",
        "hall_clear_error": "Залды тазарту мүмкін болмады. Қайталап көріңіз.",
        "ex_find_job": "Жұмыс іздеуші", "ex_hire": "Рекрутер", "ex_find_mentor": "Студент",
        "no_exp": "тәжірибесіз",
        "nav_match": "Таныстар іріктеу",
        "nav_dash": "Ұйымдастырушы панелі",
        "form_title": "Сіздің сауалнамаңыз",
        "examples": "Мысалмен көру",
        "name": "Аты (міндетті емес)",
        "role": "Рөл",
        "experience": "Тәжірибе, жыл",
        "stack": "Стек",
        "stack_help": "«Маман жалдау» мақсаты үшін — бос орынның стегі",
        "interests": "Қызығушылықтар",
        "about": "Өзім туралы",
        "about_ph": "Бірнеше сөйлем: немен айналысасыз және не іздейсіз. "
                    "Қазақша, орысша немесе ағылшынша жазуға болады.",
        "goal": "Іс-шарадағы мақсат",
        "seeking": "Кімді іздейсіз («Маман жалдау» және «Кофаундер табу» үшін)",
        "slots": "Бос уақытыңыз — кездесулер кестесі үшін",
        "submit": "5 адамды көрсету",
        "need_more": "Стекті көрсетіңіз немесе өзіңіз туралы бірнеше сөз жазыңыз — "
                     "сонда іріктеу дәлірек болады.",
        "results_title": "Кіммен танысу керек",
        "results_empty": "Мақсатты таңдап, сауалнаманы толтырыңыз — мұнда 5 адам және "
                         "әрқайсысымен неге танысу керегі пайда болады.",
        "found_in": "{n} қатысушы арасынан {ms} мс ішінде іріктелді",
        "inferred": "«Өзім туралы» мәтінінен мыналар да ескерілді: {tags}",
        "match": "сәйкестік",
        "icebreaker": "Алғашқы сөз",
        "slot": "Екеуіңіз де бос: {slots}",
        "no_slot": "Ортақ бос уақыт жоқ",
        "met": "Таныстық",
        "not_fit": "Сәйкес емес",
        "toast_met": "Керемет! Келесі адамды іріктедік.",
        "toast_not_fit": "Пікіріңізді ескеріп, ұсыныстарды қайта есептедік.",
        "met_list": "Танысып үлгердіңіз: {names}",
        "reset": "Пікірлерді тазалау",
        "no_more": "Басқа сәйкес адамдар жоқ — сауалнаманы өзгертіп көріңіз.",
        "schedule_title": "1:1 кездесулер кестесі",
        "schedule_none": "«Қосымша» бөлімінде бос уақытыңызды белгілеңіз — кездесулер кестесін жасаймыз.",
        "col_time": "Уақыты",
        "col_with": "Кіммен",
        "col_why": "Не үшін",
        "schedule_left": "Ортақ уақыты жоқ: {names} — жеке келісіңіз.",
        "booths_title": "Сізге арналған серіктес стендтері",
        "booth_hiring": "Маман іздейді: {roles}",
        "how_title": "Іріктеу қалай жұмыс істейді",
        "how_text": (
            "1. **Мақсаттардың өзара сәйкестігі.** Мақсаты сіздікіне сай келетіндерді ғана "
            "қалдырамыз: жұмыс іздеушіге — маман жалдайтындарды, тәлімгер іздеушіге — "
            "сізден тәжірибелі тәлімгерлерді.\n"
            "2. **Бағалау.** Әр адамды рөлі (34%), стегі (28%), тәжірибесі (17%), "
            "«өзім туралы» мәтіні (11%) және қызығушылықтары (10%) бойынша бағалаймыз. "
            "Салмақтар қолмен белгіленген деректер бойынша таңдалды: тест сауалнамаларында дәлдік 98%. "
            "Мәтінді үш тілде түсінеміз.\n"
            "3. **Әртүрлілік.** Тізім бір компаниядан тұрмайтындай етіп, үздіктердің ішінен 5 адам таңдаймыз.\n"
            "4. **Түсіндірме.** Неліктен дәл осы адам екенін жазып, алғашқы сөзді ұсынамыз.\n"
            "5. **Кері байланыс.** «Сәйкес емес» адамды алып тастап, ұқсастарын төмендетеді, "
            "«Таныстық» — келесі адамды көрсетеді."
        ),
        "dash_people": "Қатысушылар",
        "dash_feedback": "Таныстық туралы пікірлер",
        "dash_met_rate": "«Таныстық» үлесі",
        "dash_balance": "Мақсаттар бойынша сұраныс пен ұсыныс",
        "dash_map": "Зал қызығушылықтарының картасы: рөлдер × қызығушылықтар",
        "dash_stack": "Танымал стек",
        "dash_tips": "Ұйымдастырушыға кеңестер",
        "dash_count": "Адам",
        "dash_feedback_none": "Әзірге пікір жоқ: қатысушылар «Таныстық» немесе «Сәйкес емес» "
                              "батырмасын басқанда пайда болады.",
        "tip_jobs": "Жұмыс іздеушілер маман жалдайтындардан {x} есе көп. "
                    "Бос орны бар компанияларды көбірек шақырыңыз.",
        "tip_jobs_rev": "Маман жалдайтындар жұмыс іздеушілерден көп: студенттер мен "
                        "джуниорларды шақырған жөн.",
        "tip_mentors": "Бір тәлімгерге {x} тәлімгер іздеуші келеді. "
                       "Тәжірибелі мамандарды тәлімгер болуға шақырыңыз.",
        "tip_topic": "Залдағы ең танымал тақырып — «{topic}». Дөңгелек үстелге жақсы идея.",
        "tip_cofounder": "{n} адам кофаундер іздейді — стартаптарға арналған бөлек аймақ жасаған жөн.",
        "pair": {"job": "Жұмыс", "mentor": "Тәлімгерлік",
                 "cofounder": "Кофаундерлер", "exchange": "Тәжірибе алмасу"},
    },
    "en": {
        "tagline": "Five people in the room who need you as much as you need them",
        "goal_q": "What are you looking for at the event?",
        "more": "More: name, who you're looking for, free time",
        "data_note": "Database: {n} synthetic profiles. Names and companies are fictional.",
        "choose": "Choose",
        "guest": "Attendee",
        "navigation": "Navigation",
        "loading": "Finding people whose goals fit yours…",
        "match_error": "We couldn't load your matches. Your profile is saved in this tab.",
        "retry": "Try matching again",
        "hall_consent": "Add your profile to the hall so other participants can find you in their recommendations.",
        "hall_join": "Add me to the hall",
        "hall_joined": "You're in the hall. Other participants can see the profile you joined with.",
        "hall_error": "We couldn't add your profile. Please try again later.",
        "hall_count": "Live hall participants",
        "hall_clear": "Clear the live hall",
        "hall_code": "Organizer code",
        "hall_bad_code": "Check the organizer code and try again.",
        "hall_clear_note": "This removes every profile that participants have added to the hall.",
        "hall_cleared": "The live hall has been cleared.",
        "hall_clear_error": "We couldn't clear the hall. Please try again.",
        "ex_find_job": "Job seeker", "ex_hire": "Recruiter", "ex_find_mentor": "Student",
        "no_exp": "no experience",
        "nav_match": "Find people",
        "nav_dash": "Organizer dashboard",
        "form_title": "Your profile",
        "examples": "Try an example",
        "name": "Name (optional)",
        "role": "Role",
        "experience": "Experience, years",
        "stack": "Stack",
        "stack_help": "For «Hire» — the stack of your opening",
        "interests": "Interests",
        "about": "About you",
        "about_ph": "A couple of sentences: what you do and what you're looking for. "
                    "Kazakh, Russian or English.",
        "goal": "Your goal at the event",
        "seeking": "Who are you looking for (for «Hire» and «Find a co-founder»)",
        "slots": "When you're free — for the meeting schedule",
        "submit": "Show 5 people",
        "need_more": "Add your stack or a few words about yourself for better matches.",
        "results_title": "Who to meet",
        "results_empty": "Pick a goal and fill in the form — 5 people and why to meet "
                         "each of them will appear here.",
        "found_in": "Matched in {ms} ms among {n} attendees",
        "inferred": "From your 'about' text we also used: {tags}",
        "match": "match",
        "icebreaker": "Opening line",
        "slot": "Both free at: {slots}",
        "no_slot": "No shared free time",
        "met": "We met",
        "not_fit": "Not a fit",
        "toast_met": "Great! We've found the next person.",
        "toast_not_fit": "Feedback noted — recommendations updated.",
        "met_list": "Already met: {names}",
        "reset": "Reset feedback",
        "no_more": "No more suitable people — try changing your profile.",
        "schedule_title": "1:1 meeting schedule",
        "schedule_none": "Mark your free time under «More» and we'll build a meeting schedule.",
        "col_time": "Time",
        "col_with": "With",
        "col_why": "Why",
        "schedule_left": "No shared time: {names} — arrange in person.",
        "booths_title": "Partner booths for you",
        "booth_hiring": "Hiring: {roles}",
        "how_title": "How matching works",
        "how_text": (
            "1. **Mutual goals.** We keep only people whose goal answers yours: job seekers "
            "see people who are hiring, mentees see mentors more experienced than them.\n"
            "2. **Scoring.** Each person is scored on role (34%), stack (28%), experience (17%), "
            "the 'about' text (11%) and interests (10%). The text is understood in three languages. "
            "Weights were tuned on hand-labelled data: 98% precision on test profiles.\n"
            "3. **Variety.** We pick 5 of the best so the list isn't filled by one company.\n"
            "4. **Explanation.** We say why this person and suggest an opening line.\n"
            "5. **Feedback.** «Not a fit» removes the person and lowers similar ones; "
            "«We met» brings up the next one."
        ),
        "dash_people": "Attendees",
        "dash_feedback": "Meeting feedback",
        "dash_met_rate": "«We met» share",
        "dash_balance": "Supply and demand by goal",
        "dash_map": "Room interest map: roles × interests",
        "dash_stack": "Popular stack",
        "dash_tips": "Tips for the organizer",
        "dash_count": "People",
        "dash_feedback_none": "No feedback yet: it appears when attendees press "
                              "«We met» or «Not a fit».",
        "tip_jobs": "There are {x}× more job seekers than people hiring. "
                    "Invite more companies with openings.",
        "tip_jobs_rev": "More people are hiring than looking: invite students and juniors.",
        "tip_mentors": "There are {x} mentees per mentor. Invite experienced people to mentor.",
        "tip_topic": "The most popular topic in the room is «{topic}» — a good idea for a panel.",
        "tip_cofounder": "{n} people are looking for a co-founder — consider a startup corner.",
        "pair": {"job": "Jobs", "mentor": "Mentorship",
                 "cofounder": "Co-founders", "exchange": "Experience sharing"},
    },
}

# Цель кандидата глазами смотрящего: подпись под именем на карточке
GOAL_VERB = {
    "ru": {"find_job": "ищет работу", "hire": "нанимает", "find_mentor": "ищет ментора",
           "be_mentor": "готов менторить", "find_cofounder": "ищет кофаундера",
           "exchange": "делится опытом"},
    "kk": {"find_job": "жұмыс іздейді", "hire": "маман іздейді", "find_mentor": "тәлімгер іздейді",
           "be_mentor": "тәлімгер болуға дайын", "find_cofounder": "кофаундер іздейді",
           "exchange": "тәжірибе бөліседі"},
    "en": {"find_job": "looking for a job", "hire": "hiring", "find_mentor": "looking for a mentor",
           "be_mentor": "open to mentoring", "find_cofounder": "looking for a co-founder",
           "exchange": "sharing experience"},
}

# Строка о взаимности над результатами
RECIPROCITY = {
    "ru": {
        "find_job": "Показываем только тех, кто нанимает.",
        "hire": "Показываем только тех, кто ищет работу.",
        "find_mentor": "Показываем только менторов с бо́льшим опытом, чем у вас.",
        "be_mentor": "Показываем только тех, кто ищет ментора и у кого меньше опыта, чем у вас.",
        "find_cofounder": "Показываем только тех, кто тоже ищет кофаундера.",
        "exchange": "Показываем тех, кто тоже пришёл обменяться опытом.",
    },
    "kk": {
        "find_job": "Тек маман жалдайтындарды көрсетеміз.",
        "hire": "Тек жұмыс іздеп жүргендерді көрсетеміз.",
        "find_mentor": "Тек сізден тәжірибесі көп тәлімгерлерді көрсетеміз.",
        "be_mentor": "Тек тәлімгер іздеп жүрген, сізден тәжірибесі аз адамдарды көрсетеміз.",
        "find_cofounder": "Тек кофаундер іздеп жүргендерді көрсетеміз.",
        "exchange": "Тәжірибе алмасқысы келетіндерді көрсетеміз.",
    },
    "en": {
        "find_job": "Showing only people who are hiring.",
        "hire": "Showing only people looking for a job.",
        "find_mentor": "Showing only mentors with more experience than you.",
        "be_mentor": "Showing only people looking for a mentor who are less experienced than you.",
        "find_cofounder": "Showing only people also looking for a co-founder.",
        "exchange": "Showing people who are also here to share experience.",
    },
}

# ---------------------------------------------------------------- объяснения
# Первое предложение: почему этот человек отвечает вашей цели.
REASON = {
    "ru": {
        "find_job": "{company} нанимает: {roles} ({levels}){fit}.",
        "find_job_fit": {"exact": " — это как раз ваша роль", "related": " — близко к вашему опыту", "none": ""},
        "hire": "{role} {exp}, ищет работу{fit}.",
        "hire_fit": {"exact": " — подходит под вашу вакансию", "related": " — близко к вашей вакансии", "none": ""},
        "find_mentor": "{role} {exp} — на {diff} больше вашего — и хочет менторить.",
        "be_mentor": "{role} {exp}, ищет ментора{field}.",
        "be_mentor_field": " в вашей области",
        "find_cofounder": "Вы — {my_role}, {name} — {role}: роли дополняют друг друга для стартапа.",
        "find_cofounder_same": "{role} {exp}, тоже ищет кофаундера.",
        "exchange": "{role} {exp}, тоже хочет обменяться опытом.",
    },
    "kk": {
        "find_job": "{company} маман іздейді: {roles} ({levels}){fit}.",
        "find_job_fit": {"exact": " — дәл сіздің рөліңіз", "related": " — сіздің тәжірибеңізге жақын", "none": ""},
        "hire": "{role}, {exp}, жұмыс іздеп жүр{fit}.",
        "hire_fit": {"exact": " — бос орныңызға сай келеді", "related": " — бос орныңызға жақын", "none": ""},
        "find_mentor": "{role}, {exp} (сізден {diff} жыл артық), тәлімгер болуға дайын.",
        "be_mentor": "{role}, {exp}, {field}тәлімгер іздеп жүр.",
        "be_mentor_field": "сіздің салаңыздан ",
        "find_cofounder": "Сіз — {my_role}, {name} — {role}: стартап үшін рөлдеріңіз бірін-бірі толықтырады.",
        "find_cofounder_same": "{role}, {exp}, ол да кофаундер іздеп жүр.",
        "exchange": "{role}, {exp}, ол да тәжірибе алмасқысы келеді.",
    },
    "en": {
        "find_job": "{company} is hiring: {roles} ({levels}){fit}.",
        "find_job_fit": {"exact": " — exactly your role", "related": " — close to your background", "none": ""},
        "hire": "{role} {exp}, looking for a job{fit}.",
        "hire_fit": {"exact": " — fits your opening", "related": " — close to your opening", "none": ""},
        "find_mentor": "{role} {exp} ({diff} more than you), open to mentoring.",
        "be_mentor": "{role} {exp}, looking for a mentor{field}.",
        "be_mentor_field": " in your field",
        "find_cofounder": "You're {my_role_a}, {name} is {role_a}: your roles complement each other for a startup.",
        "find_cofounder_same": "{role} {exp}, also looking for a co-founder.",
        "exchange": "{role} {exp}, also here to share experience.",
    },
}

# Второе предложение: что у вас общего.
SHARED = {
    "ru": {"both": "Общий стек: {stack}; общие интересы: {interests}.",
           "stack": "Общий стек: {stack}.", "interests": "Общие интересы: {interests}.",
           "theirs": "Интересуется темой «{interest}»."},
    "kk": {"both": "Ортақ стек: {stack}; ортақ қызығушылықтар: {interests}.",
           "stack": "Ортақ стек: {stack}.", "interests": "Ортақ қызығушылықтар: {interests}.",
           "theirs": "«{interest}» тақырыбына қызығады."},
    "en": {"both": "Shared stack: {stack}; shared interests: {interests}.",
           "stack": "Shared stack: {stack}.", "interests": "Shared interests: {interests}.",
           "theirs": "Interested in {interest}."},
}

# Первая фраза для знакомства: от вас к собеседнику.
ICEBREAKER = {
    "ru": {
        "find_job": "Здравствуйте, {first}! Я {my_role}, мой основной стек — {topic}. "
                    "Расскажете, какие задачи сейчас у вашей команды?",
        "find_job_nostack": "Здравствуйте, {first}! Я {my_role} и ищу работу. "
                            "Каких специалистов вы сейчас ищете?",
        "hire": "Привет, {first}! Вижу в вашем профиле {topic} — у нас как раз открыта "
                "подходящая вакансия. Найдётся пара минут?",
        "find_mentor": "Здравствуйте, {first}! Хочу расти в направлении «{topic}». "
                       "Можно задать вам пару вопросов о вашем пути?",
        "be_mentor": "Привет, {first}! Вижу, вы ищете ментора в направлении «{topic}», "
                     "— могу поделиться опытом. Какая у вас сейчас главная задача?",
        "find_cofounder": "Привет, {first}! Я {my_role} и ищу кофаундера — кажется, наши роли "
                          "отлично дополняют друг друга. Какую идею вы сейчас развиваете?",
        "exchange": "Привет, {first}! Нам обоим близка тема «{topic}». "
                    "Как она устроена у вас в команде?",
    },
    "kk": {
        "find_job": "Сәлеметсіз бе, {first}! Мен {my_role}, негізгі стегім — {topic}. "
                    "Командаңыз қазір қандай міндеттермен айналысады?",
        "find_job_nostack": "Сәлеметсіз бе, {first}! Мен {my_role}, жұмыс іздеп жүрмін. "
                            "Қазір қандай мамандарды іздеп жатырсыз?",
        "hire": "Сәлем, {first}! Профиліңізде {topic} бар екен — бізде дәл осындай бос орын ашық. "
                "Бірнеше минут уақытыңыз бар ма?",
        "find_mentor": "Сәлеметсіз бе, {first}! «{topic}» бағытында дамығым келеді. "
                       "Жолыңыз туралы бірнеше сұрақ қоюға бола ма?",
        "be_mentor": "Сәлем, {first}! «{topic}» бағытында тәлімгер іздеп жүргеніңізді көрдім — "
                     "тәжірибеммен бөлісе аламын. Қазір басты мақсатыңыз қандай?",
        "find_cofounder": "Сәлем, {first}! Мен {my_role}, кофаундер іздеп жүрмін — рөлдеріміз "
                          "бірін-бірі жақсы толықтыратын сияқты. Қазір қандай идеямен айналысып жүрсіз?",
        "exchange": "Сәлем, {first}! Екеумізге де «{topic}» тақырыбы жақын. "
                    "Сіздің командаңызда бұл қалай жасалады?",
    },
    "en": {
        "find_job": "Hi {first}! I'm {my_role_a}, and my main stack is {topic}. "
                    "What is your team working on right now?",
        "find_job_nostack": "Hi {first}! I'm {my_role_a} looking for a job. "
                            "What kind of people are you hiring right now?",
        "hire": "Hi {first}! I see {topic} in your profile — we have an opening that fits. "
                "Do you have a couple of minutes?",
        "find_mentor": "Hi {first}! I want to grow in {topic}. "
                       "Could I ask you a couple of questions about your path?",
        "be_mentor": "Hi {first}! I see you're looking for a mentor in {topic} — happy to share "
                     "my experience. What's your main challenge right now?",
        "find_cofounder": "Hi {first}! I'm {my_role_a} looking for a co-founder — our roles seem "
                          "to complement each other. What idea are you working on?",
        "exchange": "Hi {first}! We both care about {topic}. How does it work in your team?",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    text = UI.get(lang, UI["ru"]).get(key) or UI["ru"][key]
    return text.format(**kwargs) if kwargs else text
